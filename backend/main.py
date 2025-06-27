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