import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import List, Dict, Optional
from datetime import datetime, timedelta

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import uvicorn
import json

from database import DatabaseManager
from alert_manager import AlertManager
from bybit_client import BybitWebSocketClient
from price_filter import PriceFilter
from telegram_bot import TelegramBot
from time_sync import ExchangeTimeSync

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Глобальные переменные
db_manager = None
alert_manager = None
bybit_client = None
price_filter = None
telegram_bot = None
time_sync = None
manager = None

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket подключен. Всего подключений: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"WebSocket отключен. Всего подключений: {len(self.active_connections)}")

    async def send_personal_message(self, message: str, websocket: WebSocket):
        try:
            await websocket.send_text(message)
        except Exception as e:
            logger.error(f"Ошибка отправки личного сообщения: {e}")

    async def broadcast(self, message: str):
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.error(f"Ошибка отправки сообщения: {e}")
                disconnected.append(connection)
        
        # Удаляем отключенные соединения
        for connection in disconnected:
            self.disconnect(connection)

    async def broadcast_json(self, data: dict):
        import json
        message = json.dumps(data, default=str)  # default=str для datetime объектов
        await self.broadcast(message)

manager = ConnectionManager()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global db_manager, alert_manager, bybit_client, price_filter, telegram_bot, time_sync
    
    try:
        logger.info("Запуск системы анализа объемов...")
        
        # Инициализация синхронизации времени
        time_sync = ExchangeTimeSync()
        await time_sync.start()
        
        # Инициализация базы данных
        db_manager = DatabaseManager()
        await db_manager.initialize()
        
        # Инициализация Telegram бота
        telegram_bot = TelegramBot()
        
        # Инициализация менеджера алертов с синхронизацией времени
        alert_manager = AlertManager(db_manager, telegram_bot, manager, time_sync)
        
        # Инициализация фильтра цен
        price_filter = PriceFilter(db_manager)
        
        # Получение списка торговых пар
        trading_pairs = await db_manager.get_watchlist()
        if not trading_pairs:
            logger.warning("Нет торговых пар в watchlist. Запуск фильтра цен...")
            asyncio.create_task(price_filter.start())
            # Ждем немного для загрузки пар
            await asyncio.sleep(10)
            trading_pairs = await db_manager.get_watchlist()
        
        if trading_pairs:
            logger.info(f"Найдено {len(trading_pairs)} торговых пар для мониторинга")
            
            # Инициализация WebSocket клиента Bybit
            bybit_client = BybitWebSocketClient(trading_pairs, alert_manager, manager)
            
            # Запуск всех сервисов
            asyncio.create_task(bybit_client.start())
            asyncio.create_task(price_filter.start())
            
            # Запуск периодической очистки данных
            asyncio.create_task(periodic_cleanup())
            
            logger.info("Система успешно запущена!")
        else:
            logger.error("Не удалось получить торговые пары. Система не запущена.")
            
    except Exception as e:
        logger.error(f"Ошибка запуска системы: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Остановка системы...")
    if time_sync:
        await time_sync.stop()
    if bybit_client:
        await bybit_client.stop()
    if price_filter:
        await price_filter.stop()
    if db_manager:
        db_manager.close()

app = FastAPI(title="Trading Volume Analyzer", lifespan=lifespan)

# Модели данных
class WatchlistAdd(BaseModel):
    symbol: str

class WatchlistUpdate(BaseModel):
    id: int
    symbol: str
    is_active: bool

async def periodic_cleanup():
    """Периодическая очистка старых данных"""
    while True:
        try:
            await asyncio.sleep(3600)  # Каждый час
            if alert_manager:
                await alert_manager.cleanup_old_data()
            if db_manager:
                retention_hours = alert_manager.settings.get('data_retention_hours', 2) if alert_manager else 2
                await db_manager.cleanup_old_data(retention_hours)
            logger.info("Периодическая очистка данных выполнена")
        except Exception as e:
            logger.error(f"Ошибка периодической очистки: {e}")

# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Ожидаем сообщения от клиента
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                # Обрабатываем ping от клиента
                if message.get('type') == 'ping':
                    await websocket.send_text(json.dumps({'type': 'pong'}))
            except json.JSONDecodeError:
                # Игнорируем некорректные JSON сообщения
                pass
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket ошибка: {e}")
        manager.disconnect(websocket)

