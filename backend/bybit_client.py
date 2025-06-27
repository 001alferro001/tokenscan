import asyncio
import json
import logging
import websockets
from typing import List, Dict, Optional
import requests
from datetime import datetime

logger = logging.getLogger(__name__)

class BybitWebSocketClient:
    def __init__(self, trading_pairs: List[str], alert_manager, connection_manager):
        self.trading_pairs = trading_pairs
        self.alert_manager = alert_manager
        self.connection_manager = connection_manager
        self.websocket = None
        self.is_running = False
        
        # Bybit WebSocket URLs
        self.ws_url = "wss://stream.bybit.com/v5/public/linear"
        self.rest_url = "https://api.bybit.com"

    async def start(self):
        """Запуск WebSocket соединения"""
        self.is_running = True
        
        # Сначала загружаем исторические данные
        await self.load_historical_data()
        
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
        if self.websocket:
            await self.websocket.close()

    async def load_historical_data(self):
        """Загрузка исторических данных за настраиваемый период"""
        logger.info("Загрузка исторических данных...")
        
        # Получаем период хранения из настроек
        retention_hours = self.alert_manager.settings.get('data_retention_hours', 2)
        limit = retention_hours * 60  # Количество минут
        
        for symbol in self.trading_pairs:
            try:
                # Получаем данные за указанный период
                url = f"{self.rest_url}/v5/market/kline"
                params = {
                    'category': 'linear',
                    'symbol': symbol,
                    'interval': '1',
                    'limit': min(limit, 1000)  # Bybit ограничивает до 1000
                }
                
                response = requests.get(url, params=params)
                data = response.json()
                
                if data.get('retCode') == 0:
                    klines = data['result']['list']
                    
                    for kline in reversed(klines):  # Bybit возвращает в обратном порядке
                        kline_data = {
                            'start': int(kline[0]),
                            'end': int(kline[0]) + 60000,  # +1 минута
                            'open': kline[1],
                            'high': kline[2],
                            'low': kline[3],
                            'close': kline[4],
                            'volume': kline[5]
                        }
                        
                        # Сохраняем в базу данных
                        await self.alert_manager.db_manager.save_kline_data(symbol, kline_data)
                
                # Небольшая задержка между запросами
                await asyncio.sleep(0.1)
                        
            except Exception as e:
                logger.error(f"Ошибка загрузки исторических данных для {symbol}: {e}")
                continue

        logger.info("Исторические данные загружены")

    async def connect_websocket(self):
        """Подключение к WebSocket"""
        try:
            async with websockets.connect(self.ws_url) as websocket:
                self.websocket = websocket
                
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
                    "pairs_count": len(self.trading_pairs)
                })
                
                # Обработка входящих сообщений
                async for message in websocket:
                    if not self.is_running:
                        break
                        
                    try:
                        data = json.loads(message)
                        await self.handle_message(data)
                    except Exception as e:
                        logger.error(f"Ошибка обработки сообщения: {e}")
                        
        except Exception as e:
            logger.error(f"Ошибка WebSocket соединения: {e}")
            raise

    async def handle_message(self, data: Dict):
        """Обработка входящих WebSocket сообщений"""
        try:
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
                    'volume': kline_data['volume']
                }
                
                # Сохраняем в базу данных
                await self.alert_manager.db_manager.save_kline_data(symbol, formatted_data)
                
                # Обрабатываем через менеджер алертов
                alerts = await self.alert_manager.process_kline_data(symbol, formatted_data)
                
                # Отправляем обновление данных клиентам (потоковые данные)
                message = {
                    "type": "kline_update",
                    "symbol": symbol,
                    "data": formatted_data,
                    "timestamp": datetime.now().isoformat()
                }
                
                # Добавляем алерты, если они есть
                if alerts:
                    message["alerts"] = alerts
                
                await self.connection_manager.broadcast_json(message)
                
        except Exception as e:
            logger.error(f"Ошибка обработки kline данных: {e}")