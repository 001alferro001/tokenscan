import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import List, Dict, Optional
from datetime import datetime, timedelta, timezone

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
from trading_api import BybitTradingAPI
from social_sentiment import SocialSentimentAnalyzer

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
trading_api = None
social_analyzer = None


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


# Модели данных
class WatchlistAdd(BaseModel):
    symbol: str


class WatchlistUpdate(BaseModel):
    id: int
    symbol: str
    is_active: bool


class FavoriteAdd(BaseModel):
    symbol: str
    notes: Optional[str] = None
    color: Optional[str] = '#FFD700'


class FavoriteUpdate(BaseModel):
    notes: Optional[str] = None
    color: Optional[str] = None
    sort_order: Optional[int] = None


class FavoriteReorder(BaseModel):
    symbol_order: List[str]


class PaperTradeCreate(BaseModel):
    symbol: str
    trade_type: str  # 'LONG' or 'SHORT'
    entry_price: float
    quantity: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    risk_amount: Optional[float] = None
    risk_percentage: Optional[float] = None
    notes: Optional[str] = None
    alert_id: Optional[int] = None


class PaperTradeClose(BaseModel):
    exit_price: float
    exit_reason: Optional[str] = 'MANUAL'


class RealTradeCreate(BaseModel):
    symbol: str
    trade_type: str  # 'LONG' or 'SHORT'
    entry_price: float
    quantity: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    risk_amount: Optional[float] = None
    risk_percentage: Optional[float] = None
    notes: Optional[str] = None
    alert_id: Optional[int] = None
    leverage: Optional[int] = 1
    margin_type: Optional[str] = 'isolated'


class RealTradeClose(BaseModel):
    exit_price: float
    exit_reason: Optional[str] = 'MANUAL'


class TradingSettingsUpdate(BaseModel):
    account_balance: Optional[float] = None
    max_risk_per_trade: Optional[float] = None
    max_open_trades: Optional[int] = None
    default_stop_loss_percentage: Optional[float] = None
    default_take_profit_percentage: Optional[float] = None
    auto_calculate_quantity: Optional[bool] = None
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    enable_real_trading: Optional[bool] = None
    default_leverage: Optional[int] = None
    default_margin_type: Optional[str] = None
    confirm_trades: Optional[bool] = None


class RiskCalculatorRequest(BaseModel):
    entry_price: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    risk_amount: Optional[float] = None
    risk_percentage: Optional[float] = None
    account_balance: Optional[float] = None
    trade_type: str = 'LONG'
    leverage: Optional[int] = 1


class ApiConnectionTest(BaseModel):
    api_key: str
    api_secret: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global db_manager, alert_manager, bybit_client, price_filter, telegram_bot, time_sync, trading_api, social_analyzer

    try:
        logger.info("Запуск системы анализа объемов...")

        # Инициализация синхронизации времени с биржей
        time_sync = ExchangeTimeSync()
        await time_sync.start()
        logger.info("Синхронизация времени с биржей запущена")

        # Инициализация базы данных
        db_manager = DatabaseManager()
        await db_manager.initialize()

        # Инициализация Telegram бота
        telegram_bot = TelegramBot()

        # Инициализация менеджера алертов С синхронизацией времени
        alert_manager = AlertManager(db_manager, telegram_bot, manager, time_sync)

        # Инициализация фильтра цен
        price_filter = PriceFilter(db_manager)

        # Инициализация API для торговли
        trading_settings = await db_manager.get_trading_settings()
        trading_api = BybitTradingAPI(
            api_key=trading_settings.get('api_key'),
            api_secret=trading_settings.get('api_secret')
        )

        # Инициализация анализатора социальных настроений
        social_analyzer = SocialSentimentAnalyzer(db_manager)
        await social_analyzer.start()
        logger.info("Анализатор социальных настроений запущен")

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

            # Запуск периодического обновления социальных рейтингов
            asyncio.create_task(periodic_social_update())

            logger.info("Система успешно запущена с синхронизацией времени!")
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
    if social_analyzer:
        await social_analyzer.stop()
    if db_manager:
        db_manager.close()


app = FastAPI(title="Trading Volume Analyzer", lifespan=lifespan)


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


