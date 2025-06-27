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
    def __init__(self, db_manager, telegram_bot=None, connection_manager=None):
        self.db_manager = db_manager
        self.telegram_bot = telegram_bot
        self.connection_manager = connection_manager
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

        # Кэш для отслеживания состояния свечей и алертов
        self.candle_cache = {}  # symbol -> list of recent candles
        self.volume_alerts_cache = {}  # symbol -> {timestamp, alert_id, alert_level}
        self.consecutive_counters = {}  # symbol -> consecutive long count
        self.consecutive_alert_ids = {}  # symbol -> ID текущего алерта по последовательности
        self.priority_signals = {}  # symbol -> priority signal data
        self.alert_cooldowns = {}  # symbol -> last alert timestamp

        logger.info("AlertManager инициализирован с анализом имбаланса")

    async def _check_consecutive_long_alert(self, symbol: str, kline_data: Dict) -> Optional[Dict]:
        """Проверка алерта по подряд идущим LONG свечам - ТОЛЬКО ПО ЗАКРЫТЫМ СВЕЧАМ"""
        try:
            # Проверяем только закрытые свечи
            is_long = float(kline_data['close']) > float(kline_data['open'])

            # Инициализируем счетчик и ID алерта, если их нет
            if symbol not in self.consecutive_counters:
                self.consecutive_counters[symbol] = 0
                self.consecutive_alert_ids[symbol] = None

            # Время закрытия свечи
            timestamp = int(kline_data['start'])
            close_time = datetime.fromtimestamp((timestamp + 60000) / 1000)

            # Данные свечи
            candle_data = {
                'open': float(kline_data['open']),
                'high': float(kline_data['high']),
                'low': float(kline_data['low']),
                'close': float(kline_data['close']),
                'volume': float(kline_data['volume'])
            }

            # Анализируем имбаланс
            imbalance_data = None
            has_imbalance = False
            if self.settings.get('imbalance_enabled', False):
                imbalance_data = await self._analyze_imbalance(symbol)
                has_imbalance = imbalance_data is not None

            if is_long:
                # Увеличиваем счетчик LONG свечей
                self.consecutive_counters[symbol] += 1

                # Проверяем, достигнуто ли нужное количество свечей
                if self.consecutive_counters[symbol] >= self.settings['consecutive_long_count']:
                    alert_data = {
                        'symbol': symbol,
                        'alert_type': AlertType.CONSECUTIVE_LONG.value,
                        'price': float(kline_data['close']),
                        'consecutive_count': self.consecutive_counters[symbol],
                        'timestamp': close_time,
                        'close_timestamp': close_time,
                        'is_closed': True,
                        'has_imbalance': has_imbalance,
                        'imbalance_data': imbalance_data,
                        'candle_data': candle_data,
                        'message': f"{self.consecutive_counters[symbol]} подряд идущих LONG свечей (закрытых)"
                    }

                    # Если уже есть активный алерт, обновляем его
                    if self.consecutive_alert_ids[symbol] is not None:
                        alert_data['id'] = self.consecutive_alert_ids[symbol]
                        await self.db_manager.update_alert(self.consecutive_alert_ids[symbol], alert_data)
                    else:
                        # Создаем новый алерт
                        alert_id = await self.db_manager.save_alert(alert_data)
                        alert_data['id'] = alert_id
                        self.consecutive_alert_ids[symbol] = alert_id

                    # Отправляем обновление в интерфейс
                    if self.connection_manager:
                        await self.connection_manager.broadcast_json({
                            'type': 'consecutive_update',
                            'symbol': symbol,
                            'count': self.consecutive_counters[symbol],
                            'alert_id': alert_data['id']
                        })

                    return alert_data
            else:
                # При появлении SHORT свечи сбрасываем счетчик и закрываем существующий алерт
                if self.consecutive_counters[symbol] >= self.settings['consecutive_long_count'] and self.consecutive_alert_ids[symbol] is not None:
                    # Закрываем существующий алерт
                    await self.db_manager.update_alert(self.consecutive_alert_ids[symbol], {
                        'id': self.consecutive_alert_ids[symbol],
                        'symbol': symbol,
                        'alert_type': AlertType.CONSECUTIVE_LONG.value,
                        'price': float(kline_data['close']),
                        'consecutive_count': self.consecutive_counters[symbol],
                        'timestamp': close_time,
                        'close_timestamp': close_time,
                        'is_closed': True,
                        'has_imbalance': has_imbalance,
                        'imbalance_data': imbalance_data,
                        'candle_data': candle_data,
                        'message': "Последовательность LONG свечей прервана SHORT свечей"
                    })

                # Сбрасываем счетчик и ID алерта
                self.consecutive_counters[symbol] = 0
                self.consecutive_alert_ids[symbol] = None

            return None

        except Exception as e:
            logger.error(f"Ошибка проверки последовательных LONG свечей для {symbol}: {e}")
            return None

    async def _send_alert(self, alert_data: Dict):
        """Отправка алерта"""
        try:
            # Если у алерта есть ID, обновляем существующий, иначе создаем новый
            if 'id' in alert_data:
                await self.db_manager.update_alert(alert_data['id'], alert_data)
            else:
                alert_id = await self.db_manager.save_alert(alert_data)
                alert_data['id'] = alert_id

            # Отправляем в WebSocket
            if self.connection_manager:
                event_type = 'alert_updated' if 'id' in alert_data else 'new_alert'
                await self.connection_manager.broadcast_json({
                    'type': event_type,
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