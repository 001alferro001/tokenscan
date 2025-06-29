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
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
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