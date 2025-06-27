import logging
import os
from typing import Dict, Optional, List
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)

class AlertType(Enum):
    VOLUME_SPIKE = "volume_spike"
    CONSECUTIVE_LONG = "consecutive_long"
    PRIORITY = "priority"

class AlertStatus(Enum):
    PENDING = "pending"
    TRUE_SIGNAL = "true_signal"
    FALSE_SIGNAL = "false_signal"
    CLOSED = "closed"

class AlertManager:
    def __init__(self, db_manager, telegram_bot=None, connection_manager=None):
        self.db_manager = db_manager
        self.telegram_bot = telegram_bot
        self.connection_manager = connection_manager
        
        # Настройки из переменных окружения
        self.settings = {
            'volume_alerts_enabled': True,
            'consecutive_alerts_enabled': True,
            'priority_alerts_enabled': True,
            'analysis_hours': int(os.getenv('ANALYSIS_HOURS', 1)),
            'volume_multiplier': float(os.getenv('VOLUME_MULTIPLIER', 2.0)),
            'min_volume_usdt': int(os.getenv('MIN_VOLUME_USDT', 1000)),
            'consecutive_long_count': int(os.getenv('CONSECUTIVE_LONG_COUNT', 5)),
            'alert_grouping_minutes': int(os.getenv('ALERT_GROUPING_MINUTES', 5)),
            'data_retention_hours': int(os.getenv('DATA_RETENTION_HOURS', 2))
        }
        
        # Кэш для отслеживания состояния свечей и алертов
        self.candle_cache = {}  # symbol -> list of recent candles
        self.volume_alerts_cache = {}  # symbol -> {timestamp, preliminary_alert, alert_level}
        self.consecutive_counters = {}  # symbol -> consecutive long count
        self.priority_signals = {}  # symbol -> priority signal data
        
        logger.info("AlertManager инициализирован")

    async def process_kline_data(self, symbol: str, kline_data: Dict) -> List[Dict]:
        """Обработка данных свечи и генерация алертов"""
        alerts = []
        
        try:
            # Сохраняем данные свечи в кэш
            await self._update_candle_cache(symbol, kline_data)
            
            # Проверяем алерты по объему (в процессе формирования свечи)
            if self.settings['volume_alerts_enabled']:
                volume_alert = await self._check_volume_alert(symbol, kline_data, is_closed=False)
                if volume_alert:
                    alerts.append(volume_alert)
            
            # Если свеча закрылась, обрабатываем закрытие
            if self._is_candle_closed(kline_data):
                closed_alerts = await self._process_candle_close(symbol, kline_data)
                alerts.extend(closed_alerts)
            
            # Отправляем алерты
            for alert in alerts:
                await self._send_alert(alert)
                
        except Exception as e:
            logger.error(f"Ошибка обработки данных свечи для {symbol}: {e}")
        
        return alerts

    async def _update_candle_cache(self, symbol: str, kline_data: Dict):
        """Обновление кэша свечей"""
        if symbol not in self.candle_cache:
            self.candle_cache[symbol] = []
        
        # Добавляем или обновляем текущую свечу
        timestamp = int(kline_data['start'])
        
        # Проверяем, есть ли уже свеча с таким временем
        existing_index = None
        for i, candle in enumerate(self.candle_cache[symbol]):
            if candle['timestamp'] == timestamp:
                existing_index = i
                break
        
        candle_info = {
            'timestamp': timestamp,
            'open': float(kline_data['open']),
            'high': float(kline_data['high']),
            'low': float(kline_data['low']),
            'close': float(kline_data['close']),
            'volume': float(kline_data['volume']),
            'volume_usdt': float(kline_data['volume']) * float(kline_data['close']),
            'is_long': float(kline_data['close']) > float(kline_data['open']),
            'is_closed': self._is_candle_closed(kline_data)
        }
        
        if existing_index is not None:
            self.candle_cache[symbol][existing_index] = candle_info
        else:
            self.candle_cache[symbol].append(candle_info)
        
        # Ограничиваем размер кэша
        max_cache_size = 120  # 2 часа данных
        if len(self.candle_cache[symbol]) > max_cache_size:
            self.candle_cache[symbol] = self.candle_cache[symbol][-max_cache_size:]

    def _is_candle_closed(self, kline_data: Dict) -> bool:
        """Проверка, закрылась ли свеча"""
        current_time = datetime.now().timestamp() * 1000
        candle_end_time = int(kline_data['end'])
        
        # Свеча считается закрытой, если прошло время её окончания
        return current_time >= candle_end_time

    async def _check_volume_alert(self, symbol: str, kline_data: Dict, is_closed: bool = False) -> Optional[Dict]:
        """Проверка алерта по превышению объема с улучшенной логикой"""
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
            
            # Получаем исторические объемы
            historical_volumes = await self.db_manager.get_historical_long_volumes(
                symbol, 
                self.settings['analysis_hours'], 
                offset_minutes=1  # Исключаем текущую минуту
            )
            
            if len(historical_volumes) < 10:
                return None
            
            # Рассчитываем средний объем
            average_volume = sum(historical_volumes) / len(historical_volumes)
            volume_ratio = current_volume_usdt / average_volume if average_volume > 0 else 0
            
            if volume_ratio >= self.settings['volume_multiplier']:
                timestamp = int(kline_data['start'])
                current_price = float(kline_data['close'])
                
                # Создаем данные свечи для алерта
                candle_data = {
                    'open': float(kline_data['open']),
                    'high': float(kline_data['high']),
                    'low': float(kline_data['low']),
                    'close': current_price,
                    'volume': float(kline_data['volume'])
                }
                
                if not is_closed:
                    # Первый алерт (предварительный - в процессе формирования)
                    if symbol in self.volume_alerts_cache and self.volume_alerts_cache[symbol]['timestamp'] == timestamp:
                        return None  # Уже есть предварительный алерт для этой минуты
                    
                    # Сохраняем уровень цены, на котором сработал алерт
                    alert_level = current_price
                    candle_data['alert_level'] = alert_level
                    
                    alert_data = {
                        'symbol': symbol,
                        'alert_type': AlertType.VOLUME_SPIKE.value,
                        'price': current_price,
                        'volume_ratio': round(volume_ratio, 2),
                        'current_volume_usdt': int(current_volume_usdt),
                        'average_volume_usdt': int(average_volume),
                        'timestamp': datetime.fromtimestamp(timestamp / 1000),
                        'is_closed': False,
                        'is_true_signal': None,
                        'candle_data': candle_data,
                        'message': f"Предварительный алерт: объем превышен в {volume_ratio:.2f}x раз"
                    }
                    
                    # Сохраняем в кэш
                    self.volume_alerts_cache[symbol] = {
                        'timestamp': timestamp,
                        'preliminary_alert': alert_data,
                        'alert_level': alert_level
                    }
                    
                    return alert_data
                else:
                    # Второй алерт (финальный - после закрытия свечи)
                    if symbol in self.volume_alerts_cache and self.volume_alerts_cache[symbol]['timestamp'] == timestamp:
                        # Обновляем существующий алерт
                        cached_data = self.volume_alerts_cache[symbol]
                        preliminary_alert = cached_data['preliminary_alert']
                        alert_level = cached_data.get('alert_level', current_price)
                        
                        # Определяем, истинный ли это сигнал (свеча закрылась в LONG)
                        final_is_long = float(kline_data['close']) > float(kline_data['open'])
                        
                        # Обновляем данные свечи с уровнем алерта
                        candle_data['alert_level'] = alert_level
                        
                        alert_data = {
                            'symbol': symbol,
                            'alert_type': AlertType.VOLUME_SPIKE.value,
                            'price': current_price,
                            'volume_ratio': round(volume_ratio, 2),
                            'current_volume_usdt': int(current_volume_usdt),
                            'average_volume_usdt': int(average_volume),
                            'timestamp': datetime.fromtimestamp(timestamp / 1000),
                            'close_timestamp': datetime.fromtimestamp(int(kline_data['end']) / 1000),
                            'is_closed': True,
                            'is_true_signal': final_is_long,
                            'candle_data': candle_data,
                            'preliminary_alert': preliminary_alert,
                            'message': f"Финальный алерт: объем превышен в {volume_ratio:.2f}x раз ({'истинный' if final_is_long else 'ложный'} сигнал)"
                        }
                        
                        # Удаляем из кэша
                        del self.volume_alerts_cache[symbol]
                        
                        return alert_data
                    else:
                        # Создаем новый финальный алерт (если не было предварительного)
                        final_is_long = float(kline_data['close']) > float(kline_data['open'])
                        candle_data['alert_level'] = current_price
                        
                        alert_data = {
                            'symbol': symbol,
                            'alert_type': AlertType.VOLUME_SPIKE.value,
                            'price': current_price,
                            'volume_ratio': round(volume_ratio, 2),
                            'current_volume_usdt': int(current_volume_usdt),
                            'average_volume_usdt': int(average_volume),
                            'timestamp': datetime.fromtimestamp(timestamp / 1000),
                            'close_timestamp': datetime.fromtimestamp(int(kline_data['end']) / 1000),
                            'is_closed': True,
                            'is_true_signal': final_is_long,
                            'candle_data': candle_data,
                            'message': f"Объем превышен в {volume_ratio:.2f}x раз ({'истинный' if final_is_long else 'ложный'} сигнал)"
                        }
                        
                        return alert_data
            
            return None
            
        except Exception as e:
            logger.error(f"Ошибка проверки алерта по объему для {symbol}: {e}")
            return None

    async def _process_candle_close(self, symbol: str, kline_data: Dict) -> List[Dict]:
        """Обработка закрытия свечи"""
        alerts = []
        
        try:
            # Проверяем алерт по объему при закрытии
            if self.settings['volume_alerts_enabled']:
                volume_alert = await self._check_volume_alert(symbol, kline_data, is_closed=True)
                if volume_alert:
                    alerts.append(volume_alert)
            
            # Проверяем последовательные LONG свечи
            if self.settings['consecutive_alerts_enabled']:
                consecutive_alert = await self._check_consecutive_long_alert(symbol, kline_data)
                if consecutive_alert:
                    alerts.append(consecutive_alert)
            
            # Проверяем приоритетные сигналы
            if self.settings['priority_alerts_enabled']:
                priority_alert = await self._check_priority_signal(symbol, alerts)
                if priority_alert:
                    alerts.append(priority_alert)
                    
        except Exception as e:
            logger.error(f"Ошибка обработки закрытия свечи для {symbol}: {e}")
        
        return alerts

    async def _check_consecutive_long_alert(self, symbol: str, kline_data: Dict) -> Optional[Dict]:
        """Проверка алерта по подряд идущим LONG свечам"""
        try:
            is_long = float(kline_data['close']) > float(kline_data['open'])
            
            if symbol not in self.consecutive_counters:
                self.consecutive_counters[symbol] = 0
            
            if is_long:
                self.consecutive_counters[symbol] += 1
                
                # Проверяем, достигли ли нужного количества
                if self.consecutive_counters[symbol] == self.settings['consecutive_long_count']:
                    candle_data = {
                        'open': float(kline_data['open']),
                        'high': float(kline_data['high']),
                        'low': float(kline_data['low']),
                        'close': float(kline_data['close']),
                        'volume': float(kline_data['volume'])
                    }
                    
                    alert_data = {
                        'symbol': symbol,
                        'alert_type': AlertType.CONSECUTIVE_LONG.value,
                        'price': float(kline_data['close']),
                        'consecutive_count': self.consecutive_counters[symbol],
                        'timestamp': datetime.fromtimestamp(int(kline_data['start']) / 1000),
                        'close_timestamp': datetime.fromtimestamp(int(kline_data['end']) / 1000),
                        'is_closed': True,
                        'candle_data': candle_data,
                        'message': f"{self.consecutive_counters[symbol]} подряд идущих LONG свечей"
                    }
                    
                    return alert_data
                elif self.consecutive_counters[symbol] > self.settings['consecutive_long_count']:
                    # Обновляем счетчик без создания нового алерта
                    # Отправляем обновление в интерфейс
                    if self.connection_manager:
                        await self.connection_manager.broadcast_json({
                            'type': 'consecutive_update',
                            'symbol': symbol,
                            'count': self.consecutive_counters[symbol]
                        })
            else:
                # Сбрасываем счетчик при SHORT свече
                self.consecutive_counters[symbol] = 0
            
            return None
            
        except Exception as e:
            logger.error(f"Ошибка проверки последовательных LONG свечей для {symbol}: {e}")
            return None

    async def _check_priority_signal(self, symbol: str, current_alerts: List[Dict]) -> Optional[Dict]:
        """Проверка приоритетного сигнала"""
        try:
            # Приоритетный сигнал формируется, если есть и объемный алерт, и алерт по последовательности
            volume_alert = None
            consecutive_alert = None
            
            for alert in current_alerts:
                if alert['alert_type'] == AlertType.VOLUME_SPIKE.value:
                    volume_alert = alert
                elif alert['alert_type'] == AlertType.CONSECUTIVE_LONG.value:
                    consecutive_alert = alert
            
            # Также проверяем, был ли объемный алерт в рамках текущей последовательности
            if consecutive_alert and symbol in self.consecutive_counters:
                # Проверяем, был ли объемный всплеск в последние N свечей
                recent_volume_alert = await self._check_recent_volume_alert(symbol, self.consecutive_counters[symbol])
                
                if volume_alert or recent_volume_alert:
                    candle_data = consecutive_alert.get('candle_data', {})
                    if volume_alert and volume_alert.get('candle_data'):
                        candle_data.update(volume_alert['candle_data'])
                    
                    priority_data = {
                        'symbol': symbol,
                        'alert_type': AlertType.PRIORITY.value,
                        'price': consecutive_alert['price'],
                        'consecutive_count': consecutive_alert['consecutive_count'],
                        'timestamp': consecutive_alert['timestamp'],
                        'close_timestamp': consecutive_alert['close_timestamp'],
                        'is_closed': True,
                        'candle_data': candle_data,
                        'message': f"Приоритетный сигнал: {consecutive_alert['consecutive_count']} LONG свечей + всплеск объема"
                    }
                    
                    if volume_alert:
                        priority_data.update({
                            'volume_ratio': volume_alert['volume_ratio'],
                            'current_volume_usdt': volume_alert['current_volume_usdt'],
                            'average_volume_usdt': volume_alert['average_volume_usdt']
                        })
                    
                    return priority_data
            
            return None
            
        except Exception as e:
            logger.error(f"Ошибка проверки приоритетного сигнала для {symbol}: {e}")
            return None

    async def _check_recent_volume_alert(self, symbol: str, candles_back: int) -> bool:
        """Проверка, был ли объемный алерт в последних N свечах"""
        try:
            # Получаем недавние алерты по объему для символа
            recent_alerts = await self.db_manager.get_recent_volume_alerts(
                symbol, 
                minutes_back=candles_back
            )
            
            return len(recent_alerts) > 0
            
        except Exception as e:
            logger.error(f"Ошибка проверки недавних объемных алертов для {symbol}: {e}")
            return False

    async def _send_alert(self, alert_data: Dict):
        """Отправка алерта"""
        try:
            # Сохраняем в базу данных
            alert_id = await self.db_manager.save_alert(alert_data)
            alert_data['id'] = alert_id
            
            # Отправляем в WebSocket
            if self.connection_manager:
                await self.connection_manager.broadcast_json({
                    'type': 'new_alert',
                    'alert': self._serialize_alert(alert_data)
                })
            
            # Отправляем в Telegram (только для финальных алертов)
            if self.telegram_bot and alert_data.get('is_closed', False):
                if alert_data['alert_type'] == AlertType.VOLUME_SPIKE.value:
                    await self.telegram_bot.send_volume_alert(alert_data)
                elif alert_data['alert_type'] == AlertType.CONSECUTIVE_LONG.value:
                    await self.telegram_bot.send_consecutive_alert(alert_data)
                elif alert_data['alert_type'] == AlertType.PRIORITY.value:
                    await self.telegram_bot.send_priority_alert(alert_data)
            
            logger.info(f"Алерт отправлен: {alert_data['symbol']} - {alert_data['alert_type']}")
            
        except Exception as e:
            logger.error(f"Ошибка отправки алерта: {e}")

    def _serialize_alert(self, alert_data: Dict) -> Dict:
        """Сериализация алерта для JSON"""
        serialized = alert_data.copy()
        
        # Преобразуем datetime в ISO строки
        for key in ['timestamp', 'close_timestamp']:
            if key in serialized and isinstance(serialized[key], datetime):
                serialized[key] = serialized[key].isoformat()
        
        # Сериализуем вложенные алерты
        if 'preliminary_alert' in serialized and serialized['preliminary_alert']:
            serialized['preliminary_alert'] = self._serialize_alert(serialized['preliminary_alert'])
        
        return serialized

    def update_settings(self, new_settings: Dict):
        """Обновление настроек"""
        self.settings.update(new_settings)
        logger.info(f"Настройки AlertManager обновлены: {self.settings}")

    def get_settings(self) -> Dict:
        """Получение текущих настроек"""
        return self.settings.copy()

    async def cleanup_old_data(self):
        """Очистка старых данных"""
        try:
            # Очищаем кэш свечей
            cutoff_time = datetime.now() - timedelta(hours=self.settings['data_retention_hours'])
            cutoff_timestamp = int(cutoff_time.timestamp() * 1000)
            
            for symbol in list(self.candle_cache.keys()):
                if symbol in self.candle_cache:
                    self.candle_cache[symbol] = [
                        candle for candle in self.candle_cache[symbol]
                        if candle['timestamp'] >= cutoff_timestamp
                    ]
                    
                    if not self.candle_cache[symbol]:
                        del self.candle_cache[symbol]
            
            # Очищаем кэш объемных алертов (старше 5 минут)
            alert_cutoff = datetime.now() - timedelta(minutes=5)
            alert_cutoff_timestamp = int(alert_cutoff.timestamp() * 1000)
            
            for symbol in list(self.volume_alerts_cache.keys()):
                if self.volume_alerts_cache[symbol]['timestamp'] < alert_cutoff_timestamp:
                    del self.volume_alerts_cache[symbol]
            
            logger.info("Очистка старых данных завершена")
            
        except Exception as e:
            logger.error(f"Ошибка очистки старых данных: {e}")