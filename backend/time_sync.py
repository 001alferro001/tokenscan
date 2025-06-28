import asyncio
import logging
import aiohttp
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

class ExchangeTimeSync:
    """Класс для синхронизации времени с биржей Bybit"""
    
    def __init__(self):
        self.time_offset = 0  # Разница между локальным и биржевым временем в миллисекундах
        self.last_sync = None
        self.sync_interval = 300  # Синхронизация каждые 5 минут
        self.is_running = False
        self.is_synced = False
        self.sync_task = None
        
    async def start(self):
        """Запуск автоматической синхронизации времени"""
        self.is_running = True
        logger.info("Запуск синхронизации времени с биржей Bybit")
        
        # Первоначальная синхронизация
        await self.sync_time()
        
        # Запускаем периодическую синхронизацию
        self.sync_task = asyncio.create_task(self._periodic_sync())
        
    async def stop(self):
        """Остановка синхронизации"""
        self.is_running = False
        if self.sync_task:
            self.sync_task.cancel()
            try:
                await self.sync_task
            except asyncio.CancelledError:
                pass
        logger.info("Синхронизация времени остановлена")
        
    async def _periodic_sync(self):
        """Периодическая синхронизация времени"""
        while self.is_running:
            try:
                await asyncio.sleep(self.sync_interval)
                if self.is_running:
                    await self.sync_time()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Ошибка периодической синхронизации времени: {e}")
                await asyncio.sleep(60)  # Повторить через минуту при ошибке
                
    async def sync_time(self) -> bool:
        """Синхронизация времени с биржей"""
        try:
            url = "https://api.bybit.com/v5/market/time"
            
            # Засекаем время до запроса (в UTC)
            local_time_before = datetime.utcnow().timestamp() * 1000
            
            timeout = aiohttp.ClientTimeout(total=5)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # Засекаем время после получения ответа (в UTC)
                        local_time_after = datetime.utcnow().timestamp() * 1000
                        
                        if data.get('retCode') == 0:
                            # Время биржи в миллисекундах
                            exchange_time = int(data['result']['timeSecond']) * 1000 + int(data['result']['timeNano']) // 1000000
                            
                            # Учитываем задержку сети (половина времени запроса)
                            network_delay = (local_time_after - local_time_before) / 2
                            adjusted_local_time = local_time_before + network_delay
                            
                            # Рассчитываем смещение
                            self.time_offset = exchange_time - adjusted_local_time
                            self.last_sync = datetime.utcnow()
                            self.is_synced = True
                            
                            logger.info(f"Время синхронизировано с биржей Bybit. Смещение: {self.time_offset:.0f}мс, задержка сети: {network_delay:.0f}мс")
                            return True
                        else:
                            logger.error(f"Ошибка API биржи при синхронизации времени: {data.get('retMsg')}")
                    else:
                        logger.error(f"HTTP ошибка при синхронизации времени: {response.status}")
                        
        except asyncio.TimeoutError:
            logger.error("Таймаут при синхронизации времени с биржей")
        except Exception as e:
            logger.error(f"Ошибка синхронизации времени с биржей: {e}")
            
        self.is_synced = False
        return False
        
    def get_exchange_time(self) -> datetime:
        """Получить текущее время биржи в UTC"""
        local_time_ms = datetime.utcnow().timestamp() * 1000
        exchange_time_ms = local_time_ms + self.time_offset
        return datetime.utcfromtimestamp(exchange_time_ms / 1000)
        
    def get_exchange_timestamp(self) -> int:
        """Получить текущий timestamp биржи в миллисекундах"""
        local_time_ms = datetime.utcnow().timestamp() * 1000
        return int(local_time_ms + self.time_offset)
        
    def get_sync_status(self) -> dict:
        """Получить статус синхронизации"""
        current_time = datetime.utcnow()
        exchange_time = self.get_exchange_time()
        
        return {
            'is_synced': self.is_synced,
            'last_sync': self.last_sync.isoformat() if self.last_sync else None,
            'time_offset_ms': self.time_offset,
            'exchange_time': exchange_time.isoformat(),
            'local_time': current_time.isoformat(),
            'sync_age_seconds': (current_time - self.last_sync).total_seconds() if self.last_sync else None,
            'serverTime': self.get_exchange_timestamp(),  # Для совместимости с клиентом
            'status': 'active' if self.is_synced else 'not_synced'
        }
        
    def is_candle_closed(self, kline_data: dict) -> bool:
        """Проверка закрытия свечи относительно биржевого времени"""
        exchange_time = self.get_exchange_timestamp()
        candle_end_time = int(kline_data['end'])
        
        # Свеча считается закрытой, если биржевое время >= времени окончания свечи
        return exchange_time >= candle_end_time
        
    def get_candle_close_time(self, kline_start_time: int) -> datetime:
        """Получить время закрытия свечи в UTC"""
        return datetime.utcfromtimestamp((kline_start_time + 60000) / 1000)