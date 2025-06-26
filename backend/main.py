import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import os
from dotenv import load_dotenv

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from database import DatabaseManager
from bybit_client import BybitWebSocketClient
from alert_manager import AlertManager
from price_filter import PriceFilter
from telegram_bot import TelegramBot

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Trading Volume Analyzer", version="2.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic модели
class WatchlistUpdate(BaseModel):
    id: int
    symbol: str
    is_active: bool

class WatchlistAdd(BaseModel):
    symbol: str

# Глобальные переменные
db_manager = None
bybit_client = None
alert_manager = None
price_filter = None
telegram_bot = None

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        try:
            await websocket.send_text(message)
        except:
            self.disconnect(websocket)

    async def broadcast(self, message: str):
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except:
                disconnected.append(connection)
        
        # Удаляем отключенные соединения
        for conn in disconnected:
            self.disconnect(conn)

    async def broadcast_json(self, data: dict):
        """Отправка JSON данных всем подключенным клиентам"""
        message = json.dumps(data, default=str)
        await self.broadcast(message)

manager = ConnectionManager()

@app.on_event("startup")
async def startup_event():
    global db_manager, bybit_client, alert_manager, price_filter, telegram_bot
    
    try:
        # Инициализация базы данных
        db_manager = DatabaseManager()
        await db_manager.initialize()
        
        # Инициализация Telegram бота
        telegram_bot = TelegramBot()
        
        # Инициализация менеджера алертов
        alert_manager = AlertManager(db_manager, telegram_bot, manager)
        
        # Инициализация фильтра цен
        price_filter = PriceFilter(db_manager)
        
        # Запуск фильтра цен в фоновом режиме
        asyncio.create_task(price_filter.start())
        
        # Запуск периодической очистки данных
        asyncio.create_task(periodic_cleanup())
        
        # Ждем первоначального обновления watchlist
        await asyncio.sleep(5)
        
        # Получение списка торговых пар
        trading_pairs = await db_manager.get_watchlist()
        logger.info(f"Загружено {len(trading_pairs)} торговых пар")
        
        if trading_pairs:
            # Инициализация Bybit WebSocket клиента
            bybit_client = BybitWebSocketClient(trading_pairs, alert_manager, manager)
            
            # Запуск WebSocket соединения в фоновом режиме
            asyncio.create_task(bybit_client.start())
        else:
            logger.warning("Нет торговых пар в watchlist. Ожидание обновления...")
        
        # Периодическое обновление списка торговых пар
        asyncio.create_task(periodic_watchlist_update())
        
        # Отправляем уведомление о запуске в Telegram
        if telegram_bot.enabled:
            await telegram_bot.send_system_message("Система анализа объемов v2.0 запущена")
        
        logger.info("Приложение успешно запущено")
        
    except Exception as e:
        logger.error(f"Ошибка при запуске приложения: {e}")
        raise

async def periodic_watchlist_update():
    """Периодическое обновление списка торговых пар"""
    global bybit_client
    
    while True:
        try:
            await asyncio.sleep(300)  # Проверяем каждые 5 минут
            
            new_pairs = await db_manager.get_watchlist()
            
            if bybit_client:
                current_pairs = bybit_client.trading_pairs
                if set(new_pairs) != set(current_pairs):
                    logger.info(f"Обновление списка торговых пар: {len(new_pairs)} пар")
                    
                    # Останавливаем текущий клиент
                    await bybit_client.stop()
                    
                    # Создаем новый клиент с обновленным списком
                    bybit_client = BybitWebSocketClient(new_pairs, alert_manager, manager)
                    asyncio.create_task(bybit_client.start())
            elif new_pairs:
                # Если клиента не было, но появились пары
                logger.info(f"Создание WebSocket клиента для {len(new_pairs)} пар")
                bybit_client = BybitWebSocketClient(new_pairs, alert_manager, manager)
                asyncio.create_task(bybit_client.start())
                
        except Exception as e:
            logger.error(f"Ошибка обновления watchlist: {e}")