async def periodic_social_update():
    """Периодическое обновление социальных рейтингов"""
    while True:
        try:
            await asyncio.sleep(1800)  # Каждые 30 минут
            if social_analyzer and db_manager:
                # Получаем список активных торговых пар
                trading_pairs = await db_manager.get_watchlist()
                if trading_pairs:
                    logger.info(f"Обновление социальных рейтингов для {len(trading_pairs)} пар")
                    # Обновляем рейтинги для всех пар
                    await social_analyzer.get_ratings_for_symbols(trading_pairs[:20])  # Ограничиваем 20 парами
                    logger.info("Обновление социальных рейтингов завершено")
        except Exception as e:
            logger.error(f"Ошибка обновления социальных рейтингов: {e}")


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
        favorites = await db_manager.get_favorites()
        trading_stats = await db_manager.get_trading_statistics()
        real_trading_stats = await db_manager.get_real_trading_statistics()

        # Добавляем информацию о синхронизации времени
        time_sync_info = {}
        if time_sync:
            time_sync_info = time_sync.get_sync_status()

        return {
            "pairs_count": len(watchlist),
            "favorites_count": len(favorites),
            "alerts_count": len(alerts_data.get('alerts', [])),
            "volume_alerts_count": len(alerts_data.get('volume_alerts', [])),
            "consecutive_alerts_count": len(alerts_data.get('consecutive_alerts', [])),
            "priority_alerts_count": len(alerts_data.get('priority_alerts', [])),
            "trading_stats": trading_stats,
            "real_trading_stats": real_trading_stats,
            "last_update": datetime.now(timezone.utc).isoformat(),
            "system_status": "running",
            "time_sync": time_sync_info
        }
    except Exception as e:
        logger.error(f"Ошибка получения статистики: {e}")
        return {"error": str(e)}


@app.get("/api/social-ratings")
async def get_social_ratings(symbols: Optional[str] = None):
    """Получить социальные рейтинги для торговых пар"""
    try:
        if not social_analyzer:
            return {"error": "Social analyzer not initialized"}

        if symbols:
            # Получаем рейтинги для конкретных символов
            symbol_list = [s.strip().upper() for s in symbols.split(',')]
            ratings = await social_analyzer.get_ratings_for_symbols(symbol_list)
        else:
            # Получаем рейтинги для всех активных пар
            watchlist = await db_manager.get_watchlist()
            ratings = await social_analyzer.get_ratings_for_symbols(watchlist[:20])

        # Преобразуем в формат для API
        formatted_ratings = {}
        for symbol, rating in ratings.items():
            formatted_ratings[symbol] = {
                'overall_score': rating.overall_score,
                'mention_count': rating.mention_count,
                'positive_mentions': rating.positive_mentions,
                'negative_mentions': rating.negative_mentions,
                'neutral_mentions': rating.neutral_mentions,
                'trending_score': rating.trending_score,
                'volume_score': rating.volume_score,
                'sentiment_trend': rating.sentiment_trend,
                'last_updated': rating.last_updated.isoformat(),
                'rating_emoji': social_analyzer.get_rating_emoji(rating.overall_score),
                'trend_emoji': social_analyzer.get_trend_emoji(rating.sentiment_trend),
                'top_mentions': [
                    {
                        'platform': mention.platform,
                        'text': mention.text[:100] + '...' if len(mention.text) > 100 else mention.text,
                        'author': mention.author,
                        'engagement': mention.engagement,
                        'sentiment_score': mention.sentiment_score,
                        'timestamp': mention.timestamp.isoformat()
                    }
                    for mention in rating.top_mentions[:3]
                ]
            }

        return {"ratings": formatted_ratings}

    except Exception as e:
        logger.error(f"Ошибка получения социальных рейтингов: {e}")
        return {"error": str(e)}


@app.get("/api/social-rating/{symbol}")
async def get_symbol_social_rating(symbol: str):
    """Получить детальный социальный рейтинг для конкретной торговой пары"""
    try:
        if not social_analyzer:
            return {"error": "Social analyzer not initialized"}

        rating = await social_analyzer.get_symbol_rating(symbol.upper())
        
        if not rating:
            return {"error": f"No rating data available for {symbol}"}

        return {
            "symbol": rating.symbol,
            "overall_score": rating.overall_score,
            "mention_count": rating.mention_count,
            "positive_mentions": rating.positive_mentions,
            "negative_mentions": rating.negative_mentions,
            "neutral_mentions": rating.neutral_mentions,
            "trending_score": rating.trending_score,
            "volume_score": rating.volume_score,
            "sentiment_trend": rating.sentiment_trend,
            "last_updated": rating.last_updated.isoformat(),
            "rating_emoji": social_analyzer.get_rating_emoji(rating.overall_score),
            "trend_emoji": social_analyzer.get_trend_emoji(rating.sentiment_trend),
            "top_mentions": [
                {
                    'platform': mention.platform,
                    'text': mention.text,
                    'author': mention.author,
                    'engagement': mention.engagement,
                    'sentiment_score': mention.sentiment_score,
                    'confidence': mention.confidence,
                    'timestamp': mention.timestamp.isoformat(),
                    'url': mention.url
                }
                for mention in rating.top_mentions
            ]
        }

    except Exception as e:
        logger.error(f"Ошибка получения рейтинга для {symbol}: {e}")
        return {"error": str(e)}


