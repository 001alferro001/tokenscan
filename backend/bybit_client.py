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
        
        # Настраиваемый интервал обновления
        self.update_interval = alert_manager.settings.get('update_interval_seconds', 1)

    async def start(self):
        """Запуск WebSocket соединения"""
        self.is_running = True
        
        # Сначала загружаем исторические данные с проверкой целостности
        await self.load_historical_data_with_integrity_check()
        
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

    async def load_historical_data_with_integrity_check(self):
        """Загрузка исторических данных с проверкой целостности"""
        logger.info("Проверка целостности исторических данных...")
        
        # Получаем период хранения из настроек
        retention_hours = self.alert_manager.settings.get('data_retention_hours', 2)
        
        for symbol in self.trading_pairs:
            try:
                # Проверяем целостность данных
                integrity_info = await self.alert_manager.db_manager.check_data_integrity(symbol, retention_hours)
                
                logger.info(f"{symbol}: {integrity_info['total_existing']}/{integrity_info['total_expected']} свечей "
                           f"({integrity_info['integrity_percentage']:.1f}% целостность)")
                
                # Если целостность менее 90% или есть недостающие данные, загружаем
                if integrity_info['integrity_percentage'] < 90 or integrity_info['missing_count'] > 0:
                    logger.info(f"Загрузка недостающих данных для {symbol}...")
                    await self.load_missing_data(symbol, integrity_info['missing_periods'], retention_hours)
                else:
                    logger.info(f"Данные для {symbol} актуальны")
                
                # Небольшая задержка между запросами
                await asyncio.sleep(0.1)
                        
            except Exception as e:
                logger.error(f"Ошибка проверки данных для {symbol}: {e}")
                continue

        logger.info("Проверка целостности данных завершена")

    async def load_missing_data(self, symbol: str, missing_periods: List[int], retention_hours: int):
        """Загрузка недостающих исторических данных"""
        try:
            if not missing_periods:
                # Загружаем весь период
                limit = min(retention_hours * 60, 1000)  # Bybit ограничивает до 1000
                
                url = f"{self.rest_url}/v5/market/kline"
                params = {
                    'category': 'linear',
                    'symbol': symbol,
                    'interval': '1',
                    'limit': limit
                }
                
                response = requests.get(url, params=params, timeout=10)
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
            else:
                # Загружаем только недостающие периоды (группами)
                # Группируем последовательные периоды для оптимизации запросов
                groups = []
                current_group = [missing_periods[0]]
                
                for i in range(1, len(missing_periods)):
                    if missing_periods[i] - missing_periods[i-1] == 60000:  # Последовательные минуты
                        current_group.append(missing_periods[i])
                    else:
                        groups.append(current_group)
                        current_group = [missing_periods[i]]
                
                groups.append(current_group)
                
                # Загружаем каждую группу
                for group in groups:
                    start_time = group[0]
                    end_time = group[-1] + 60000
                    
                    url = f"{self.rest_url}/v5/market/kline"
                    params = {
                        'category': 'linear',
                        'symbol': symbol,
                        'interval': '1',
                        'start': start_time,
                        'end': end_time
                    }
                    
                    response = requests.get(url, params=params, timeout=10)
                    data = response.json()
                    
                    if data.get('retCode') == 0:
                        klines = data['result']['list']
                        
                        for kline in reversed(klines):
                            kline_data = {
                                'start': int(kline[0]),
                                'end': int(kline[0]) + 60000,
                                'open': kline[1],
                                'high': kline[2],
                                'low': kline[3],
                                'close': kline[4],
                                'volume': kline[5]
                            }
                            
                            await self.alert_manager.db_manager.save_kline_data(symbol, kline_data)
                    
                    # Задержка между запросами групп
                    await asyncio.sleep(0.2)
                    
        except Exception as e:
            logger.error(f"Ошибка загрузки недостающих данных для {symbol}: {e}")

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
                logger.info(f"Подписка на {len(self.trading_pairs)} торговых пар с интервалом {self.update_interval}с")
                
                # Отправляем статус подключения
                await self.connection_manager.broadcast_json({
                    "type": "connection_status",
                    "status": "connected",
                    "pairs_count": len(self.trading_pairs),
                    "update_interval": self.update_interval
                })
                
                # Обработка входящих сообщений
                async for message in websocket:
                    if not self.is_running:
                        break
                        
                    try:
                        data = json.loads(message)
                        await self.handle_message(data)
                        
                        # Добавляем задержку согласно настройкам
                        if self.update_interval > 1:
                            await asyncio.sleep(self.update_interval - 1)
                            
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