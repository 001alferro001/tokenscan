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
        
        # Кэш для отслеживания обработанных свечей (упрощенный)
        self.processed_candles = {}  # symbol -> last_processed_timestamp

    async def start(self):
        """Запуск WebSocket соединения"""
        self.is_running = True
        
        # Сначала загружаем исторические данные
        await self.load_historical_data_simple()
        
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

    async def load_historical_data_simple(self):
        """Простая загрузка исторических данных без сложной логики"""
        logger.info("Загрузка исторических данных...")
        
        # Получаем период хранения из настроек
        retention_hours = self.alert_manager.settings.get('data_retention_hours', 2)
        analysis_hours = self.alert_manager.settings.get('analysis_hours', 1)
        total_hours_needed = retention_hours + analysis_hours + 1  # +1 час буфера
        
        for symbol in self.trading_pairs:
            try:
                await self.load_symbol_data(symbol, total_hours_needed)
                await asyncio.sleep(0.1)  # Небольшая задержка между запросами
                        
            except Exception as e:
                logger.error(f"Ошибка загрузки данных для {symbol}: {e}")
                continue

        logger.info("Загрузка исторических данных завершена")

    async def load_symbol_data(self, symbol: str, hours: int):
        """Загрузка данных для одного символа"""
        try:
            # Простая загрузка без сложной проверки целостности
            limit = min(hours * 60 + 60, 1000)
            
            # Используем простое UTC время
            end_time = int(datetime.utcnow().timestamp() * 1000)
            start_time = end_time - (hours * 60 * 60 * 1000)
            
            url = f"{self.rest_url}/v5/market/kline"
            params = {
                'category': 'linear',
                'symbol': symbol,
                'interval': '1',
                'start': start_time,
                'end': end_time,
                'limit': limit
            }
            
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            if data.get('retCode') == 0:
                klines = data['result']['list']
                klines.reverse()  # Bybit возвращает данные в обратном порядке
                
                saved_count = 0
                for kline in klines:
                    kline_data = {
                        'start': int(kline[0]),
                        'end': int(kline[0]) + 60000,
                        'open': kline[1],
                        'high': kline[2],
                        'low': kline[3],
                        'close': kline[4],
                        'volume': kline[5],
                        'confirm': True  # Исторические данные всегда закрыты
                    }
                    
                    # Сохраняем как закрытую свечу
                    await self.alert_manager.db_manager.save_kline_data(symbol, kline_data, is_closed=True)
                    saved_count += 1
                
                logger.info(f"Загружено {saved_count} свечей для {symbol}")
            else:
                logger.error(f"Ошибка API при загрузке данных для {symbol}: {data.get('retMsg')}")
                    
        except Exception as e:
            logger.error(f"Ошибка загрузки данных для {symbol}: {e}")

    async def connect_websocket(self):
        """Подключение к WebSocket"""
        try:
            logger.info(f"Подключение к WebSocket: {self.ws_url}")
            
            async with websockets.connect(
                self.ws_url,
                ping_interval=30,
                ping_timeout=10,
                close_timeout=10
            ) as websocket:
                self.websocket = websocket
                self.last_message_time = datetime.utcnow()
                
                # Подписываемся на kline данные для всех торговых пар
                subscribe_message = {
                    "op": "subscribe",
                    "args": [f"kline.1.{pair}" for pair in self.trading_pairs]
                }
                
                await websocket.send(json.dumps(subscribe_message))
                logger.info(f"Подписка на {len(self.trading_pairs)} торговых пар")
                
                # Отправляем статус подключения
                await self.connection_manager.broadcast_json({
                    "type": "connection_status",
                    "status": "connected",
                    "pairs_count": len(self.trading_pairs),
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
                            logger.info(f"WebSocket статистика: {self.messages_received} сообщений получено")
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
                    logger.info("Успешная подписка на WebSocket")
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
                
                # Преобразуем данные в нужный формат
                formatted_data = {
                    'start': int(kline_data['start']),
                    'end': int(kline_data['end']),
                    'open': kline_data['open'],
                    'high': kline_data['high'],
                    'low': kline_data['low'],
                    'close': kline_data['close'],
                    'volume': kline_data['volume'],
                    'confirm': kline_data.get('confirm', False)  # Важно: флаг закрытия от биржи
                }
                
                # Простая проверка на дублирование
                timestamp = int(kline_data['start'])
                is_closed = kline_data.get('confirm', False)
                
                # Если свеча закрылась и мы её ещё не обрабатывали
                if is_closed:
                    last_processed = self.processed_candles.get(symbol, 0)
                    if timestamp > last_processed:
                        # Обрабатываем через менеджер алертов
                        alerts = await self.alert_manager.process_kline_data(symbol, formatted_data)
                        
                        # Помечаем свечу как обработанную
                        self.processed_candles[symbol] = timestamp
                        
                        logger.debug(f"Обработана закрытая свеча {symbol} в {timestamp}")
                
                # Отправляем обновление данных клиентам (потоковые данные)
                stream_item = {
                    "type": "kline_update",
                    "symbol": symbol,
                    "data": formatted_data,
                    "timestamp": datetime.utcnow().isoformat(),
                    "is_closed": is_closed
                }
                
                await self.connection_manager.broadcast_json(stream_item)
                
        except Exception as e:
            logger.error(f"Ошибка обработки kline данных: {e}")