@app.get("/api/time")
async def get_time_info():
    """Получить информацию о времени биржи"""
    try:
        if time_sync and time_sync.get_sync_status()['is_synced']:
            # Возвращаем синхронизированное UTC время
            sync_status = time_sync.get_sync_status()
            logger.info(
                f"API /api/time: Возвращаем синхронизированное UTC время. serverTime={sync_status['serverTime']}")
            return sync_status
        else:
            # Fallback на локальное UTC время
            current_time_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
            fallback_response = {
                "is_synced": False,
                "serverTime": current_time_ms,  # Ключевое поле для клиента
                "local_time": datetime.now(timezone.utc).isoformat(),
                "utc_time": datetime.now(timezone.utc).isoformat(),
                "time_offset_ms": 0,
                "status": "not_synced"
            }
            logger.warning(
                f"API /api/time: Синхронизация недоступна, возвращаем fallback. serverTime={current_time_ms}")
            return fallback_response
    except Exception as e:
        logger.error(f"Ошибка получения информации о времени: {e}")
        # Аварийный fallback
        current_time_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        return {
            "is_synced": False,
            "serverTime": current_time_ms,
            "local_time": datetime.now(timezone.utc).isoformat(),
            "utc_time": datetime.now(timezone.utc).isoformat(),
            "time_offset_ms": 0,
            "status": "error",
            "error": str(e)
        }


