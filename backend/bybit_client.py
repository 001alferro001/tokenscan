import asyncio
import json
import logging
import websockets
from typing import List, Dict, Optional
import requests
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class BybitWebSocketClient:
    def __init__(self, trading_pairs: List[str], alert_manager, connection_manager):
        self.trading_pairs = trading_pairs
        self.alert_manager = alert_manager
        self.connection_manager = connection_manager
        self.websocket = None
        self.is_running = False
        self.ping_task = None
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
        
        # Отслеживание подписанных пар
        self.subscribed_pairs = set()
        self.subscription_confirmed = set()  # Пары с подтвержденной подпиской
        self.failed_subscriptions = set()

    async def start(self):
        """Запуск WebSocket соединения"""
        self.is_running = True
        
        # Проверяем и загружаем недостающие исторические данные
        await self.check_and_load_missing_data()
        
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
        if self.websocket:
            await self.websocket.close()

    async def check_and_load_missing_data(self):
        """Проверка и загрузка только недостающих данных"""
        logger.info("Проверка существующих данных...")
        
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
                    logger.info(f"{symbol}: Требуется загрузка данных ({integrity_info['total_existing']}/{integrity_info['total_expected']} свечей, {integrity_info['integrity_percentage']:.1f}%)")
                else:
                    symbols_with_data.append(symbol)
                    logger.debug(f"{symbol}: Данные актуальны ({integrity_info['total_existing']}/{integrity_info['total_expected']} свечей, {integrity_info['integrity_percentage']:.1f}%)")
                        
            except Exception as e:
                logger.error(f"Ошибка проверки данных для {symbol}: {e}")
                symbols_to_load.append(symbol)  # На всякий случай добавляем в загрузку
        
        logger.info(f"Найдено {len(symbols_with_data)} символов с актуальными данными, {len(symbols_to_load)} требуют загрузки")
        
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
        """Загрузка данных для одного символа с UNIX временем"""
        try:
            # Получаем информацию о недостающих периодах
            integrity_info = await self.alert_manager.db_manager.check_data_integrity(symbol, hours)
            
            if integrity_info['missing_count'] == 0:
                logger.debug(f"{symbol}: Все данные уже загружены")
                return
            
            # Определяем период для загрузки в UNIX формате
            end_time_unix = int(datetime.utcnow().timestamp() * 1000)
            start_time_unix = end_time_unix - (hours * 60 * 60 * 1000)
            
            # Загружаем данные с биржи
            await self._load_full_period(symbol, start_time_unix, end_time_unix)
                
        except Exception as e:
            logger.error(f"Ошибка загрузки данных для {symbol}: {e}")

    async def _load_full_period(self, symbol: str, start_time_unix: int, end_time_unix: int):
        """Загрузка полного периода данных с UNIX временем"""
        try:
            hours = (end_time_unix - start_time_unix) / (60 * 60 * 1000)
            limit = min(int(hours * 60) + 60, 1000)
            
            url = f"{self.rest_url}/v5/market/kline"
            params = {
                'category': 'linear',
                'symbol': symbol,
                'interval': '1',
                'start': start_time_unix,
                'end': end_time_unix,
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
                    # Биржа передает UNIX время в миллисекундах
                    kline_timestamp_unix = int(kline[0])
                    
                    # Для исторических данных округляем до минут с нулями (1687958700000)
                    rounded_timestamp = (kline_timestamp_unix // 60000) * 60000
                    
                    kline_data = {
                        'start': rounded_timestamp,  # Округленное время с нулями
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

    async def _check_candle_exists(self, symbol: str, timestamp_unix: int) -> bool:
        """Проверка существования свечи в базе данных по UNIX времени"""
        try:
            cursor = self.alert_manager.db_manager.connection.cursor()
            cursor.execute("""
                SELECT 1 FROM kline_data 
                WHERE symbol = %s AND open_time_unix = %s
                LIMIT 1
            """, (symbol, timestamp_unix))
            
            result = cursor.fetchone()
            cursor.close()
            
            return result is not None
            
        except Exception as e:
            logger.error(f"Ошибка проверки существования свечи: {e}")
            return False

    async def connect_websocket(self):
        """Подключение к WebSocket с улучшенной подпиской на ВСЕ торговые пары"""
        try:
            logger.info(f"🔗 Подключение к WebSocket: {self.ws_url}")
            logger.info(f"📊 Всего торговых пар для подписки: {len(self.trading_pairs)}")
            
            # Очищаем списки подписанных пар
            self.subscribed_pairs.clear()
            self.subscription_confirmed.clear()
            self.failed_subscriptions.clear()
            
            async with websockets.connect(
                self.ws_url,
                ping_interval=30,
                ping_timeout=10,
                close_timeout=10
            ) as websocket:
                self.websocket = websocket
                self.last_message_time = datetime.utcnow()
                
                # УЛУЧШЕННАЯ СТРАТЕГИЯ ПОДПИСКИ
                await self._subscribe_to_all_pairs(websocket)
                
                # Отправляем статус подключения с детальной информацией
                await self.connection_manager.broadcast_json({
                    "type": "connection_status",
                    "status": "connected",
                    "pairs_count": len(self.trading_pairs),
                    "subscribed_count": len(self.subscribed_pairs),
                    "confirmed_count": len(self.subscription_confirmed),
                    "failed_count": len(self.failed_subscriptions),
                    "subscribed_pairs": sorted(list(self.subscribed_pairs)),
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
                            logger.info(f"📊 WebSocket статистика: {self.messages_received} сообщений, подписано пар: {len(self.subscription_confirmed)}/{len(self.trading_pairs)}")
                            self.last_stats_log = datetime.utcnow()
                            
                    except Exception as e:
                        logger.error(f"Ошибка обработки сообщения: {e}")
                        
        except Exception as e:
            logger.error(f"Ошибка WebSocket соединения: {e}")
            raise
        finally:
            if self.ping_task:
                self.ping_task.cancel()

    async def _subscribe_to_all_pairs(self, websocket):
        """Улучшенная подписка на все торговые пары с проверкой подтверждений"""
        # Стратегия 1: Маленькие пакеты с подтверждением
        batch_size = 25  # Уменьшаем размер пакета для надежности
        total_subscribed = 0
        failed_subscriptions = 0
        
        logger.info(f"🚀 Начинаем подписку на {len(self.trading_pairs)} пар пакетами по {batch_size}")
        
        for i in range(0, len(self.trading_pairs), batch_size):
            batch = self.trading_pairs[i:i + batch_size]
            batch_number = i // batch_size + 1
            
            try:
                # Формируем сообщение подписки
                subscribe_message = {
                    "op": "subscribe",
                    "args": [f"kline.1.{pair}" for pair in batch]
                }
                
                logger.info(f"📤 Отправка пакета {batch_number}/{(len(self.trading_pairs) + batch_size - 1) // batch_size}: {len(batch)} пар")
                logger.debug(f"Пары в пакете {batch_number}: {batch}")
                
                # Отправляем подписку
                await websocket.send(json.dumps(subscribe_message))
                
                # Добавляем пары в список отправленных
                for pair in batch:
                    self.subscribed_pairs.add(pair)
                
                total_subscribed += len(batch)
                
                # Ждем между пакетами для стабильности
                await asyncio.sleep(2.0)  # Увеличиваем задержку
                
                logger.info(f"✅ Пакет {batch_number} отправлен. Отправлено: {total_subscribed}/{len(self.trading_pairs)}")
                
            except Exception as e:
                logger.error(f"❌ Ошибка подписки на пакет {batch_number}: {e}")
                failed_subscriptions += len(batch)
                for pair in batch:
                    self.failed_subscriptions.add(pair)
                continue
        
        logger.info(f"🎯 Подписка завершена! Отправлено: {total_subscribed}, Ошибок: {failed_subscriptions}")
        
        # Ждем немного для получения подтверждений
        await asyncio.sleep(5.0)
        
        # Проверяем, какие подписки подтвердились
        confirmed_count = len(self.subscription_confirmed)
        logger.info(f"📋 Подтверждено подписок: {confirmed_count}/{total_subscribed}")
        
        # Если подтвердилось мало подписок, пробуем альтернативную стратегию
        if confirmed_count < total_subscribed * 0.5:  # Менее 50% подтвердилось
            logger.warning(f"⚠️ Подтвердилось только {confirmed_count} из {total_subscribed} подписок. Пробуем индивидуальную подписку...")
            await self._subscribe_individually(websocket)

    async def _subscribe_individually(self, websocket):
        """Индивидуальная подписка на каждую пару отдельно"""
        logger.info("🔄 Начинаем индивидуальную подписку на неподтвержденные пары")
        
        # Определяем пары, которые не подтвердились
        unconfirmed_pairs = self.subscribed_pairs - self.subscription_confirmed
        
        logger.info(f"📝 Неподтвержденных пар: {len(unconfirmed_pairs)}")
        
        individual_success = 0
        individual_failed = 0
        
        for pair in unconfirmed_pairs:
            try:
                subscribe_message = {
                    "op": "subscribe",
                    "args": [f"kline.1.{pair}"]
                }
                
                await websocket.send(json.dumps(subscribe_message))
                await asyncio.sleep(0.5)  # Небольшая задержка между индивидуальными подписками
                
                individual_success += 1
                logger.debug(f"📤 Индивидуальная подписка на {pair}")
                
            except Exception as e:
                logger.error(f"❌ Ошибка индивидуальной подписки на {pair}: {e}")
                individual_failed += 1
                self.failed_subscriptions.add(pair)
        
        logger.info(f"🎯 Индивидуальная подписка завершена: успешно {individual_success}, ошибок {individual_failed}")

    async def _monitor_connection(self):
        """Мониторинг состояния WebSocket соединения"""
        while self.is_running:
            try:
                await asyncio.sleep(60)
                
                if self.last_message_time:
                    time_since_last_message = (datetime.utcnow() - self.last_message_time).total_seconds()
                    
                    if time_since_last_message > 120:
                        logger.warning(f"⚠️ Нет сообщений от WebSocket уже {time_since_last_message:.0f} секунд")
                        
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
        """Обработка входящих WebSocket сообщений с UNIX временем"""
        try:
            # Обрабатываем системные сообщения
            if 'success' in data:
                if data['success']:
                    logger.debug("✅ Успешная подписка на WebSocket пакет")
                    
                    # Если есть информация о подписке, добавляем в подтвержденные
                    if 'request' in data and 'args' in data['request']:
                        for arg in data['request']['args']:
                            if arg.startswith('kline.1.'):
                                pair = arg.replace('kline.1.', '')
                                self.subscription_confirmed.add(pair)
                                logger.debug(f"✅ Подтверждена подписка на {pair}")
                else:
                    logger.error(f"❌ Ошибка подписки WebSocket: {data}")
                return
                
            if 'op' in data:
                logger.debug(f"🔧 Системное сообщение WebSocket: {data}")
                return
            
            # Обрабатываем данные свечей
            if data.get('topic', '').startswith('kline.1.'):
                kline_data = data['data'][0]
                symbol = data['topic'].split('.')[-1]
                
                # Подтверждаем получение данных для этой пары
                if symbol not in self.subscription_confirmed:
                    self.subscription_confirmed.add(symbol)
                    logger.debug(f"✅ Получены данные от {symbol}, подписка подтверждена")
                
                # КРИТИЧЕСКИ ВАЖНО: Проверяем, что символ в нашем списке торговых пар
                if symbol not in self.trading_pairs:
                    logger.warning(f"⚠️ Символ {symbol} не в watchlist")
                    return
                
                # Биржа передает UNIX время в миллисекундах
                start_time_unix = int(kline_data['start'])
                end_time_unix = int(kline_data['end'])
                is_closed = kline_data.get('confirm', False)
                
                # Для потоковых данных оставляем миллисекунды, но для закрытых свечей - округляем
                if is_closed:
                    # Закрытые свечи с нулями в конце (1687958700000)
                    start_time_unix = (start_time_unix // 60000) * 60000
                    end_time_unix = (end_time_unix // 60000) * 60000
                
                # Преобразуем данные в нужный формат
                formatted_data = {
                    'start': start_time_unix,
                    'end': end_time_unix,
                    'open': kline_data['open'],
                    'high': kline_data['high'],
                    'low': kline_data['low'],
                    'close': kline_data['close'],
                    'volume': kline_data['volume'],
                    'confirm': is_closed
                }
                
                # Логируем получение данных для отладки (только для первых 10 пар)
                if symbol in sorted(list(self.subscription_confirmed))[:10]:
                    logger.debug(f"📊 Данные от {symbol}: закрыта={is_closed}, время={start_time_unix}")
                
                # Простая проверка на дублирование для закрытых свечей
                if is_closed:
                    last_processed = self.processed_candles.get(symbol, 0)
                    if start_time_unix > last_processed:
                        # Обрабатываем через менеджер алертов
                        alerts = await self.alert_manager.process_kline_data(symbol, formatted_data)
                        
                        # Помечаем свечу как обработанную
                        self.processed_candles[symbol] = start_time_unix
                        
                        logger.debug(f"✅ Обработана закрытая свеча {symbol} в {start_time_unix}")
                
                # Сохраняем данные в базу (формирующиеся или закрытые)
                await self.alert_manager.db_manager.save_kline_data(symbol, formatted_data, is_closed)
                
                # Отправляем обновление данных клиентам (потоковые данные)
                stream_item = {
                    "type": "kline_update",
                    "symbol": symbol,
                    "data": formatted_data,
                    "timestamp": datetime.utcnow().isoformat(),
                    "is_closed": is_closed,
                    "server_timestamp": self.alert_manager._get_current_timestamp_ms() if hasattr(self.alert_manager, '_get_current_timestamp_ms') else int(datetime.utcnow().timestamp() * 1000)
                }
                
                # Отправляем обновление
                await self.connection_manager.broadcast_json(stream_item)
                
        except Exception as e:
            logger.error(f"❌ Ошибка обработки kline данных: {e}")