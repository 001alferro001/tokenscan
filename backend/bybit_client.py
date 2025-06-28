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
        
        # Bybit WebSocket URLs
        self.ws_url = "wss://stream.bybit.com/v5/public/linear"
        self.rest_url = "https://api.bybit.com"
        
        # Настраиваемый интервал обновления
        self.update_interval = alert_manager.settings.get('update_interval_seconds', 1)

    async def start(self):
        """Запуск WebSocket соединения"""
        self.is_running = True
        
        # Сначала загружаем исторические данные с улучшенной проверкой целостности
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
        """Загрузка исторических данных с улучшенной проверкой целостности"""
        logger.info("Проверка целостности исторических данных...")
        
        # Получаем период хранения из настроек
        retention_hours = self.alert_manager.settings.get('data_retention_hours', 2)
        
        # Добавляем буфер для анализа (дополнительный час для расчета средних объемов)
        analysis_hours = self.alert_manager.settings.get('analysis_hours', 1)
        total_hours_needed = retention_hours + analysis_hours + 1  # +1 час буфера
        
        for symbol in self.trading_pairs:
            try:
                # Проверяем целостность данных с учетом буфера
                integrity_info = await self.alert_manager.db_manager.check_data_integrity(
                    symbol, total_hours_needed
                )
                
                logger.info(f"{symbol}: {integrity_info['total_existing']}/{integrity_info['total_expected']} свечей "
                           f"({integrity_info['integrity_percentage']:.1f}% целостность)")
                
                # Если целостность менее 95% или есть недостающие данные, загружаем
                if integrity_info['integrity_percentage'] < 95 or integrity_info['missing_count'] > 0:
                    logger.info(f"Загрузка недостающих данных для {symbol}...")
                    await self.load_missing_data(symbol, integrity_info['missing_periods'], total_hours_needed)
                    
                    # Повторная проверка после загрузки
                    integrity_info_after = await self.alert_manager.db_manager.check_data_integrity(
                        symbol, total_hours_needed
                    )
                    logger.info(f"{symbol}: После загрузки {integrity_info_after['total_existing']}/{integrity_info_after['total_expected']} свечей "
                               f"({integrity_info_after['integrity_percentage']:.1f}% целостность)")
                else:
                    logger.info(f"Данные для {symbol} актуальны")
                
                # Небольшая задержка между запросами
                await asyncio.sleep(0.1)
                        
            except Exception as e:
                logger.error(f"Ошибка проверки данных для {symbol}: {e}")
                continue

        logger.info("Проверка целостности данных завершена")

    async def load_missing_data(self, symbol: str, missing_periods: List[int], retention_hours: int):
        """Загрузка недостающих исторических данных с улучшенной логикой"""
        try:
            if not missing_periods:
                # Загружаем весь период с запасом
                limit = min(retention_hours * 60 + 60, 1000)  # +60 минут запаса, но не более 1000
                
                # Используем биржевое время для точности
                if self.alert_manager.time_sync:
                    end_time = self.alert_manager.time_sync.get_exchange_timestamp()
                else:
                    end_time = int(datetime.utcnow().timestamp() * 1000)
                
                start_time = end_time - (retention_hours * 60 * 60 * 1000)
                
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
                    
                    # Bybit возвращает данные в обратном порядке (новые сверху)
                    klines.reverse()
                    
                    saved_count = 0
                    for kline in klines:
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
                        saved_count += 1
                    
                    logger.info(f"Загружено {saved_count} свечей для {symbol}")
                else:
                    logger.error(f"Ошибка API при загрузке данных для {symbol}: {data.get('retMsg')}")
            else:
                # Загружаем только недостающие периоды (оптимизированная версия)
                await self._load_specific_missing_periods(symbol, missing_periods)
                    
        except Exception as e:
            logger.error(f"Ошибка загрузки недостающих данных для {symbol}: {e}")

    async def _load_specific_missing_periods(self, symbol: str, missing_periods: List[int]):
        """Загрузка конкретных недостающих периодов"""
        try:
            # Группируем последовательные периоды для оптимизации запросов
            groups = self._group_consecutive_periods(missing_periods)
            
            for group in groups:
                start_time = group[0]
                end_time = group[-1] + 60000  # Конец последней свечи в группе
                
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
                    
                    # Bybit возвращает данные в обратном порядке
                    klines.reverse()
                    
                    for kline in klines:
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
                else:
                    logger.error(f"Ошибка API при загрузке группы для {symbol}: {data.get('retMsg')}")
                
                # Задержка между запросами групп
                await asyncio.sleep(0.2)
                
        except Exception as e:
            logger.error(f"Ошибка загрузки конкретных периодов для {symbol}: {e}")

    def _group_consecutive_periods(self, periods: List[int]) -> List[List[int]]:
        """Группировка последовательных периодов"""
        if not periods:
            return []
        
        periods.sort()
        groups = []
        current_group = [periods[0]]
        
        for i in range(1, len(periods)):
            # Если периоды идут подряд (разница 60000 мс = 1 минута)
            if periods[i] - periods[i-1] == 60000:
                current_group.append(periods[i])
            else:
                groups.append(current_group)
                current_group = [periods[i]]
        
        groups.append(current_group)
        return groups

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
                    "timestamp": datetime.utcnow().isoformat()  # Используем UTC время
                }
                
                # Добавляем алерты, если они есть (уже сериализованные)
                if alerts:
                    message["alerts"] = alerts
                
                await self.connection_manager.broadcast_json(message)
                
        except Exception as e:
            logger.error(f"Ошибка обработки kline данных: {e}")