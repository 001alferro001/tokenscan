import logging
import os
from typing import Dict, Optional, List
from datetime import datetime, timedelta
import statistics

logger = logging.getLogger(__name__)

class VolumeAnalyzer:
    def __init__(self, db_manager, telegram_bot=None):
        self.db_manager = db_manager
        self.telegram_bot = telegram_bot
        self.settings = {
            'analysis_hours': int(os.getenv('ANALYSIS_HOURS', 1)),
            'offset_minutes': int(os.getenv('OFFSET_MINUTES', 0)),
            'volume_multiplier': float(os.getenv('VOLUME_MULTIPLIER', 2.0)),
            'min_volume_usdt': int(os.getenv('MIN_VOLUME_USDT', 1000)),
            'alert_grouping_minutes': int(os.getenv('ALERT_GROUPING_MINUTES', 5)),
            # Новые настройки для подряд идущих LONG свечей
            'consecutive_long_count': int(os.getenv('CONSECUTIVE_LONG_COUNT', 5)),
            'max_shadow_to_body_ratio': float(os.getenv('MAX_SHADOW_TO_BODY_RATIO', 1.0)),
            'min_body_percentage': float(os.getenv('MIN_BODY_PERCENTAGE', 0.1))
        }
        self.stats = {
            'total_candles': 0,
            'long_candles': 0,
            'alerts_count': 0,
            'consecutive_alerts_count': 0,
            'last_update': None
        }
        # Кэш для хранения последних свечей каждого символа
        self.candle_cache = {}

    async def analyze_volume(self, symbol: str, kline_data: Dict) -> Optional[Dict]:
        """Анализ объема для определения алертов"""
        try:
            # Проверяем, является ли свеча LONG
            is_long = float(kline_data['close']) > float(kline_data['open'])
            if not is_long:
                return None

            # Рассчитываем объем в USDT
            current_volume_usdt = float(kline_data['volume']) * float(kline_data['close'])
            
            # Проверяем минимальный объем
            if current_volume_usdt < self.settings['min_volume_usdt']:
                return None

            # Получаем исторические объемы LONG свечей
            historical_volumes = await self.db_manager.get_historical_long_volumes(
                symbol, 
                self.settings['analysis_hours'], 
                self.settings['offset_minutes']
            )

            if len(historical_volumes) < 10:  # Недостаточно данных для анализа
                return None

            # Рассчитываем средний объем
            average_volume = statistics.mean(historical_volumes)
            
            # Проверяем превышение объема
            volume_ratio = current_volume_usdt / average_volume if average_volume > 0 else 0
            
            if volume_ratio >= self.settings['volume_multiplier']:
                # Создаем данные алерта
                alert_data = {
                    'symbol': symbol,
                    'alert_type': 'volume_spike',
                    'price': float(kline_data['close']),
                    'volume_ratio': round(volume_ratio, 2),
                    'current_volume_usdt': int(current_volume_usdt),
                    'average_volume_usdt': int(average_volume),
                    'timestamp': datetime.now(),
                    'message': f"Объем превышен в {volume_ratio:.2f}x раз"
                }
                
                # Проверяем, есть ли недавняя группа алертов для этого символа
                recent_group = await self.db_manager.get_recent_alert_group(
                    symbol, 
                    self.settings['alert_grouping_minutes']
                )
                
                if recent_group:
                    # Обновляем существующую группу
                    await self.db_manager.update_alert_group(recent_group['id'], alert_data)
                    await self.db_manager.save_alert(recent_group['id'], alert_data)
                    
                    alert_data['is_grouped'] = True
                    alert_data['group_id'] = recent_group['id']
                    alert_data['group_count'] = recent_group['alert_count'] + 1
                else:
                    # Создаем новую группу
                    group_id = await self.db_manager.create_alert_group(alert_data)
                    await self.db_manager.save_alert(group_id, alert_data)
                    
                    alert_data['is_grouped'] = False
                    alert_data['group_id'] = group_id
                    alert_data['group_count'] = 1
                    
                    # Отправляем в Telegram только новые группы алертов
                    if self.telegram_bot:
                        await self.telegram_bot.send_alert(alert_data)
                
                # Обновляем статистику
                self.stats['alerts_count'] += 1
                
                # Преобразуем timestamp в ISO строку для JSON
                alert_data['timestamp'] = alert_data['timestamp'].isoformat()
                
                return alert_data

            return None

        except Exception as e:
            logger.error(f"Ошибка анализа объема для {symbol}: {e}")
            return None

    async def analyze_consecutive_long_candles(self, symbol: str, kline_data: Dict) -> Optional[Dict]:
        """Анализ подряд идущих LONG свечей с маленьким телом"""
        try:
            # Проверяем, является ли свеча LONG
            open_price = float(kline_data['open'])
            close_price = float(kline_data['close'])
            high_price = float(kline_data['high'])
            low_price = float(kline_data['low'])
            
            is_long = close_price > open_price
            if not is_long:
                # Если свеча не LONG, сбрасываем счетчик для этого символа
                if symbol in self.candle_cache:
                    self.candle_cache[symbol] = []
                return None

            # Рассчитываем параметры свечи
            body_size = abs(close_price - open_price)
            upper_shadow = high_price - max(open_price, close_price)
            lower_shadow = min(open_price, close_price) - low_price
            total_shadow = upper_shadow + lower_shadow
            candle_range = high_price - low_price
            
            # Проверяем условия для "маленького тела"
            body_percentage = (body_size / candle_range) * 100 if candle_range > 0 else 0
            shadow_to_body_ratio = total_shadow / body_size if body_size > 0 else float('inf')
            
            # Условия для подходящей свечи:
            # 1. Тело составляет минимальный процент от всей свечи
            # 2. Тени не превышают определенное соотношение к телу
            is_suitable_candle = (
                body_percentage >= self.settings['min_body_percentage'] and
                shadow_to_body_ratio <= self.settings['max_shadow_to_body_ratio']
            )
            
            if not is_suitable_candle:
                # Если свеча не подходит, сбрасываем счетчик
                if symbol in self.candle_cache:
                    self.candle_cache[symbol] = []
                return None

            # Инициализируем кэш для символа, если его нет
            if symbol not in self.candle_cache:
                self.candle_cache[symbol] = []

            # Добавляем текущую свечу в кэш
            candle_info = {
                'timestamp': int(kline_data['start']),
                'open': open_price,
                'close': close_price,
                'high': high_price,
                'low': low_price,
                'body_percentage': body_percentage,
                'shadow_to_body_ratio': shadow_to_body_ratio
            }
            
            self.candle_cache[symbol].append(candle_info)
            
            # Ограничиваем размер кэша
            max_cache_size = self.settings['consecutive_long_count'] + 5
            if len(self.candle_cache[symbol]) > max_cache_size:
                self.candle_cache[symbol] = self.candle_cache[symbol][-max_cache_size:]

            # Проверяем, достигли ли мы нужного количества подряд идущих свечей
            consecutive_count = len(self.candle_cache[symbol])
            
            if consecutive_count >= self.settings['consecutive_long_count']:
                # Создаем алерт
                alert_data = {
                    'symbol': symbol,
                    'alert_type': 'consecutive_long',
                    'price': close_price,
                    'consecutive_count': consecutive_count,
                    'avg_body_percentage': sum(c['body_percentage'] for c in self.candle_cache[symbol]) / consecutive_count,
                    'avg_shadow_ratio': sum(c['shadow_to_body_ratio'] for c in self.candle_cache[symbol]) / consecutive_count,
                    'timestamp': datetime.now(),
                    'message': f"{consecutive_count} подряд идущих LONG свечей с маленьким телом"
                }
                
                # Проверяем недавние группы алертов
                recent_group = await self.db_manager.get_recent_alert_group(
                    symbol, 
                    self.settings['alert_grouping_minutes'],
                    'consecutive_long'
                )
                
                if recent_group:
                    # Обновляем существующую группу
                    await self.db_manager.update_alert_group(recent_group['id'], alert_data)
                    await self.db_manager.save_alert(recent_group['id'], alert_data)
                    
                    alert_data['is_grouped'] = True
                    alert_data['group_id'] = recent_group['id']
                    alert_data['group_count'] = recent_group['alert_count'] + 1
                else:
                    # Создаем новую группу
                    group_id = await self.db_manager.create_alert_group(alert_data)
                    await self.db_manager.save_alert(group_id, alert_data)
                    
                    alert_data['is_grouped'] = False
                    alert_data['group_id'] = group_id
                    alert_data['group_count'] = 1
                    
                    # Отправляем в Telegram
                    if self.telegram_bot:
                        await self.telegram_bot.send_consecutive_alert(alert_data)

                # Обновляем статистику
                self.stats['consecutive_alerts_count'] += 1
                
                # Сбрасываем кэш после создания алерта
                self.candle_cache[symbol] = []
                
                # Преобразуем timestamp в ISO строку для JSON
                alert_data['timestamp'] = alert_data['timestamp'].isoformat()
                
                return alert_data

            return None

        except Exception as e:
            logger.error(f"Ошибка анализа подряд идущих свечей для {symbol}: {e}")
            return None

    def update_settings(self, new_settings: Dict):
        """Обновление настроек анализатора"""
        self.settings.update(new_settings)
        logger.info(f"Настройки анализатора обновлены: {self.settings}")

    def get_settings(self) -> Dict:
        """Получение текущих настроек"""
        return self.settings.copy()

    async def get_stats(self) -> Dict:
        """Получение статистики работы"""
        self.stats['last_update'] = datetime.now().isoformat()
        return self.stats.copy()

    def update_stats(self, is_long: bool = False):
        """Обновление статистики"""
        self.stats['total_candles'] += 1
        if is_long:
            self.stats['long_candles'] += 1