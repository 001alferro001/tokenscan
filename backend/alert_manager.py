import logging
import os
from typing import Dict, Optional, List
from datetime import datetime, timedelta
from enum import Enum
import asyncio
import aiohttp

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

class ImbalanceAnalyzer:
    """Анализатор имбалансов на основе концепций Smart Money"""
    
    def __init__(self):
        self.min_gap_percentage = 0.1  # Минимальный размер гэпа в %
        self.min_strength = 0.5  # Минимальная сила сигнала
    
    def analyze_fair_value_gap(self, candles: List[Dict]) -> Optional[Dict]:
        """Анализ Fair Value Gap"""
        if len(candles) < 3:
            return None
        
        # Берем последние 3 свечи
        prev_candle = candles[-3]
        current_candle = candles[-2]
        next_candle = candles[-1]
        
        # Bullish FVG: предыдущая свеча low > следующая свеча high
        if prev_candle['low'] > next_candle['high'] and current_candle['is_long']:
            gap_size = (prev_candle['low'] - next_candle['high']) / next_candle['high'] * 100
            if gap_size >= self.min_gap_percentage:
                return {
                    'type': 'fair_value_gap',
                    'direction': 'bullish',
                    'strength': gap_size,
                    'top': prev_candle['low'],
                    'bottom': next_candle['high'],
                    'timestamp': current_candle['timestamp']
                }
        
        # Bearish FVG: предыдущая свеча high < следующая свеча low
        if prev_candle['high'] < next_candle['low'] and not current_candle['is_long']:
            gap_size = (next_candle['low'] - prev_candle['high']) / prev_candle['high'] * 100
            if gap_size >= self.min_gap_percentage:
                return {
                    'type': 'fair_value_gap',
                    'direction': 'bearish',
                    'strength': gap_size,
                    'top': next_candle['low'],
                    'bottom': prev_candle['high'],
                    'timestamp': current_candle['timestamp']
                }
        
        return None
    
    def analyze_order_block(self, candles: List[Dict]) -> Optional[Dict]:
        """Анализ Order Block"""
        if len(candles) < 10:
            return None
        
        current_candle = candles[-1]
        window = candles[-10:-1]  # Последние 9 свечей перед текущей
        
        # Bullish Order Block: последняя медвежья свеча перед сильным восходящим движением
        last_bearish = None
        for candle in reversed(window):
            if not candle['is_long']:
                last_bearish = candle
                break
        
        if last_bearish and current_candle['is_long']:
            price_move = (current_candle['close'] - last_bearish['high']) / last_bearish['high'] * 100
            if price_move >= 2.0:  # Движение минимум на 2%
                return {
                    'type': 'order_block',
                    'direction': 'bullish',
                    'strength': price_move,
                    'top': last_bearish['high'],
                    'bottom': last_bearish['low'],
                    'timestamp': last_bearish['timestamp']
                }
        
        # Bearish Order Block: последняя бычья свеча перед сильным нисходящим движением
        last_bullish = None
        for candle in reversed(window):
            if candle['is_long']:
                last_bullish = candle
                break
        
        if last_bullish and not current_candle['is_long']:
            price_move = (last_bullish['low'] - current_candle['close']) / last_bullish['low'] * 100
            if price_move >= 2.0:  # Движение минимум на 2%
                return {
                    'type': 'order_block',
                    'direction': 'bearish',
                    'strength': price_move,
                    'top': last_bullish['high'],
                    'bottom': last_bullish['low'],
                    'timestamp': last_bullish['timestamp']
                }
        
        return None
    
    def analyze_breaker_block(self, candles: List[Dict]) -> Optional[Dict]:
        """Анализ Breaker Block (пробитый Order Block)"""
        if len(candles) < 15:
            return None
        
        # Ищем пробитые уровни поддержки/сопротивления
        current_candle = candles[-1]
        window = candles[-15:-1]
        
        # Находим значимые уровни
        highs = [c['high'] for c in window]
        lows = [c['low'] for c in window]
        
        max_high = max(highs)
        min_low = min(lows)
        
        # Bullish Breaker: пробитие вниз с последующим возвратом вверх
        if current_candle['close'] > max_high and current_candle['is_long']:
            strength = (current_candle['close'] - max_high) / max_high * 100
            if strength >= 1.0:
                return {
                    'type': 'breaker_block',
                    'direction': 'bullish',
                    'strength': strength,
                    'top': max_high,
                    'bottom': min_low,
                    'timestamp': current_candle['timestamp']
                }
        
        # Bearish Breaker: пробитие вверх с последующим возвратом вниз
        if current_candle['close'] < min_low and not current_candle['is_long']:
            strength = (min_low - current_candle['close']) / min_low * 100
            if strength >= 1.0:
                return {
                    'type': 'breaker_block',
                    'direction': 'bearish',
                    'strength': strength,
                    'top': max_high,
                    'bottom': min_low,
                    'timestamp': current_candle['timestamp']
                }
        
        return None