# API endpoints
@app.get("/api/stats")
async def get_stats():
    """Получить статистику системы"""
    try:
        if not db_manager:
            return {"error": "Database not initialized"}
        
        # Получаем статистику из базы данных
        watchlist = await db_manager.get_watchlist()
        alerts_data = await db_manager.get_all_alerts(limit=1000)
        
        # Добавляем информацию о синхронизации времени
        time_sync_status = time_sync.get_sync_status() if time_sync else None
        
        return {
            "pairs_count": len(watchlist),
            "alerts_count": len(alerts_data.get('alerts', [])),
            "volume_alerts_count": len(alerts_data.get('volume_alerts', [])),
            "consecutive_alerts_count": len(alerts_data.get('consecutive_alerts', [])),
            "priority_alerts_count": len(alerts_data.get('priority_alerts', [])),
            "last_update": datetime.now().isoformat(),
            "system_status": "running",
            "time_sync": time_sync_status
        }
    except Exception as e:
        logger.error(f"Ошибка получения статистики: {e}")
        return {"error": str(e)}

@app.get("/api/time")
async def get_time_info():
    """Получить информацию о времени"""
    try:
        if time_sync:
            return time_sync.get_sync_status()
        else:
            return {
                "is_synced": False,
                "local_time": datetime.now().isoformat(),
                "error": "Time sync not initialized"
            }
    except Exception as e:
        logger.error(f"Ошибка получения информации о времени: {e}")
        return {"error": str(e)}

@app.get("/api/watchlist")
async def get_watchlist():
    """Получить список торговых пар"""
    try:
        pairs = await db_manager.get_watchlist_details()
        return {"pairs": pairs}
    except Exception as e:
        logger.error(f"Ошибка получения watchlist: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/watchlist")
async def add_to_watchlist(item: WatchlistAdd):
    """Добавить торговую пару в watchlist"""
    try:
        await db_manager.add_to_watchlist(item.symbol)
        
        # Уведомляем клиентов об обновлении
        await manager.broadcast_json({
            "type": "watchlist_updated",
            "action": "added",
            "symbol": item.symbol
        })
        
        return {"status": "success", "symbol": item.symbol}
    except Exception as e:
        logger.error(f"Ошибка добавления в watchlist: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/watchlist/{item_id}")
async def update_watchlist_item(item_id: int, item: WatchlistUpdate):
    """Обновить элемент watchlist"""
    try:
        await db_manager.update_watchlist_item(item.id, item.symbol, item.is_active)
        
        # Уведомляем клиентов об обновлении
        await manager.broadcast_json({
            "type": "watchlist_updated",
            "action": "updated",
            "item_id": item_id
        })
        
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Ошибка обновления watchlist: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/watchlist/{item_id}")
async def remove_from_watchlist(item_id: int):
    """Удалить торговую пару из watchlist"""
    try:
        await db_manager.remove_from_watchlist(item_id=item_id)
        
        # Уведомляем клиентов об обновлении
        await manager.broadcast_json({
            "type": "watchlist_updated",
            "action": "removed",
            "item_id": item_id
        })
        
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Ошибка удаления из watchlist: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/alerts/all")
async def get_all_alerts():
    """Получить все алерты"""
    try:
        alerts = await db_manager.get_all_alerts()
        return alerts
    except Exception as e:
        logger.error(f"Ошибка получения алертов: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/alerts/{alert_type}")
async def get_alerts_by_type(alert_type: str, limit: int = 50):
    """Получить алерты по типу"""
    try:
        alerts = await db_manager.get_alerts_by_type(alert_type, limit)
        return {"alerts": alerts}
    except Exception as e:
        logger.error(f"Ошибка получения алертов по типу: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/alerts/clear/{alert_type}")
async def clear_alerts(alert_type: str):
    """Очистить алерты по типу"""
    try:
        await db_manager.clear_alerts(alert_type)
        
        # Уведомляем клиентов об очистке
        await manager.broadcast_json({
            "type": "alerts_cleared",
            "alert_type": alert_type
        })
        
        return {"status": "success", "alert_type": alert_type}
    except Exception as e:
        logger.error(f"Ошибка очистки алертов: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/chart-data/{symbol}")
async def get_chart_data(symbol: str, hours: int = 1, alert_time: Optional[str] = None):
    """Получить данные для графика"""
    try:
        chart_data = await db_manager.get_chart_data(symbol, hours, alert_time)
        return {"chart_data": chart_data}
    except Exception as e:
        logger.error(f"Ошибка получения данных графика: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/settings")
