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
        
        # 🎯 КРИТИЧЕСКИ ВАЖНО: Отслеживание подписанных пар
        self.subscribed_pairs = set()
        self.subscription_confirmed = set()  # Пары с подтвержденной подпиской
        self.failed_subscriptions = set()
        self.subscription_attempts = {}  # symbol -> attempt_count

    async def start(self):
        """Запуск WebSocket соединения с проверкой целостности БД"""
        self.is_running = True
        
        # НОВОЕ: Интеллектуальная проверка и загрузка недостающих данных
        await self.intelligent_data_check_and_load()
        
        # Затем подключаемся к WebSocket для real-time данных
        while self.is_running:
            try:
                await self.connect_websocket()
            except Exception as e:
                logger.error(f"❌ WebSocket ошибка: {e}")
                if self.is_running:
                    logger.info("🔄 Переподключение через 5 секунд...")
                    await asyncio.sleep(5)

    async def stop(self):
        """Остановка WebSocket соединения"""
        self.is_running = False
        if self.ping_task:
            self.ping_task.cancel()
        if self.websocket:
            await self.websocket.close()

    async def intelligent_data_check_and_load(self):
        """🧠 ИНТЕЛЛЕКТУАЛЬНАЯ проверка целостности БД и загрузка только недостающих данных"""
        logger.info("🔍 Запуск интеллектуальной проверки целостности базы данных...")
        
        # Получаем период хранения из настроек
        retention_hours = self.alert_manager.settings.get('data_retention_hours', 2)
        analysis_hours = self.alert_manager.settings.get('analysis_hours', 1)
        total_hours_needed = retention_hours + analysis_hours + 1  # +1 час буфера
        
        # Получаем сводку по всем символам
        summary = await self.alert_manager.db_manager.get_missing_data_summary(
            self.trading_pairs, total_hours_needed
        )
        
        logger.info(f"📊 Сводка по данным:")
        logger.info(f"   • Всего символов: {summary['total_symbols']}")
        logger.info(f"   • С хорошими данными: {summary['symbols_with_good_data']}")
        logger.info(f"   • Требуют загрузки: {summary['symbols_need_loading']}")
        logger.info(f"   • Качество данных: {summary.get('quality_distribution', {})}")
        
        # Если большинство данных актуальны, загружаем только недостающие
        if summary['symbols_with_good_data'] > summary['symbols_need_loading']:
            logger.info("✅ Большинство данных актуальны. Загружаем только недостающие...")
            await self._load_missing_data_optimized(summary['symbols_details'], total_hours_needed)
        else:
            logger.info("⚠️ Много недостающих данных. Выполняем полную загрузку...")
            await self._load_all_data_full(total_hours_needed)
        
        logger.info("🎯 Проверка целостности БД завершена!")

    async def _load_missing_data_optimized(self, symbols_details: List[Dict], hours: int):
        """Оптимизированная загрузка только недостающих данных"""
        symbols_to_load = [
            detail for detail in symbols_details 
            if detail['needs_loading']
        ]
        
        if not symbols_to_load:
            logger.info("✅ Все данные актуальны, загрузка не требуется")
            return
        
        logger.info(f"📥 Загрузка недостающих данных для {len(symbols_to_load)} символов...")
        
        # Группируем символы по качеству данных для приоритизации
        critical_symbols = [s for s in symbols_to_load if s['quality'] == 'critical']
        poor_symbols = [s for s in symbols_to_load if s['quality'] == 'poor']
        fair_symbols = [s for s in symbols_to_load if s['quality'] == 'fair']
        
        # Загружаем в порядке приоритета
        for priority_group, group_name in [
            (critical_symbols, "критических"),
            (poor_symbols, "плохих"),
            (fair_symbols, "удовлетворительных")
        ]:
            if priority_group:
                logger.info(f"🔄 Загрузка {group_name} данных ({len(priority_group)} символов)...")
                await self._load_symbols_batch(priority_group, hours)

    async def _load_all_data_full(self, hours: int):
        """Полная загрузка данных для всех символов"""
        logger.info(f"📥 Полная загрузка данных для {len(self.trading_pairs)} символов...")
        
        symbols_details = [{'symbol': symbol} for symbol in self.trading_pairs]
        await self._load_symbols_batch(symbols_details, hours)

    async def _load_symbols_batch(self, symbols_details: List[Dict], hours: int):
        """Загрузка данных для группы символов с оптимизацией"""
        batch_size = 5  # Загружаем по 5 символов параллельно
        
        for i in range(0, len(symbols_details), batch_size):
            batch = symbols_details[i:i + batch_size]
            
            # Создаем задачи для параллельной загрузки
            tasks = []
            for symbol_detail in batch:
                symbol = symbol_detail['symbol']
                task = self._load_symbol_data_optimized(symbol, hours)
                tasks.append(task)
            
            # Выполняем загрузку параллельно
            try:
                await asyncio.gather(*tasks, return_exceptions=True)
                logger.info(f"✅ Обработан пакет {i//batch_size + 1}/{(len(symbols_details) + batch_size - 1)//batch_size}")
                
                # Небольшая пауза между пакетами для снижения нагрузки на API
                if i + batch_size < len(symbols_details):
                    await asyncio.sleep(1.0)
                    
            except Exception as e:
                logger.error(f"❌ Ошибка загрузки пакета: {e}")

    async def _load_symbol_data_optimized(self, symbol: str, hours: int):
        """Оптимизированная загрузка данных для одного символа"""
        try:
            # Получаем оптимизированный план загрузки
            loading_periods = await self.alert_manager.db_manager.optimize_missing_data_loading(symbol, hours)
            
            if not loading_periods:
                logger.debug(f"✅ {symbol}: Данные актуальны, загрузка не требуется")
                return
            
            logger.info(f"📥 {symbol}: Загрузка {len(loading_periods)} периодов...")
            
            # Загружаем каждый период
            for i, period in enumerate(loading_periods):
                try:
                    await self._load_period_from_exchange(
                        symbol, 
                        period['start_unix'], 
                        period['end_unix']
                    )
                    
                    logger.debug(f"✅ {symbol}: Период {i+1}/{len(loading_periods)} загружен")
                    
                    # Небольшая пауза между периодами
                    if i < len(loading_periods) - 1:
                        await asyncio.sleep(0.2)
                        
                except Exception as e:
                    logger.error(f"❌ {symbol}: Ошибка загрузки периода {i+1}: {e}")
                    continue
            
            logger.info(f"✅ {symbol}: Загрузка завершена")
                
        except Exception as e:
            logger.error(f"❌ Ошибка оптимизированной загрузки данных для {symbol}: {e}")

    async def _load_period_from_exchange(self, symbol: str, start_time_unix: int, end_time_unix: int):
        """Загрузка конкретного периода с биржи"""
        try:
            # Рассчитываем количество минут в периоде
            duration_minutes = (end_time_unix - start_time_unix) // 60000
            limit = min(duration_minutes + 10, 1000)  # +10 для буфера, максимум 1000
            
            url = f"{self.rest_url}/v5/market/kline"
            params = {
                'category': 'linear',
                'symbol': symbol,
                'interval': '1',
                'start': start_time_unix,
                'end': end_time_unix,
                'limit': limit
            }
            
            response = requests.get(url, params=params, timeout=15)
            data = response.json()
            
            if data.get('retCode') == 0:
                klines = data['result']['list']
                klines.reverse()  # Bybit возвращает данные в обратном порядке
                
                saved_count = 0
                skipped_count = 0
                
                for kline in klines:
                    # Биржа передает UNIX время в миллисекундах
                    kline_timestamp_unix = int(kline[0])
                    
                    # Для исторических данных округляем до минут с нулями
                    rounded_timestamp = (kline_timestamp_unix // 60000) * 60000
                    
                    # Проверяем, что время в нужном диапазоне
                    if not (start_time_unix <= rounded_timestamp < end_time_unix):
                        continue
                    
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
                
                if saved_count > 0:
                    logger.debug(f"📊 {symbol}: Сохранено {saved_count} новых свечей, пропущено {skipped_count}")
                    
            else:
                logger.error(f"❌ API ошибка для {symbol}: {data.get('retMsg')}")
                    
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки периода для {symbol}: {e}")

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
        """🎯 ИСПРАВЛЕННОЕ подключение к WebSocket с гарантированной подпиской на ВСЕ торговые пары"""
        try:
            logger.info(f"🔗 Подключение к WebSocket: {self.ws_url}")
            logger.info(f"📊 ВСЕГО торговых пар для подписки: {len(self.trading_pairs)}")
            
            # Очищаем списки подписанных пар
            self.subscribed_pairs.clear()
            self.subscription_confirmed.clear()
            self.failed_subscriptions.clear()
            self.subscription_attempts.clear()
            
            async with websockets.connect(
                self.ws_url,
                ping_interval=30,
                ping_timeout=10,
                close_timeout=10
            ) as websocket:
                self.websocket = websocket
                self.last_message_time = datetime.utcnow()
                
                # 🚀 КРИТИЧЕСКИ ВАЖНО: Подписываемся на ВСЕ пары из watchlist
                await self._subscribe_to_all_pairs_guaranteed(websocket)
                
                # Ждем подтверждений подписок
                await asyncio.sleep(10)  # Даем время на получение подтверждений
                
                # Проверяем результаты подписки
                confirmed_count = len(self.subscription_confirmed)
                total_pairs = len(self.trading_pairs)
                success_rate = (confirmed_count / total_pairs) * 100 if total_pairs > 0 else 0
                
                logger.info(f"📊 РЕЗУЛЬТАТ ПОДПИСКИ:")
                logger.info(f"   • Всего пар в watchlist: {total_pairs}")
                logger.info(f"   • Подтверждено подписок: {confirmed_count}")
                logger.info(f"   • Успешность: {success_rate:.1f}%")
                logger.info(f"   • Неподтвержденных: {total_pairs - confirmed_count}")
                
                if confirmed_count < total_pairs:
                    unconfirmed = set(self.trading_pairs) - self.subscription_confirmed
                    logger.warning(f"⚠️ Неподтвержденные пары: {sorted(list(unconfirmed))[:10]}...")  # Показываем первые 10
                    
                    # Пробуем повторную подписку на неподтвержденные пары
                    await self._retry_failed_subscriptions(websocket, unconfirmed)
                
                # Отправляем статус подключения с детальной информацией
                await self.connection_manager.broadcast_json({
                    "type": "connection_status",
                    "status": "connected",
                    "pairs_count": total_pairs,
                    "subscribed_count": len(self.subscribed_pairs),
                    "confirmed_count": confirmed_count,
                    "failed_count": len(self.failed_subscriptions),
                    "success_rate": success_rate,
                    "subscribed_pairs": sorted(list(self.subscription_confirmed)),
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
                            active_pairs = len(self.subscription_confirmed)
                            logger.info(f"📊 WebSocket статистика: {self.messages_received} сообщений, активных пар: {active_pairs}/{total_pairs}")
                            self.last_stats_log = datetime.utcnow()
                            
                    except Exception as e:
                        logger.error(f"❌ Ошибка обработки сообщения: {e}")
                        
        except Exception as e:
            logger.error(f"❌ Ошибка WebSocket соединения: {e}")
            raise
        finally:
            if self.ping_task:
                self.ping_task.cancel()

    async def _subscribe_to_all_pairs_guaranteed(self, websocket):
        """🎯 ГАРАНТИРОВАННАЯ подписка на ВСЕ торговые пары из watchlist"""
        total_pairs = len(self.trading_pairs)
        logger.info(f"🚀 Начинаем ГАРАНТИРОВАННУЮ подписку на {total_pairs} пар")
        
        # Стратегия 1: Очень маленькие пакеты для максимальной надежности
        batch_size = 10  # Еще меньше для гарантии
        batches_sent = 0
        total_subscribed = 0
        
        for i in range(0, total_pairs, batch_size):
            batch = self.trading_pairs[i:i + batch_size]
            batch_number = i // batch_size + 1
            total_batches = (total_pairs + batch_size - 1) // batch_size
            
            try:
                # Формируем сообщение подписки для пакета
                subscribe_message = {
                    "op": "subscribe",
                    "args": [f"kline.1.{pair}" for pair in batch]
                }
                
                logger.info(f"📤 Отправка пакета {batch_number}/{total_batches}: {len(batch)} пар")
                logger.debug(f"   Пары: {batch}")
                
                # Отправляем подписку
                await websocket.send(json.dumps(subscribe_message))
                
                # Добавляем пары в список отправленных
                for pair in batch:
                    self.subscribed_pairs.add(pair)
                    self.subscription_attempts[pair] = self.subscription_attempts.get(pair, 0) + 1
                
                total_subscribed += len(batch)
                batches_sent += 1
                
                # Увеличенная задержка между пакетами для стабильности
                await asyncio.sleep(3.0)
                
                logger.info(f"✅ Пакет {batch_number} отправлен. Прогресс: {total_subscribed}/{total_pairs}")
                
            except Exception as e:
                logger.error(f"❌ Ошибка отправки пакета {batch_number}: {e}")
                for pair in batch:
                    self.failed_subscriptions.add(pair)
                continue
        
        logger.info(f"🎯 Первичная подписка завершена!")
        logger.info(f"   • Отправлено пакетов: {batches_sent}/{total_batches}")
        logger.info(f"   • Отправлено подписок: {total_subscribed}/{total_pairs}")
        logger.info(f"   • Ошибок отправки: {len(self.failed_subscriptions)}")

    async def _retry_failed_subscriptions(self, websocket, failed_pairs: set):
        """Повторная попытка подписки на неудачные пары"""
        if not failed_pairs:
            return
            
        logger.info(f"🔄 Повторная подписка на {len(failed_pairs)} неподтвержденных пар...")
        
        # Индивидуальная подписка на каждую неудачную пару
        retry_success = 0
        retry_failed = 0
        
        for pair in failed_pairs:
            try:
                # Проверяем количество попыток
                attempts = self.subscription_attempts.get(pair, 0)
                if attempts >= 3:  # Максимум 3 попытки
                    logger.warning(f"⚠️ Превышено количество попыток для {pair}")
                    self.failed_subscriptions.add(pair)
                    retry_failed += 1
                    continue
                
                subscribe_message = {
                    "op": "subscribe",
                    "args": [f"kline.1.{pair}"]
                }
                
                await websocket.send(json.dumps(subscribe_message))
                self.subscription_attempts[pair] = attempts + 1
                
                # Небольшая задержка между индивидуальными подписками
                await asyncio.sleep(1.0)
                
                retry_success += 1
                logger.debug(f"🔄 Повторная подписка на {pair} (попытка {attempts + 1})")
                
            except Exception as e:
                logger.error(f"❌ Ошибка повторной подписки на {pair}: {e}")
                self.failed_subscriptions.add(pair)
                retry_failed += 1
        
        logger.info(f"🎯 Повторная подписка завершена: отправлено {retry_success}, ошибок {retry_failed}")

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
                logger.error(f"❌ Ошибка мониторинга соединения: {e}")

    async def handle_message(self, data: Dict):
        """Обработка входящих WebSocket сообщений с улучшенным отслеживанием подписок"""
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
                                if pair in self.trading_pairs:  # ВАЖНО: проверяем, что пара в watchlist
                                    self.subscription_confirmed.add(pair)
                                    logger.debug(f"✅ Подтверждена подписка на {pair}")
                                else:
                                    logger.warning(f"⚠️ Подтверждена подписка на {pair}, но пары нет в watchlist")
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
                
                # 🎯 КРИТИЧЕСКИ ВАЖНО: Подтверждаем получение данных для этой пары
                if symbol in self.trading_pairs:
                    if symbol not in self.subscription_confirmed:
                        self.subscription_confirmed.add(symbol)
                        logger.info(f"✅ Получены данные от {symbol}, подписка подтверждена автоматически")
                else:
                    logger.warning(f"⚠️ Получены данные от {symbol}, но пары НЕТ в watchlist!")
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
                
                # Логируем получение данных для отладки (только для первых 5 пар)
                if symbol in sorted(list(self.subscription_confirmed))[:5]:
                    logger.debug(f"📊 Данные от {symbol}: закрыта={is_closed}, время={start_time_unix}")
                
                # Простая проверка на дублирование для закрытых свечей
                if is_closed:
                    last_processed = self.processed_candles.get(symbol, 0)
                    if start_time_unix > last_processed:
                        # Обрабатываем через менеджер алертов
                        alerts = await self.alert_manager.process_kline_data(symbol, formatted_data)
                        
                        # Помечаем свечу как обработанную
                        self.processed_candles[symbol] = start_time_unix
                        
                        if alerts:
                            logger.info(f"🚨 Создано {len(alerts)} алертов для {symbol}")
                
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