@app.get("/api/alerts/symbol/{symbol}")
async def get_alerts_by_symbol(symbol: str, hours: int = 24):
    """Получить все алерты для конкретного символа за указанный период"""
    try:
        # Получаем все алерты
        all_alerts_data = await db_manager.get_all_alerts(limit=1000)
        
        # Объединяем все типы алертов
        all_alerts = [
            *all_alerts_data.get('volume_alerts', []),
            *all_alerts_data.get('consecutive_alerts', []),
            *all_alerts_data.get('priority_alerts', [])
        ]
        
        # Фильтруем по символу и времени
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
        cutoff_timestamp_ms = int(cutoff_time.timestamp() * 1000)
        
        symbol_alerts = []
        for alert in all_alerts:
            if alert['symbol'] == symbol:
                # Проверяем время алерта
                alert_time_ms = None
                if 'alert_timestamp_ms' in alert and alert['alert_timestamp_ms']:
                    alert_time_ms = alert['alert_timestamp_ms']
                elif 'timestamp' in alert:
                    if isinstance(alert['timestamp'], str):
                        try:
                            alert_time_ms = int(datetime.fromisoformat(alert['timestamp'].replace('Z', '+00:00')).timestamp() * 1000)
                        except:
                            continue
                    else:
                        alert_time_ms = int(alert['timestamp'])
                
                if alert_time_ms and alert_time_ms > cutoff_timestamp_ms:
                    symbol_alerts.append(alert)
        
        # Сортируем по времени
        symbol_alerts.sort(key=lambda x: x.get('alert_timestamp_ms', 0))
        
        return {
            "symbol": symbol,
            "alerts": symbol_alerts,
            "count": len(symbol_alerts),
            "period_hours": hours
        }
        
    except Exception as e:
        logger.error(f"Ошибка получения алертов для символа {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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


# API для избранного
@app.get("/api/favorites")
async def get_favorites():
    """Получить список избранных торговых пар"""
    try:
        favorites = await db_manager.get_favorites()
        return {"favorites": favorites}
    except Exception as e:
        logger.error(f"Ошибка получения избранного: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/favorites")
async def add_to_favorites(item: FavoriteAdd):
    """Добавить торговую пару в избранное"""
    try:
        await db_manager.add_to_favorites(item.symbol, item.notes, item.color)

        # Уведомляем клиентов об обновлении
        await manager.broadcast_json({
            "type": "favorites_updated",
            "action": "added",
            "symbol": item.symbol
        })

        return {"status": "success", "symbol": item.symbol}
    except Exception as e:
        logger.error(f"Ошибка добавления в избранное: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/favorites/{symbol}")
async def remove_from_favorites(symbol: str):
    """Удалить торговую пару из избранного"""
    try:
        await db_manager.remove_from_favorites(symbol)

        # Уведомляем клиентов об обновлении
        await manager.broadcast_json({
            "type": "favorites_updated",
            "action": "removed",
            "symbol": symbol
        })

        return {"status": "success"}
    except Exception as e:
        logger.error(f"Ошибка удаления из избранного: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/favorites/{symbol}")
async def update_favorite(symbol: str, item: FavoriteUpdate):
    """Обновить информацию об избранной паре"""
    try:
        await db_manager.update_favorite(symbol, item.notes, item.color, item.sort_order)

        # Уведомляем клиентов об обновлении
        await manager.broadcast_json({
            "type": "favorites_updated",
            "action": "updated",
            "symbol": symbol
        })

        return {"status": "success"}
    except Exception as e:
        logger.error(f"Ошибка обновления избранной пары: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/favorites/reorder")
async def reorder_favorites(item: FavoriteReorder):
    """Изменить порядок избранных пар"""
    try:
        await db_manager.reorder_favorites(item.symbol_order)

        # Уведомляем клиентов об обновлении
        await manager.broadcast_json({
            "type": "favorites_updated",
            "action": "reordered",
            "symbol_order": item.symbol_order
        })

        return {"status": "success"}
    except Exception as e:
        logger.error(f"Ошибка изменения порядка избранных пар: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# API для бумажной торговли
@app.get("/api/trading/settings")
async def get_trading_settings():
    """Получить настройки торговли"""
    try:
        settings = await db_manager.get_trading_settings()
        
        # Скрываем API секрет в ответе
        if 'api_secret' in settings:
            settings['api_secret'] = '********' if settings['api_secret'] else None
            
        return {"settings": settings}
    except Exception as e:
        logger.error(f"Ошибка получения настроек торговли: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/trading/settings")
async def update_trading_settings(settings: TradingSettingsUpdate):
    """Обновить настройки торговли"""
    try:
        settings_dict = settings.dict(exclude_unset=True)
        
        # Обновляем настройки в базе данных
        success = await db_manager.update_trading_settings(settings_dict)
        
        # Обновляем API клиент, если изменились ключи
        global trading_api
        if 'api_key' in settings_dict or 'api_secret' in settings_dict:
            # Получаем полные настройки
            full_settings = await db_manager.get_trading_settings()
            trading_api = BybitTradingAPI(
                api_key=full_settings.get('api_key'),
                api_secret=full_settings.get('api_secret')
            )
        
        if success:
            return {"status": "success"}
        else:
            raise HTTPException(status_code=500, detail="Не удалось обновить настройки")
    except Exception as e:
        logger.error(f"Ошибка обновления настроек торговли: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/trading/test-connection")
async def test_api_connection(data: ApiConnectionTest):
    """Проверка подключения к API биржи"""
    try:
        # Создаем временный экземпляр API клиента
        temp_api = BybitTradingAPI(api_key=data.api_key, api_secret=data.api_secret)
        
        # Проверяем подключение
        result = temp_api.test_connection()
        
        if result.get('success'):
            return {
                "status": "success",
                "balance": result.get('balance', 0),
                "available_balance": result.get('available_balance', 0)
            }
        else:
            raise HTTPException(status_code=400, detail=result.get('error', 'Ошибка подключения к API'))
    except Exception as e:
        logger.error(f"Ошибка проверки API подключения: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/trading/calculate-risk")
async def calculate_risk(request: RiskCalculatorRequest):
    """Калькулятор риска и прибыли"""
    try:
        # Получаем настройки торговли
        settings = await db_manager.get_trading_settings()
        account_balance = request.account_balance or settings.get('account_balance', 10000)
        
        # Базовые расчеты
        entry_price = request.entry_price
        stop_loss = request.stop_loss
        take_profit = request.take_profit
        trade_type = request.trade_type.upper()
        leverage = request.leverage or 1
        
        result = {
            'entry_price': entry_price,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'trade_type': trade_type,
            'account_balance': account_balance,
            'leverage': leverage
        }
        
        # Если указан риск в деньгах
        if request.risk_amount:
            risk_amount = request.risk_amount
            risk_percentage = (risk_amount / account_balance) * 100
        # Если указан риск в процентах
        elif request.risk_percentage:
            risk_percentage = request.risk_percentage
            risk_amount = (account_balance * risk_percentage) / 100
        # Используем настройки по умолчанию
        else:
            risk_percentage = settings.get('max_risk_per_trade', 2.0)
            risk_amount = (account_balance * risk_percentage) / 100
        
        result.update({
            'risk_amount': round(risk_amount, 2),
            'risk_percentage': round(risk_percentage, 2)
        })
        
        # Рассчитываем количество токенов, если указан стоп-лосс
        if stop_loss:
            if trade_type == 'LONG':
                price_diff = entry_price - stop_loss
            else:  # SHORT
                price_diff = stop_loss - entry_price
            
            if price_diff > 0:
                # Учитываем плечо при расчете количества
                quantity = (risk_amount / price_diff) * leverage
                position_size = quantity * entry_price
                
                result['quantity'] = round(quantity, 8)
                result['position_size'] = round(position_size, 2)
                
                # Рассчитываем потенциальную прибыль, если указан тейк-профит
                if take_profit:
                    if trade_type == 'LONG':
                        profit_diff = take_profit - entry_price
                    else:  # SHORT
                        profit_diff = entry_price - take_profit
                    
                    if profit_diff > 0:
                        potential_profit = quantity * profit_diff
                        result['potential_profit'] = round(potential_profit, 2)
                        result['potential_profit_percentage'] = round((potential_profit / position_size) * 100, 2)
                        result['risk_reward_ratio'] = round(potential_profit / risk_amount, 2)
                
                # Рассчитываем потенциальный убыток
                potential_loss = quantity * price_diff
                result['potential_loss'] = round(potential_loss, 2)
                result['potential_loss_percentage'] = round((potential_loss / position_size) * 100, 2)
            else:
                result['error'] = 'Некорректные уровни стоп-лосса'
        else:
            result['error'] = 'Стоп-лосс не указан'
        
        return result
        
    except Exception as e:
        logger.error(f"Ошибка расчета риска: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/trading/trades")
async def create_paper_trade(trade: PaperTradeCreate):
    """Создать бумажную сделку"""
    try:
        # Автоматически рассчитываем параметры, если не указаны
        settings = await db_manager.get_trading_settings()
        
        trade_data = trade.dict()
        
        # Рассчитываем количество, если не указано
        if not trade_data.get('quantity') and trade_data.get('stop_loss'):
            account_balance = settings.get('account_balance', 10000)
            risk_percentage = trade_data.get('risk_percentage') or settings.get('max_risk_per_trade', 2.0)
            risk_amount = (account_balance * risk_percentage) / 100
            
            entry_price = trade_data['entry_price']
            stop_loss = trade_data['stop_loss']
            
            if trade_data['trade_type'].upper() == 'LONG':
                price_diff = entry_price - stop_loss
            else:
                price_diff = stop_loss - entry_price
            
            if price_diff > 0:
                quantity = risk_amount / price_diff
                trade_data['quantity'] = quantity
                trade_data['risk_amount'] = risk_amount
                trade_data['risk_percentage'] = risk_percentage
                
                # Рассчитываем потенциальную прибыль
                if trade_data.get('take_profit'):
                    take_profit = trade_data['take_profit']
                    if trade_data['trade_type'].upper() == 'LONG':
                        profit_diff = take_profit - entry_price
                    else:
                        profit_diff = entry_price - take_profit
                    
                    if profit_diff > 0:
                        potential_profit = quantity * profit_diff
                        potential_loss = quantity * price_diff
                        trade_data['potential_profit'] = potential_profit
                        trade_data['potential_loss'] = potential_loss
                        trade_data['risk_reward_ratio'] = potential_profit / potential_loss
        
        trade_id = await db_manager.create_paper_trade(trade_data)
        
        if trade_id:
            # Уведомляем клиентов о новой сделке
            await manager.broadcast_json({
                "type": "paper_trade_created",
                "trade_id": trade_id,
                "symbol": trade_data['symbol']
            })
            
            return {"status": "success", "trade_id": trade_id}
        else:
            raise HTTPException(status_code=500, detail="Не удалось создать сделку")
            
    except Exception as e:
        logger.error(f"Ошибка создания бумажной сделки: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/trading/trades")
async def get_paper_trades(status: Optional[str] = None, limit: int = 100):
    """Получить список бумажных сделок"""
    try:
        trades = await db_manager.get_paper_trades(status, limit)
        return {"trades": trades}
    except Exception as e:
        logger.error(f"Ошибка получения бумажных сделок: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/trading/trades/{trade_id}/close")
async def close_paper_trade(trade_id: int, close_data: PaperTradeClose):
    """Закрыть бумажную сделку"""
    try:
        success = await db_manager.close_paper_trade(
            trade_id, 
            close_data.exit_price, 
            close_data.exit_reason
        )
        
        if success:
            # Уведомляем клиентов о закрытии сделки
            await manager.broadcast_json({
                "type": "paper_trade_closed",
                "trade_id": trade_id
            })
            
            return {"status": "success"}
        else:
            raise HTTPException(status_code=404, detail="Сделка не найдена или уже закрыта")
            
    except Exception as e:
        logger.error(f"Ошибка закрытия бумажной сделки: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/trading/statistics")
async def get_trading_statistics():
    """Получить статистику торговли"""
    try:
        stats = await db_manager.get_trading_statistics()
        return {"statistics": stats}
    except Exception as e:
        logger.error(f"Ошибка получения статистики торговли: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# API для реальной торговли
@app.get("/api/trading/account-info")
async def get_account_info():
    """Получить информацию об аккаунте"""
    try:
        if not trading_api or not trading_api.is_configured:
            raise HTTPException(status_code=400, detail="API не настроено")
        
        account_info = trading_api.get_account_info()
        
        if "error" in account_info:
            raise HTTPException(status_code=400, detail=account_info["error"])
        
        return account_info
    except Exception as e:
        logger.error(f"Ошибка получения информации об аккаунте: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/trading/positions")
async def get_positions(symbol: Optional[str] = None):
    """Получить открытые позиции"""
    try:
        if not trading_api or not trading_api.is_configured:
            raise HTTPException(status_code=400, detail="API не настроено")
        
        positions = trading_api.get_positions(symbol)
        
        if "error" in positions:
            raise HTTPException(status_code=400, detail=positions["error"])
        
        return positions
    except Exception as e:
        logger.error(f"Ошибка получения позиций: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/trading/real-trades")
async def create_real_trade(trade: RealTradeCreate):
    """Создать реальную сделку"""
    try:
        # Проверяем, включена ли реальная торговля
        settings = await db_manager.get_trading_settings()
        if not settings.get('enable_real_trading', False):
            raise HTTPException(status_code=400, detail="Реальная торговля отключена в настройках")
        
        if not trading_api or not trading_api.is_configured:
            raise HTTPException(status_code=400, detail="API не настроено")
        
        # Преобразуем тип сделки в формат Bybit
        side = "Buy" if trade.trade_type.upper() == "LONG" else "Sell"
        
        # Размещаем ордер
        order_result = trading_api.place_order(
            symbol=trade.symbol,
            side=side,
            order_type="Market",
            qty=trade.quantity,
            stop_loss=trade.stop_loss,
            take_profit=trade.take_profit,
            leverage=trade.leverage,
            margin_type=trade.margin_type
        )
        
        if "error" in order_result:
            raise HTTPException(status_code=400, detail=order_result["error"])
        
        # Сохраняем сделку в базу данных
        trade_data = trade.dict()
        trade_data["order_id"] = order_result.get("order_id")
        
        trade_id = await db_manager.create_real_trade(trade_data)
        
        if trade_id:
            # Уведомляем клиентов о новой сделке
            await manager.broadcast_json({
                "type": "real_trade_created",
                "trade_id": trade_id,
                "symbol": trade.symbol,
                "order_id": order_result.get("order_id")
            })
            
            return {
                "status": "success", 
                "trade_id": trade_id, 
                "order_id": order_result.get("order_id")
            }
        else:
            raise HTTPException(status_code=500, detail="Не удалось создать сделку в базе данных")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка создания реальной сделки: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/trading/real-trades")
async def get_real_trades(status: Optional[str] = None, limit: int = 100):
    """Получить список реальных сделок"""
    try:
        trades = await db_manager.get_real_trades(status, limit)
        return {"trades": trades}
    except Exception as e:
        logger.error(f"Ошибка получения реальных сделок: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/trading/real-trades/{trade_id}/close")
async def close_real_trade(trade_id: int, close_data: RealTradeClose):
    """Закрыть реальную сделку"""
    try:
        # Проверяем, включена ли реальная торговля
        settings = await db_manager.get_trading_settings()
        if not settings.get('enable_real_trading', False):
            raise HTTPException(status_code=400, detail="Реальная торговля отключена в настройках")
        
        if not trading_api or not trading_api.is_configured:
            raise HTTPException(status_code=400, detail="API не настроено")
        
        # Получаем данные сделки
        cursor = db_manager.connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("""
            SELECT symbol, trade_type
            FROM real_trades
            WHERE id = %s AND status = 'OPEN'
        """, (trade_id,))
        
        trade = cursor.fetchone()
        cursor.close()
        
        if not trade:
            raise HTTPException(status_code=404, detail="Сделка не найдена или уже закрыта")
        
        # Преобразуем тип сделки в формат Bybit для закрытия (противоположный)
        side = "Sell" if trade['trade_type'].upper() == "LONG" else "Buy"
        
        # Закрываем позицию
        close_result = trading_api.close_position(trade['symbol'], side)
        
        if "error" in close_result:
            raise HTTPException(status_code=400, detail=close_result["error"])
        
        # Обновляем сделку в базе данных
        success = await db_manager.close_real_trade(
            trade_id,
            close_data.exit_price,
            close_data.exit_reason
        )
        
        if success:
            # Уведомляем клиентов о закрытии сделки
            await manager.broadcast_json({
                "type": "real_trade_closed",
                "trade_id": trade_id,
                "order_id": close_result.get("order_id")
            })
            
            return {
                "status": "success",
                "order_id": close_result.get("order_id")
            }
        else:
            raise HTTPException(status_code=500, detail="Не удалось обновить сделку в базе данных")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка закрытия реальной сделки: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/trading/real-statistics")
async def get_real_trading_statistics():
    """Получить статистику реальной торговли"""
    try:
        stats = await db_manager.get_real_trading_statistics()
        return {"statistics": stats}
    except Exception as e:
        logger.error(f"Ошибка получения статистики реальной торговли: {e}")
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

        # Логируем временные метки в данных графика
        if chart_data:
            logger.debug(f"API /api/chart-data: Возвращаем {len(chart_data)} свечей для {symbol}. "
                         f"Первая свеча: {chart_data[0]['timestamp'] if chart_data else 'N/A'}, "
                         f"Последняя свеча: {chart_data[-1]['timestamp'] if chart_data else 'N/A'}")

        return {"chart_data": chart_data}
    except Exception as e:
        logger.error(f"Ошибка получения данных графика: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/settings")
async def get_settings():
    """Получить текущие настройки анализатора"""
    if alert_manager and price_filter:
        # Добавляем информацию о синхронизации времени
        time_sync_info = {}
        if time_sync:
            time_sync_info = time_sync.get_sync_status()

        # Получаем настройки торговли
        trading_settings = await db_manager.get_trading_settings()
        
        # Скрываем API секрет в ответе
        if 'api_secret' in trading_settings:
            trading_settings['api_secret'] = '********' if trading_settings['api_secret'] else None

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
            },
            "trading": trading_settings,
            "time_sync": time_sync_info
        }

        return settings

    # Fallback настройки
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
        "trading": {
            "account_balance": 10000,
            "max_risk_per_trade": 2.0,
            "max_open_trades": 5,
            "default_stop_loss_percentage": 2.0,
            "default_take_profit_percentage": 6.0,
            "auto_calculate_quantity": True,
            "enable_real_trading": False,
            "default_leverage": 1,
            "default_margin_type": "isolated",
            "confirm_trades": True
        },
        "time_sync": {
            "is_synced": False,
            "status": "not_initialized"
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
            
        if 'trading' in settings:
            # Обновляем настройки торговли
            await db_manager.update_trading_settings(settings['trading'])
            
            # Обновляем API клиент, если изменились ключи
            global trading_api
            if 'api_key' in settings['trading'] or 'api_secret' in settings['trading']:
                # Получаем полные настройки
                full_settings = await db_manager.get_trading_settings()
                trading_api = BybitTradingAPI(
                    api_key=full_settings.get('api_key'),
                    api_secret=full_settings.get('api_secret')
                )

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