async def periodic_cleanup():
    """Периодическая очистка старых данных"""
    while True:
        try:
            await asyncio.sleep(3600)  # Каждый час
            
            # Очищаем старые данные в базе
            retention_hours = alert_manager.settings.get('data_retention_hours', 2)
            await db_manager.cleanup_old_data(retention_hours)
            
            # Очищаем кэш в менеджере алертов
            await alert_manager.cleanup_old_data()
            
            logger.info("Периодическая очистка данных завершена")
            
        except Exception as e:
            logger.error(f"Ошибка периодической очистки: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    global bybit_client, price_filter, telegram_bot
    if bybit_client:
        await bybit_client.stop()
    if price_filter:
        await price_filter.stop()
    if telegram_bot and telegram_bot.enabled:
        await telegram_bot.send_system_message("Система анализа объемов остановлена")

@app.get("/", response_class=HTMLResponse)
async def read_root():
    try:
        with open("src/index.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse(content="""
        <!DOCTYPE html>
        <html>
        <head><title>Trading Volume Analyzer v2.0</title></head>
        <body>
            <h1>Trading Volume Analyzer v2.0</h1>
            <p>Обновленная система анализа объемов торговых пар запущена</p>
            <p>WebSocket подключение: ws://localhost:8000/ws</p>
        </body>
        </html>
        """)

@app.get("/api/watchlist")
async def get_watchlist():
    """Получить список торговых пар из watchlist"""
    try:
        pairs = await db_manager.get_watchlist_details()
        return {"pairs": pairs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/watchlist")
async def add_to_watchlist(item: WatchlistAdd):
    """Добавить пару в watchlist"""
    try:
        await db_manager.add_to_watchlist(item.symbol)
        await manager.broadcast_json({
            "type": "watchlist_updated",
            "action": "added",
            "symbol": item.symbol
        })
        return {"status": "success", "message": f"Пара {item.symbol} добавлена"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/watchlist/{item_id}")
async def update_watchlist_item(item_id: int, item: WatchlistUpdate):
    """Обновить элемент watchlist"""
    try:
        await db_manager.update_watchlist_item(item_id, item.symbol, item.is_active)
        await manager.broadcast_json({
            "type": "watchlist_updated",
            "action": "updated",
            "item": item.dict()
        })
        return {"status": "success", "message": "Элемент обновлен"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/watchlist/{item_id}")
async def delete_watchlist_item(item_id: int):
    """Удалить элемент из watchlist"""
    try:
        await db_manager.remove_from_watchlist(item_id=item_id)
        await manager.broadcast_json({
            "type": "watchlist_updated",
            "action": "deleted",
            "item_id": item_id
        })
        return {"status": "success", "message": "Элемент удален"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/alerts/all")
async def get_all_alerts():
    """Получить все алерты, разделенные по типам"""
    try:
        alerts_data = await db_manager.get_all_alerts()
        return alerts_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/alerts/{alert_type}")
async def get_alerts_by_type(alert_type: str, limit: int = 50):
    """Получить алерты по типу"""
    try:
        alerts = await db_manager.get_alerts_by_type(alert_type, limit)
        return {"alerts": alerts}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/alerts/clear/{alert_type}")
async def clear_alerts_by_type(alert_type: str):
    """Очистить алерты по типу"""
    try:
        await db_manager.clear_alerts(alert_type)
        await manager.broadcast_json({
            "type": "alerts_cleared",
            "alert_type": alert_type
        })
        return {"status": "success", "message": f"Алерты типа {alert_type} очищены"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/alerts/clear")
async def clear_all_alerts():
    """Очистить все алерты"""
    try:
        await db_manager.clear_alerts()
        await manager.broadcast_json({
            "type": "alerts_cleared"
        })
        return {"status": "success", "message": "Все алерты очищены"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/chart-data/{symbol}")
async def get_chart_data(symbol: str, hours: int = 1, alert_time: str = None):
    """Получить данные для построения графика"""
    try:
        chart_data = await db_manager.get_chart_data(symbol, hours, alert_time)
        return {"chart_data": chart_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/settings")
async def get_settings():
    """Получить текущие настройки анализатора"""
    if alert_manager and price_filter:
        return {
            "volume_analyzer": alert_manager.get_settings(),
            "price_filter": price_filter.settings,
            "alerts": {
                "volume_alerts_enabled": alert_manager.settings.get('volume_alerts_enabled', True),
                "consecutive_alerts_enabled": alert_manager.settings.get('consecutive_alerts_enabled', True),
                "priority_alerts_enabled": alert_manager.settings.get('priority_alerts_enabled', True)
            },
            "telegram": {
                "enabled": telegram_bot.enabled if telegram_bot else False
            }
        }
    return {"error": "Анализатор не инициализирован"}

@app.post("/api/settings")
async def update_settings(settings: dict):
    """Обновить настройки анализатора"""
    try:
        if alert_manager and 'volume_analyzer' in settings:
            alert_manager.update_settings(settings['volume_analyzer'])
        
        if alert_manager and 'alerts' in settings:
            alert_manager.update_settings(settings['alerts'])
        
        if price_filter and 'price_filter' in settings:
            price_filter.update_settings(settings['price_filter'])
            
        await manager.broadcast_json({
            "type": "settings_updated",
            "data": settings
        })
        return {"status": "success", "settings": settings}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stats")
async def get_stats():
    """Получить статистику работы"""
    try:
        if alert_manager:
            # Получаем базовую статистику
            stats = await alert_manager.get_stats() if hasattr(alert_manager, 'get_stats') else {}
            
            # Добавляем количество пар
            watchlist_count = len(await db_manager.get_watchlist())
            stats['pairs_count'] = watchlist_count
            
            # Получаем статистику алертов из базы данных
            all_alerts = await db_manager.get_all_alerts(limit=1000)
            stats['alerts_count'] = len([a for a in all_alerts['alerts'] if a['alert_type'] == 'volume_spike'])
            stats['consecutive_alerts_count'] = len([a for a in all_alerts['alerts'] if a['alert_type'] == 'consecutive_long'])
            stats['priority_alerts_count'] = len([a for a in all_alerts['alerts'] if a['alert_type'] == 'priority'])
            
            # Статистика свечей (примерная)
            stats['total_candles'] = stats.get('total_candles', 0)
            stats['long_candles'] = stats.get('long_candles', 0)
            stats['last_update'] = datetime.now().isoformat()
            
            return stats
        return {"error": "Анализатор не инициализирован"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Ожидаем сообщения от клиента
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message.get("type") == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket ошибка: {e}")
        manager.disconnect(websocket)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app", 
        host=os.getenv('SERVER_HOST', '0.0.0.0'), 
        port=int(os.getenv('SERVER_PORT', 8000)), 
        reload=True,
        log_level="info"
    )