class AlertManager:
    def __init__(self, db_manager, telegram_bot=None, connection_manager=None, time_sync=None):
        self.db_manager = db_manager
        self.telegram_bot = telegram_bot
        self.connection_manager = connection_manager
        self.time_sync = time_sync
        self.imbalance_analyzer = ImbalanceAnalyzer()
        
        # Настройки из переменных окружения
        self.settings = {
            'volume_alerts_enabled': True,
            'consecutive_alerts_enabled': True,
            'priority_alerts_enabled': True,
            'analysis_hours': int(os.getenv('ANALYSIS_HOURS', 1)),
            'offset_minutes': int(os.getenv('OFFSET_MINUTES', 0)),
            'volume_multiplier': float(os.getenv('VOLUME_MULTIPLIER', 2.0)),
            'min_volume_usdt': int(os.getenv('MIN_VOLUME_USDT', 1000)),
            'consecutive_long_count': int(os.getenv('CONSECUTIVE_LONG_COUNT', 5)),
            'alert_grouping_minutes': int(os.getenv('ALERT_GROUPING_MINUTES', 5)),
            'data_retention_hours': int(os.getenv('DATA_RETENTION_HOURS', 2)),
            'update_interval_seconds': int(os.getenv('UPDATE_INTERVAL_SECONDS', 1)),
            'notification_enabled': True,
            'volume_type': 'long',
            'orderbook_enabled': False,
            'orderbook_snapshot_on_alert': False,
            'imbalance_enabled': True,
            'fair_value_gap_enabled': True,
            'order_block_enabled': True,
            'breaker_block_enabled': True
        }
        
        # Кэш для отслеживания состояния алертов
        self.volume_alerts_cache = {}  # symbol -> {timestamp, alert_id, alert_level}
        self.consecutive_counters = {}  # symbol -> consecutive long count
        self.consecutive_alert_ids = {}  # symbol -> ID текущего алерта по последовательности
        self.alert_cooldowns = {}  # symbol -> last alert timestamp
        
        logger.info("AlertManager инициализирован с анализом имбаланса и синхронизацией времени")

    def _get_current_time(self) -> datetime:
        """Получить текущее время (биржевое, если доступно)"""
        if self.time_sync:
            return self.time_sync.get_exchange_time()
        return datetime.utcnow()

    def _is_candle_closed(self, kline_data: Dict) -> bool:
        """Проверка, закрылась ли свеча (используя биржевое время)"""
        if self.time_sync:
            return self.time_sync.is_candle_closed(kline_data)
        
        # Fallback на UTC время
        current_time = datetime.utcnow().timestamp() * 1000
        candle_end_time = int(kline_data['end'])
        return current_time >= candle_end_time

    async def process_kline_data(self, symbol: str, kline_data: Dict) -> List[Dict]:
        """Обработка данных свечи и генерация алертов"""
        alerts = []
        
        try:
            # Определяем, закрылась ли свеча
            is_closed = self._is_candle_closed(kline_data)
            
            # Сохраняем данные в базу
            await self.db_manager.save_kline_data(symbol, kline_data, is_closed)
            
            # Обрабатываем алерты только для закрытых свечей
            if is_closed:
                alerts = await self._process_closed_candle(symbol, kline_data)
            
            # Отправляем алерты
            for alert in alerts:
                await self._send_alert(alert)
                
        except Exception as e:
            logger.error(f"Ошибка обработки данных свечи для {symbol}: {e}")
        
        return alerts

    async def _process_closed_candle(self, symbol: str, kline_data: Dict) -> List[Dict]:
        """Обработка закрытой свечи - генерация алертов"""
        alerts = []
        
        try:
            # Проверяем алерт по объему
            if self.settings['volume_alerts_enabled']:
                volume_alert = await self._check_volume_alert(symbol, kline_data)
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
            logger.error(f"Ошибка обработки закрытой свечи для {symbol}: {e}")
        
        return alerts

    async def _check_volume_alert(self, symbol: str, kline_data: Dict) -> Optional[Dict]:
        """Проверка алерта по превышению объема"""
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
            
            timestamp = int(kline_data['start'])
            
            # Проверяем кулдаун для повторных сигналов
            if symbol in self.alert_cooldowns:
                last_alert_time = self.alert_cooldowns[symbol]
                current_time = self._get_current_time()
                cooldown_period = self.settings['alert_grouping_minutes']
                if (current_time - last_alert_time).total_seconds() < cooldown_period * 60:
                    return None
            
            # Получаем исторические объемы
            historical_volumes = await self.db_manager.get_historical_long_volumes(
                symbol, 
                self.settings['analysis_hours'], 
                offset_minutes=self.settings['offset_minutes'],
                volume_type=self.settings['volume_type']
            )
            
            if len(historical_volumes) < 10:
                logger.debug(f"Недостаточно исторических данных для {symbol}: {len(historical_volumes)}")
                return None
            
            # Рассчитываем средний объем
            average_volume = sum(historical_volumes) / len(historical_volumes)
            volume_ratio = current_volume_usdt / average_volume if average_volume > 0 else 0
            
            logger.debug(f"{symbol}: Текущий объем {current_volume_usdt:.0f}, средний {average_volume:.0f}, коэффициент {volume_ratio:.2f}")
            
            if volume_ratio >= self.settings['volume_multiplier']:
                current_price = float(kline_data['close'])
                close_time = self._get_current_time()
                
                # Создаем данные свечи для алерта
                candle_data = {
                    'open': float(kline_data['open']),
                    'high': float(kline_data['high']),
                    'low': float(kline_data['low']),
                    'close': current_price,
                    'volume': float(kline_data['volume']),
                    'alert_level': current_price
                }
                
                # Анализируем имбаланс
                imbalance_data = None
                has_imbalance = False
                if self.settings.get('imbalance_enabled', False):
                    imbalance_data = await self._analyze_imbalance(symbol)
                    has_imbalance = imbalance_data is not None
                
                # Получаем снимок стакана, если включено
                order_book_snapshot = None
                if self.settings.get('orderbook_snapshot_on_alert', False):
                    order_book_snapshot = await self._get_order_book_snapshot(symbol)
                
                alert_data = {
                    'symbol': symbol,
                    'alert_type': AlertType.VOLUME_SPIKE.value,
                    'price': current_price,
                    'volume_ratio': round(volume_ratio, 2),
                    'current_volume_usdt': int(current_volume_usdt),
                    'average_volume_usdt': int(average_volume),
                    'timestamp': close_time,
                    'close_timestamp': close_time,
                    'is_closed': True,
                    'is_true_signal': True,  # Закрытая LONG свеча = истинный сигнал
                    'has_imbalance': has_imbalance,
                    'imbalance_data': imbalance_data,
                    'candle_data': candle_data,
                    'order_book_snapshot': order_book_snapshot,
                    'message': f"Объем превышен в {volume_ratio:.2f}x раз (истинный сигнал)"
                }
                
                # Обновляем кулдаун
                self.alert_cooldowns[symbol] = self._get_current_time()
                
                logger.info(f"Создан алерт по объему для {symbol}: {volume_ratio:.2f}x")
                return alert_data
            
            return None
            
        except Exception as e:
            logger.error(f"Ошибка проверки алерта по объему для {symbol}: {e}")
            return None

    async def _analyze_imbalance(self, symbol: str) -> Optional[Dict]:
        """Анализ имбаланса для символа"""
        try:
            # Получаем последние свечи для анализа
            candles = await self.db_manager.get_recent_candles(symbol, 20)
            
            if len(candles) < 15:
                return None
            
            # Проверяем Fair Value Gap
            if self.settings.get('fair_value_gap_enabled', True):
                fvg = self.imbalance_analyzer.analyze_fair_value_gap(candles)
                if fvg:
                    return fvg
            
            # Проверяем Order Block
            if self.settings.get('order_block_enabled', True):
                ob = self.imbalance_analyzer.analyze_order_block(candles)
                if ob:
                    return ob
            
            # Проверяем Breaker Block
            if self.settings.get('breaker_block_enabled', True):
                bb = self.imbalance_analyzer.analyze_breaker_block(candles)
                if bb:
                    return bb
            
            return None
            
        except Exception as e:
            logger.error(f"Ошибка анализа имбаланса для {symbol}: {e}")
            return None

    async def _get_order_book_snapshot(self, symbol: str) -> Optional[Dict]:
        """Получение снимка стакана заявок"""
        try:
            if not self.settings.get('orderbook_enabled', False):
                return None
            
            url = f"https://api.bybit.com/v5/market/orderbook"
            params = {
                'category': 'linear',
                'symbol': symbol,
                'limit': 25
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('retCode') == 0:
                            result = data['result']
                            return {
                                'bids': [[float(bid[0]), float(bid[1])] for bid in result.get('b', [])],
                                'asks': [[float(ask[0]), float(ask[1])] for ask in result.get('a', [])],
                                'timestamp': self._get_current_time().isoformat()
                            }
            
            return None
            
        except Exception as e:
            logger.error(f"Ошибка получения стакана для {symbol}: {e}")
            return None

    async def _check_consecutive_long_alert(self, symbol: str, kline_data: Dict) -> Optional[Dict]:
        """Проверка алерта по подряд идущим LONG свечам"""
        try:
            # Получаем последние свечи
            recent_candles = await self.db_manager.get_recent_candles(symbol, self.settings['consecutive_long_count'] + 5)
            
            if len(recent_candles) < self.settings['consecutive_long_count']:
                return None
            
            # Считаем последовательные LONG свечи с конца
            consecutive_count = 0
            for candle in reversed(recent_candles):
                if candle['is_long'] and candle['is_closed']:
                    consecutive_count += 1
                else:
                    break
            
            # Проверяем, достигнуто ли нужное количество
            if consecutive_count >= self.settings['consecutive_long_count']:
                close_time = self._get_current_time()
                current_price = float(kline_data['close'])
                
                # Создаем данные свечи
                candle_data = {
                    'open': float(kline_data['open']),
                    'high': float(kline_data['high']),
                    'low': float(kline_data['low']),
                    'close': current_price,
                    'volume': float(kline_data['volume'])
                }
                
                # Анализируем имбаланс
                imbalance_data = await self._analyze_imbalance(symbol)
                has_imbalance = imbalance_data is not None
                
                alert_data = {
                    'symbol': symbol,
                    'alert_type': AlertType.CONSECUTIVE_LONG.value,
                    'price': current_price,
                    'consecutive_count': consecutive_count,
                    'timestamp': close_time,
                    'close_timestamp': close_time,
                    'is_closed': True,
                    'has_imbalance': has_imbalance,
                    'imbalance_data': imbalance_data,
                    'candle_data': candle_data,
                    'message': f"{consecutive_count} подряд идущих LONG свечей (закрытых)"
                }
                
                logger.info(f"Алерт по последовательности для {symbol}: {consecutive_count} LONG свечей")
                return alert_data
            
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
            if consecutive_alert:
                recent_volume_alert = await self._check_recent_volume_alert(symbol, consecutive_alert['consecutive_count'])
                
                if volume_alert or recent_volume_alert:
                    candle_data = consecutive_alert.get('candle_data', {})
                    if volume_alert and volume_alert.get('candle_data'):
                        candle_data.update(volume_alert['candle_data'])
                    
                    # Проверяем имбаланс для приоритетного сигнала
                    has_imbalance = False
                    imbalance_data = None
                    if volume_alert and volume_alert.get('has_imbalance'):
                        has_imbalance = True
                        imbalance_data = volume_alert.get('imbalance_data')
                    elif consecutive_alert and consecutive_alert.get('has_imbalance'):
                        has_imbalance = True
                        imbalance_data = consecutive_alert.get('imbalance_data')
                    
                    priority_data = {
                        'symbol': symbol,
                        'alert_type': AlertType.PRIORITY.value,
                        'price': consecutive_alert['price'],
                        'consecutive_count': consecutive_alert['consecutive_count'],
                        'timestamp': consecutive_alert['timestamp'],
                        'close_timestamp': consecutive_alert['close_timestamp'],
                        'is_closed': True,
                        'has_imbalance': has_imbalance,
                        'imbalance_data': imbalance_data,
                        'candle_data': candle_data,
                        'message': f"Приоритетный сигнал: {consecutive_alert['consecutive_count']} LONG свечей + всплеск объема{' + имбаланс' if has_imbalance else ''}"
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

            # Отправляем в Telegram
            if self.telegram_bot:
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
        
        # Конвертируем datetime в строки
        for key in ['timestamp', 'close_timestamp']:
            if key in serialized and isinstance(serialized[key], datetime):
                serialized[key] = serialized[key].isoformat()
        
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
            # Очищаем кэши
            cutoff_time = self._get_current_time() - timedelta(minutes=5)
            
            # Очищаем кулдауны (старше часа)
            cooldown_cutoff = self._get_current_time() - timedelta(hours=1)
            for symbol in list(self.alert_cooldowns.keys()):
                if self.alert_cooldowns[symbol] < cooldown_cutoff:
                    del self.alert_cooldowns[symbol]
            
            logger.info("Очистка старых данных завершена")
            
        except Exception as e:
            logger.error(f"Ошибка очистки старых данных: {e}")