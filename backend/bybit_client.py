import asyncio
import json
import logging
import websockets
from typing import List, Dict, Optional, Set
import requests
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class BybitWebSocketClient:
    def __init__(self, trading_pairs: List[str], alert_manager, connection_manager):
        self.trading_pairs = set(trading_pairs)  # Используем set для быстрого поиска
        self.alert_manager = alert_manager
        self.connection_manager = connection_manager
        self.websocket = None
        self.is_running = False
        self.ping_task = None
        self.subscription_update_task = None
        self.last_message_time = None

        # Bybit WebSocket URLs
        self.ws_url = "wss://stream.bybit.com/v5/public/linear"
        self.rest_url = "https://api.bybit.com"

        # Настраиваемый интервал обновления
        self.update_interval = alert_manager.settings.get('update_interval_seconds', 1)

        # Статистика для отладки
        self.messages_received = 0
        self.last_stats_log = datetime.utcnow()

        # Кэш для отслеживания обработанных свечей
        self.processed_candles = {}  # symbol -> last_processed_timestamp

        # Отслеживание подписок
        self.subscribed_pairs = set()  # Пары, на которые мы подписаны
        self.subscription_pending = set()  # Пары, ожидающие подписки
        self.last_subscription_update = datetime.utcnow()

    async def start(self):
        """Запуск WebSocket соединения"""
        self.is_running = True

        # Проверяем и загружаем недостающие исторические данные
        await self.check_and_load_missing_data()

        # Запускаем задачу обновления подписок
        self.subscription_update_task = asyncio.create_task(self._subscription_updater())

        # Затем подключаемся к WebSocket для real-time данных
        while self.is_running:
            try:
                await self.connect_websocket()
            except Exception as e:
                logger.error(f"WebSocket ошибка: {e}")
                if self.is_running:
                    logger.info("Переподключение через 5 секунд...")
                    await asyncio.sleep(5)

    async def stop(self):
        """Остановка WebSocket соединения"""
        self.is_running = False
        if self.ping_task:
            self.ping_task.cancel()
        if self.subscription_update_task:
            self.subscription_update_task.cancel()
        if self.websocket:
            await self.websocket.close()

    async def _subscription_updater(self):
        """Периодическое обновление подписок на новые пары"""
        while self.is_running:
            try:
                await asyncio.sleep(60)  # Проверяем каждую минуту
                
                if not self.is_running:
                    break
                
                # Получаем актуальный список пар из базы данных
                current_pairs = set(await self.alert_manager.db_manager.get_watchlist())
                
                # Находим новые пары
                new_pairs = current_pairs - self.trading_pairs
                
                # Находим удаленные пары
                removed_pairs = self.trading_pairs - current_pairs
                
                if new_pairs or removed_pairs:
                    logger.info(f"Обновление подписок: +{len(new_pairs)} новых пар, -{len(removed_pairs)} удаленных пар")
                    
                    # Обновляем локальный список
                    self.trading_pairs = current_pairs.copy()
                    
                    # Если WebSocket активен, обновляем подписки
                    if self.websocket and self.websocket.open:
                        await self._update_subscriptions(new_pairs, removed_pairs)
                    
                    # Загружаем данные для новых пар
                    if new_pairs:
                        await self._load_data_for_new_pairs(new_pairs)
                
                self.last_subscription_update = datetime.utcnow()
                
            except Exception as e:
                logger.error(f"Ошибка обновления подписок: {e}")
                await asyncio.sleep(30)  # При ошибке ждем 30 секунд

    async def _update_subscriptions(self, new_pairs: Set[str], removed_pairs: Set[str]):
        """Обновление подписок WebSocket"""
        try:
            # Отписываемся от удаленных пар
            if removed_pairs:
                unsubscribe_message = {
                    "op": "unsubscribe",
                    "args": [f"kline.1.{pair}" for pair in removed_pairs]
                }
                await self.websocket.send(json.dumps(unsubscribe_message))
                logger.info(f"Отписка от {len(removed_pairs)} пар: {list(removed_pairs)[:5]}...")
                
                # Обновляем отслеживание подписок
                self.subscribed_pairs -= removed_pairs

            # Подписываемся на новые пары
            if new_pairs:
                # Разбиваем на группы по 50 пар
                batch_size = 50
                new_pairs_list = list(new_pairs)
                
                for i in range(0, len(new_pairs_list), batch_size):
                    batch = new_pairs_list[i:i + batch_size]
                    subscribe_message = {
                        "op": "subscribe",
                        "args": [f"kline.1.{pair}" for pair in batch]
                    }
                    
                    await self.websocket.send(json.dumps(subscribe_message))
                    logger.info(f"Подписка на новые пары (пакет {i // batch_size + 1}): {len(batch)} пар")
                    
                    # Добавляем в ожидающие подписки
                    self.subscription_pending.update(batch)
                    
                    # Небольшая задержка между пакетами
                    if i + batch_size < len(new_pairs_list):
                        await asyncio.sleep(0.5)

            # Отправляем обновленную статистику
            await self.connection_manager.broadcast_json({
                "type": "subscription_updated",
                "total_pairs": len(self.trading_pairs),
                "subscribed_pairs": len(self.subscribed_pairs),
                "new_pairs": list(new_pairs),
                "removed_pairs": list(removed_pairs),
                "timestamp": datetime.utcnow().isoformat()
            })

        except Exception as e:
            logger.error(f"Ошибка обновления подписок WebSocket: {e}")

    async def _load_data_for_new_pairs(self, new_pairs: Set[str]):
        """Загрузка исторических данных для новых пар"""
        try:
            retention_hours = self.alert_manager.settings.get('data_retention_hours', 2)
            analysis_hours = self.alert_manager.settings.get('analysis_hours', 1)
            total_hours_needed = retention_hours + analysis_hours + 1

            logger.info(f"Загрузка данных для {len(new_pairs)} новых пар...")
            
            for symbol in new_pairs:
                try:
                    await self.load_symbol_data(symbol, total_hours_needed)
                    await asyncio.sleep(0.1)  # Небольшая задержка между запросами
                except Exception as e:
                    logger.error(f"Ошибка загрузки данных для новой пары {symbol}: {e}")
                    continue
            
            logger.info(f"Загрузка данных для новых пар завершена")

        except Exception as e:
            logger.error(f"Ошибка загрузки данных для новых пар: {e}")

    async def check_and_load_missing_data(self):
        """Проверка и загрузка недостающих данных для всех пар"""
        logger.info("Проверка существующих данных...")

        # Получаем актуальный список пар из базы данных
        current_pairs = await self.alert_manager.db_manager.get_watchlist()
        self.trading_pairs = set(current_pairs)

        # Получаем период хранения из настроек
        retention_hours = self.alert_manager.settings.get('data_retention_hours', 2)
        analysis_hours = self.alert_manager.settings.get('analysis_hours', 1)
        total_hours_needed = retention_hours + analysis_hours + 1  # +1 час буфера

        symbols_to_load = []
        symbols_with_data = []

        for symbol in self.trading_pairs:
            try:
                # Проверяем целостность данных для символа
                integrity_info = await self.alert_manager.db_manager.check_data_integrity(
                    symbol, total_hours_needed
                )

                # Если данных мало или целостность низкая - добавляем в список для загрузки
                if integrity_info['integrity_percentage'] < 80 or integrity_info['total_existing'] < 60:
                    symbols_to_load.append(symbol)
                    logger.info(
                        f"{symbol}: Требуется загрузка данных ({integrity_info['total_existing']}/{integrity_info['total_expected']} свечей, {integrity_info['integrity_percentage']:.1f}%)")
                else:
                    symbols_with_data.append(symbol)
                    logger.debug(
                        f"{symbol}: Данные актуальны ({integrity_info['total_existing']}/{integrity_info['total_expected']} свечей, {integrity_info['integrity_percentage']:.1f}%)")

            except Exception as e:
                logger.error(f"Ошибка проверки данных для {symbol}: {e}")
                symbols_to_load.append(symbol)  # На всякий случай добавляем в загрузку

        logger.info(
            f"Найдено {len(symbols_with_data)} символов с актуальными данными, {len(symbols_to_load)} требуют загрузки")

        # Загружаем данные только для символов, которым это нужно
        if symbols_to_load:
            logger.info(f"Загрузка данных для {len(symbols_to_load)} символов...")
            for symbol in symbols_to_load:
                try:
                    await self.load_symbol_data(symbol, total_hours_needed)
                    await asyncio.sleep(0.1)  # Небольшая задержка между запросами
                except Exception as e:
                    logger.error(f"Ошибка загрузки данных для {symbol}: {e}")
                    continue
            logger.info("Загрузка недостающих данных завершена")
        else:
            logger.info("Все данные актуальны, загрузка не требуется")

    async def load_symbol_data(self, symbol: str, hours: int):
        """Загрузка данных для одного символа"""
        try:
            # Получаем информацию о недостающих периодах
            integrity_info = await self.alert_manager.db_manager.check_data_integrity(symbol, hours)

            if integrity_info['missing_count'] == 0:
                logger.debug(f"{symbol}: Все данные уже загружены")
                return

            # Определяем период для загрузки
            end_time_ms = int(datetime.utcnow().timestamp() * 1000)
            start_time_ms = end_time_ms - (hours * 60 * 60 * 1000)

            # Загружаем данные с биржи
            await self._load_full_period(symbol, start_time_ms, end_time_ms)

        except Exception as e:
            logger.error(f"Ошибка загрузки данных для {symbol}: {e}")

    async def _load_full_period(self, symbol: str, start_time_ms: int, end_time_ms: int):
        """Загрузка полного периода данных"""
        try:
            hours = (end_time_ms - start_time_ms) / (60 * 60 * 1000)
            limit = min(int(hours * 60) + 60, 1000)

            url = f"{self.rest_url}/v5/market/kline"
            params = {
                'category': 'linear',
                'symbol': symbol,
                'interval': '1',
                'start': start_time_ms,
                'end': end_time_ms,
                'limit': limit
            }

            response = requests.get(url, params=params, timeout=10)
            data = response.json()

            if data.get('retCode') == 0:
                klines = data['result']['list']
                klines.reverse()  # Bybit возвращает данные в обратном порядке

                saved_count = 0
                skipped_count = 0

                for kline in klines:
                    # Биржа передает время в миллисекундах
                    kline_timestamp_ms = int(kline[0])

                    # Для исторических данных округляем до минут
                    rounded_timestamp = (kline_timestamp_ms // 60000) * 60000

                    kline_data = {
                        'start': rounded_timestamp,
                        'end': rounded_timestamp + 60000,
                        'open': kline[1],
                        'high': kline[2],
                        'low': kline[3],
                        'close': kline[4],
                        'volume': kline[5],
                        'confirm': True  # Исторические данные всегда закрыты
                    }

                    # Проверяем, есть ли уже эта свеча в базе
                    existing = await self._check_candle_exists(symbol, rounded_timestamp)
                    if not existing:
                        # Сохраняем как закрытую свечу
                        await self.alert_manager.db_manager.save_kline_data(symbol, kline_data, is_closed=True)
                        saved_count += 1
                    else:
                        skipped_count += 1

                logger.info(f"{symbol}: Загружено {saved_count} новых свечей, пропущено {skipped_count} существующих")
            else:
                logger.error(f"Ошибка API при загрузке данных для {symbol}: {data.get('retMsg')}")

        except Exception as e:
            logger.error(f"Ошибка загрузки полного периода для {symbol}: {e}")

    async def _check_candle_exists(self, symbol: str, timestamp_ms: int) -> bool:
        """Проверка существования свечи в базе данных"""
        try:
            cursor = self.alert_manager.db_manager.connection.cursor()
            cursor.execute("""
                SELECT 1 FROM kline_data 
                WHERE symbol = %s AND open_time_ms = %s
                LIMIT 1
            """, (symbol, timestamp_ms))

            result = cursor.fetchone()
            cursor.close()

            return result is not None

        except Exception as e:
            logger.error(f"Ошибка проверки существования свечи: {e}")
            return False

    async def connect_websocket(self):
        """Подключение к WebSocket с подпиской на ВСЕ торговые пары"""
        try:
            logger.info(f"Подключение к WebSocket: {self.ws_url}")
            logger.info(
                f"Подписка на {len(self.trading_pairs)} торговых пар: {list(self.trading_pairs)[:10]}...")

            async with websockets.connect(
                    self.ws_url,
                    ping_interval=30,
                    ping_timeout=10,
                    close_timeout=10
            ) as websocket:
                self.websocket = websocket
                self.last_message_time = datetime.utcnow()

                # Сбрасываем отслеживание подписок
                self.subscribed_pairs.clear()
                self.subscription_pending.clear()

                # Подписываемся на kline данные для ВСЕХ торговых пар
                # Разбиваем на группы по 50 пар для избежания ограничений WebSocket
                batch_size = 50
                trading_pairs_list = list(self.trading_pairs)
                
                for i in range(0, len(trading_pairs_list), batch_size):
                    batch = trading_pairs_list[i:i + batch_size]
                    subscribe_message = {
                        "op": "subscribe",
                        "args": [f"kline.1.{pair}" for pair in batch]
                    }

                    await websocket.send(json.dumps(subscribe_message))
                    logger.info(f"Подписка на пакет {i // batch_size + 1}: {len(batch)} пар")

                    # Добавляем в ожидающие подписки
                    self.subscription_pending.update(batch)

                    # Небольшая задержка между пакетами
                    if i + batch_size < len(trading_pairs_list):
                        await asyncio.sleep(0.5)

                logger.info(f"Подписка завершена на {len(self.trading_pairs)} торговых пар")

                # Отправляем статус подключения
                await self.connection_manager.broadcast_json({
                    "type": "connection_status",
                    "status": "connected",
                    "pairs_count": len(self.trading_pairs),
                    "subscribed_count": len(self.subscribed_pairs),
                    "pending_count": len(self.subscription_pending),
                    "update_interval": self.update_interval,
                    "timestamp": datetime.utcnow().isoformat()
                })

                # Запускаем задачу мониторинга соединения
                self.ping_task = asyncio.create_task(self._monitor_connection())

                # Обработка входящих сообщений
                async for message in websocket:
                    if not self.is_running:
                        break

                    try:
                        self.last_message_time = datetime.utcnow()
                        self.messages_received += 1

                        data = json.loads(message)
                        await self.handle_message(data)

                        # Логируем статистику каждые 5 минут
                        if (datetime.utcnow() - self.last_stats_log).total_seconds() > 300:
                            logger.info(f"WebSocket статистика: {self.messages_received} сообщений получено, подписано на {len(self.subscribed_pairs)} пар")
                            self.last_stats_log = datetime.utcnow()

                    except Exception as e:
                        logger.error(f"Ошибка обработки сообщения: {e}")

        except Exception as e:
            logger.error(f"Ошибка WebSocket соединения: {e}")
            raise
        finally:
            if self.ping_task:
                self.ping_task.cancel()

    async def _monitor_connection(self):
        """Мониторинг состояния WebSocket соединения"""
        while self.is_running:
            try:
                await asyncio.sleep(60)

                if self.last_message_time:
                    time_since_last_message = (datetime.utcnow() - self.last_message_time).total_seconds()

                    if time_since_last_message > 120:
                        logger.warning(f"Нет сообщений от WebSocket уже {time_since_last_message:.0f} секунд")

                        await self.connection_manager.broadcast_json({
                            "type": "connection_status",
                            "status": "disconnected",
                            "reason": "No messages received",
                            "timestamp": datetime.utcnow().isoformat()
                        })
                        break

            except Exception as e:
                logger.error(f"Ошибка мониторинга соединения: {e}")

    async def handle_message(self, data: Dict):
        """Обработка входящих WebSocket сообщений"""
        try:
            # Обрабатываем системные сообщения
            if 'success' in data:
                if data['success']:
                    logger.debug("Успешная подписка на WebSocket пакет")
                    # Перемещаем пары из ожидающих в подписанные
                    # (точное определение каких пар требует дополнительной логики)
                else:
                    logger.error(f"Ошибка подписки WebSocket: {data}")
                return

            if 'op' in data:
                logger.debug(f"Системное сообщение WebSocket: {data}")
                return

            # Обрабатываем данные свечей
            if data.get('topic', '').startswith('kline.1.'):
                kline_data = data['data'][0]
                symbol = data['topic'].split('.')[-1]

                # Проверяем, что символ в нашем списке
                if symbol not in self.trading_pairs:
                    logger.debug(f"Получены данные для символа {symbol}, которого нет в watchlist")
                    return

                # Добавляем символ в подписанные (если получили данные, значит подписка работает)
                if symbol in self.subscription_pending:
                    self.subscription_pending.remove(symbol)
                self.subscribed_pairs.add(symbol)

                # Биржа передает время в миллисекундах
                start_time_ms = int(kline_data['start'])
                end_time_ms = int(kline_data['end'])
                is_closed = kline_data.get('confirm', False)

                # Для потоковых данных оставляем миллисекунды, но для закрытых свечей - округляем
                if is_closed:
                    # Закрытые свечи с округлением до минут
                    start_time_ms = (start_time_ms // 60000) * 60000
                    end_time_ms = (end_time_ms // 60000) * 60000

                # Преобразуем данные в нужный формат
                formatted_data = {
                    'start': start_time_ms,
                    'end': end_time_ms,
                    'open': kline_data['open'],
                    'high': kline_data['high'],
                    'low': kline_data['low'],
                    'close': kline_data['close'],
                    'volume': kline_data['volume'],
                    'confirm': is_closed
                }

                # Логируем временные метки для закрытых свечей
                if is_closed:
                    logger.debug(f"WebSocket kline_update: {symbol} закрытая свеча, timestamp={start_time_ms}")

                # Простая проверка на дублирование для закрытых свечей
                if is_closed:
                    last_processed = self.processed_candles.get(symbol, 0)
                    if start_time_ms > last_processed:
                        # Обрабатываем через менеджер алертов
                        alerts = await self.alert_manager.process_kline_data(symbol, formatted_data)

                        # Помечаем свечу как обработанную
                        self.processed_candles[symbol] = start_time_ms

                        # Загружаем новые данные для поддержания диапазона
                        await self._maintain_data_range(symbol)

                        logger.debug(f"Обработана закрытая свеча {symbol} в {start_time_ms}")

                # Сохраняем данные в базу (формирующиеся или закрытые)
                await self.alert_manager.db_manager.save_kline_data(symbol, formatted_data, is_closed)

                # Отправляем обновление данных клиентам (потоковые данные)
                stream_item = {
                    "type": "kline_update",
                    "symbol": symbol,
                    "data": formatted_data,
                    "timestamp": datetime.utcnow().isoformat(),
                    "is_closed": is_closed,
                    "server_timestamp": self.alert_manager._get_current_timestamp_ms() if hasattr(self.alert_manager,
                                                                                                  '_get_current_timestamp_ms') else int(
                        datetime.utcnow().timestamp() * 1000)
                }

                await self.connection_manager.broadcast_json(stream_item)

        except Exception as e:
            logger.error(f"Ошибка обработки kline данных: {e}")

    async def _maintain_data_range(self, symbol: str):
        """Поддержание диапазона данных в заданных пределах"""
        try:
            # Получаем настройки диапазона
            retention_hours = self.alert_manager.settings.get('data_retention_hours', 2)
            analysis_hours = self.alert_manager.settings.get('analysis_hours', 1)
            total_hours_needed = retention_hours + analysis_hours + 1

            # Очищаем старые данные
            await self.alert_manager.db_manager.cleanup_old_candles(symbol, total_hours_needed)

            # Проверяем, нужно ли загрузить новые данные
            integrity_info = await self.alert_manager.db_manager.check_data_integrity(symbol, total_hours_needed)
            
            # Если целостность низкая, загружаем недостающие данные
            if integrity_info['integrity_percentage'] < 90 and integrity_info['missing_count'] > 5:
                logger.info(f"Загрузка недостающих данных для {symbol}: {integrity_info['missing_count']} свечей")
                await self.load_symbol_data(symbol, total_hours_needed)

        except Exception as e:
            logger.error(f"Ошибка поддержания диапазона данных для {symbol}: {e}")

    def get_subscription_stats(self) -> Dict:
        """Получить статистику подписок"""
        return {
            'total_pairs': len(self.trading_pairs),
            'subscribed_pairs': len(self.subscribed_pairs),
            'pending_pairs': len(self.subscription_pending),
            'last_update': self.last_subscription_update.isoformat() if self.last_subscription_update else None,
            'subscription_rate': len(self.subscribed_pairs) / len(self.trading_pairs) * 100 if self.trading_pairs else 0
        }