async def get_settings():
    """Получить текущие настройки анализатора"""
    if alert_manager and price_filter:
        settings = {
            "volume_analyzer": alert_manager.get_settings(),
            "price_filter": price_filter.settings,
            "alerts": {
                "volume_alerts_enabled": alert_manager.settings.get('volume_alerts_enabled', True),
                "consecutive_alerts_enabled": alert_manager.settings.get('consecutive_alerts_enabled', True),
                "priority_alerts_enabled": alert_manager.settings.get('priority_alerts_enabled', True)
            },
            "imbalance": {
                "fair_value_gap_enabled": alert_manager.settings.get('fair_value_gap_enabled', True),
                "order_block_enabled": alert_manager.settings.get('order_block_enabled', True),
                "breaker_block_enabled": alert_manager.settings.get('breaker_block_enabled', True),
                "min_gap_percentage": 0.1,
                "min_strength": 0.5
            },
            "orderbook": {
                "enabled": alert_manager.settings.get('orderbook_enabled', False),
                "snapshot_on_alert": alert_manager.settings.get('orderbook_snapshot_on_alert', False)
            },
            "telegram": {
                "enabled": telegram_bot.enabled if telegram_bot else False
            }
        }
        
        # Добавляем информацию о синхронизации времени
        if time_sync:
            settings["time_sync"] = time_sync.get_sync_status()
        
        return settings
    return {
        "volume_analyzer": {
            "analysis_hours": 1,
            "offset_minutes": 0,
            "volume_multiplier": 2.0,
            "min_volume_usdt": 1000,
            "consecutive_long_count": 5,
            "alert_grouping_minutes": 5,
            "data_retention_hours": 2,
            "update_interval_seconds": 1,
            "notification_enabled": True,
            "volume_type": "long"
        },
        "alerts": {
            "volume_alerts_enabled": True,
            "consecutive_alerts_enabled": True,
            "priority_alerts_enabled": True
        },
        "imbalance": {
            "fair_value_gap_enabled": True,
            "order_block_enabled": True,
            "breaker_block_enabled": True,
            "min_gap_percentage": 0.1,
            "min_strength": 0.5
        },
        "orderbook": {
            "enabled": False,
            "snapshot_on_alert": False
        },
        "telegram": {
            "enabled": False
        },
        "time_sync": {
            "is_synced": False,
            "error": "Time sync not initialized"
        }
    }

@app.post("/api/settings")
async def update_settings(settings: dict):
    """Обновить настройки анализатора"""
    try:
        if alert_manager and 'volume_analyzer' in settings:
            alert_manager.update_settings(settings['volume_analyzer'])
        
        if alert_manager and 'alerts' in settings:
            alert_manager.update_settings(settings['alerts'])
            
        if alert_manager and 'imbalance' in settings:
            alert_manager.update_settings(settings['imbalance'])
            
        if alert_manager and 'orderbook' in settings:
            orderbook_settings = {
                'orderbook_enabled': settings['orderbook'].get('enabled', False),
                'orderbook_snapshot_on_alert': settings['orderbook'].get('snapshot_on_alert', False)
            }
            alert_manager.update_settings(orderbook_settings)
        
        if price_filter and 'price_filter' in settings:
            price_filter.update_settings(settings['price_filter'])
            
        await manager.broadcast_json({
            "type": "settings_updated",
            "data": settings
        })
        return {"status": "success", "settings": settings}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Проверяем существование директории dist перед монтированием
if os.path.exists("dist"):
    if os.path.exists("dist/assets"):
        app.mount("/assets", StaticFiles(directory="dist/assets"), name="assets")
    
    @app.get("/vite.svg")
    async def get_vite_svg():
        if os.path.exists("dist/vite.svg"):
            return FileResponse("dist/vite.svg")
        raise HTTPException(status_code=404, detail="File not found")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Обслуживание SPA для всех маршрутов"""
        if os.path.exists("dist/index.html"):
            return FileResponse("dist/index.html")
        raise HTTPException(status_code=404, detail="SPA not built")
else:
    @app.get("/")
    async def root():
        return {"message": "Frontend not built. Run 'npm run build' first."}

if __name__ == "__main__":
    # Настройки сервера из переменных окружения
    host = os.getenv('SERVER_HOST', '0.0.0.0')
    port = int(os.getenv('SERVER_PORT', 8000))
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=False,
        log_level="info"
    )