import asyncio
import logging
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()

class DatabaseManager:
    def __init__(self):
        self.connection = None
        self.db_config = {
            'host': os.getenv('DB_HOST', 'localhost'),
            'port': int(os.getenv('DB_PORT', 5432)),
            'database': os.getenv('DB_NAME', 'tradingbase'),
            'user': os.getenv('DB_USER', 'postgres'),
            'password': os.getenv('DB_PASSWORD', 'password')
        }

    async def initialize(self):
        """Инициализация базы данных"""
        try:
            self.connection = psycopg2.connect(**self.db_config)
            self.connection.autocommit = True
            logger.info("✅ Подключение к базе данных установлено")
            
            await self.create_tables()
            logger.info("✅ Таблицы базы данных проверены/созданы")
            
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации базы данных: {e}")
            raise

    async def create_tables(self):
        """Создание таблиц базы данных"""
        try:
            cursor = self.connection.cursor()
            
            # Таблица торговых пар
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS watchlist (
                    id SERIAL PRIMARY KEY,
                    symbol VARCHAR(20) UNIQUE NOT NULL,
                    is_active BOOLEAN DEFAULT TRUE,
                    price_drop_percentage DECIMAL(10,4),
                    current_price DECIMAL(20,8),
                    historical_price DECIMAL(20,8),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Таблица данных свечей с UNIX временем
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS kline_data (
                    id SERIAL PRIMARY KEY,
                    symbol VARCHAR(20) NOT NULL,
                    open_time_unix BIGINT NOT NULL,
                    close_time_unix BIGINT NOT NULL,
                    open_price DECIMAL(20,8) NOT NULL,
                    high_price DECIMAL(20,8) NOT NULL,
                    low_price DECIMAL(20,8) NOT NULL,
                    close_price DECIMAL(20,8) NOT NULL,
                    volume DECIMAL(20,8) NOT NULL,
                    volume_usdt DECIMAL(20,8) NOT NULL,
                    is_long BOOLEAN NOT NULL,
                    is_closed BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(symbol, open_time_unix)
                )
            """)
            
            # Индексы для оптимизации
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_kline_symbol_time 
                ON kline_data(symbol, open_time_unix DESC)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_kline_symbol_closed 
                ON kline_data(symbol, is_closed, open_time_unix DESC)
            """)
            
            # Таблица алертов
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS alerts (
                    id SERIAL PRIMARY KEY,
                    symbol VARCHAR(20) NOT NULL,
                    alert_type VARCHAR(50) NOT NULL,
                    price DECIMAL(20,8) NOT NULL,
                    volume_ratio DECIMAL(10,2),
                    consecutive_count INTEGER,
                    current_volume_usdt DECIMAL(20,2),
                    average_volume_usdt DECIMAL(20,2),
                    is_true_signal BOOLEAN,
                    is_closed BOOLEAN DEFAULT FALSE,
                    has_imbalance BOOLEAN DEFAULT FALSE,
                    imbalance_data JSONB,
                    candle_data JSONB,
                    order_book_snapshot JSONB,
                    message TEXT,
                    timestamp TIMESTAMP NOT NULL,
                    close_timestamp TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_alerts_symbol_type 
                ON alerts(symbol, alert_type, timestamp DESC)
            """)
            
            cursor.close()
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания таблиц: {e}")
            raise

    async def save_kline_data(self, symbol: str, kline_data: Dict, is_closed: bool = False):
        """Сохранение данных свечи с проверкой на дублирование"""
        try:
            cursor = self.connection.cursor()
            
            open_time_unix = int(kline_data['start'])
            close_time_unix = int(kline_data['end'])
            open_price = float(kline_data['open'])
            high_price = float(kline_data['high'])
            low_price = float(kline_data['low'])
            close_price = float(kline_data['close'])
            volume = float(kline_data['volume'])
            volume_usdt = volume * close_price
            is_long = close_price > open_price
            
            # Используем ON CONFLICT для избежания дублирования
            cursor.execute("""
                INSERT INTO kline_data (
                    symbol, open_time_unix, close_time_unix, open_price, high_price, 
                    low_price, close_price, volume, volume_usdt, is_long, is_closed
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (symbol, open_time_unix) 
                DO UPDATE SET
                    close_time_unix = EXCLUDED.close_time_unix,
                    high_price = EXCLUDED.high_price,
                    low_price = EXCLUDED.low_price,
                    close_price = EXCLUDED.close_price,
                    volume = EXCLUDED.volume,
                    volume_usdt = EXCLUDED.volume_usdt,
                    is_long = EXCLUDED.is_long,
                    is_closed = EXCLUDED.is_closed
            """, (symbol, open_time_unix, close_time_unix, open_price, high_price, 
                  low_price, close_price, volume, volume_usdt, is_long, is_closed))
            
            cursor.close()
            
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения данных свечи для {symbol}: {e}")

    async def get_missing_data_summary(self, symbols: List[str], hours: int) -> Dict:
        """Получение сводки по недостающим данным для всех символов"""
        try:
            cursor = self.connection.cursor(cursor_factory=RealDictCursor)
            
            # Рассчитываем временные границы
            end_time_unix = int(datetime.utcnow().timestamp() * 1000)
            start_time_unix = end_time_unix - (hours * 60 * 60 * 1000)
            expected_candles = hours * 60  # Ожидаемое количество свечей
            
            symbols_details = []
            quality_distribution = {'excellent': 0, 'good': 0, 'fair': 0, 'poor': 0, 'critical': 0}
            
            for symbol in symbols:
                # Получаем статистику по символу
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_candles,
                        MIN(open_time_unix) as first_candle,
                        MAX(open_time_unix) as last_candle,
                        COUNT(CASE WHEN is_closed = true THEN 1 END) as closed_candles
                    FROM kline_data 
                    WHERE symbol = %s 
                    AND open_time_unix >= %s 
                    AND open_time_unix < %s
                """, (symbol, start_time_unix, end_time_unix))
                
                result = cursor.fetchone()
                total_existing = result['total_candles'] or 0
                first_candle = result['first_candle']
                last_candle = result['last_candle']
                closed_candles = result['closed_candles'] or 0
                
                # Рассчитываем качество данных
                integrity_percentage = (total_existing / expected_candles * 100) if expected_candles > 0 else 0
                
                # Определяем качество
                if integrity_percentage >= 95:
                    quality = 'excellent'
                elif integrity_percentage >= 85:
                    quality = 'good'
                elif integrity_percentage >= 70:
                    quality = 'fair'
                elif integrity_percentage >= 50:
                    quality = 'poor'
                else:
                    quality = 'critical'
                
                quality_distribution[quality] += 1
                
                # Определяем, нужна ли загрузка
                needs_loading = integrity_percentage < 80 or total_existing < 60
                
                # Находим пропуски
                missing_ranges = []
                if total_existing > 0:
                    missing_ranges = await self._find_missing_ranges(symbol, start_time_unix, end_time_unix)
                
                symbols_details.append({
                    'symbol': symbol,
                    'total_existing': total_existing,
                    'total_expected': expected_candles,
                    'integrity_percentage': integrity_percentage,
                    'quality': quality,
                    'needs_loading': needs_loading,
                    'first_candle': first_candle,
                    'last_candle': last_candle,
                    'closed_candles': closed_candles,
                    'missing_ranges': missing_ranges,
                    'missing_count': len(missing_ranges)
                })
            
            cursor.close()
            
            # Подсчитываем сводку
            symbols_with_good_data = sum(1 for s in symbols_details if not s['needs_loading'])
            symbols_need_loading = sum(1 for s in symbols_details if s['needs_loading'])
            
            return {
                'total_symbols': len(symbols),
                'symbols_with_good_data': symbols_with_good_data,
                'symbols_need_loading': symbols_need_loading,
                'quality_distribution': quality_distribution,
                'symbols_details': symbols_details
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения сводки по данным: {e}")
            return {
                'total_symbols': len(symbols),
                'symbols_with_good_data': 0,
                'symbols_need_loading': len(symbols),
                'quality_distribution': {'critical': len(symbols)},
                'symbols_details': []
            }

    async def _find_missing_ranges(self, symbol: str, start_time_unix: int, end_time_unix: int) -> List[Dict]:
        """Поиск пропущенных диапазонов данных"""
        try:
            cursor = self.connection.cursor()
            
            # Получаем все существующие временные метки
            cursor.execute("""
                SELECT open_time_unix 
                FROM kline_data 
                WHERE symbol = %s 
                AND open_time_unix >= %s 
                AND open_time_unix < %s
                ORDER BY open_time_unix
            """, (symbol, start_time_unix, end_time_unix))
            
            existing_times = [row[0] for row in cursor.fetchall()]
            cursor.close()
            
            if not existing_times:
                # Нет данных вообще
                return [{
                    'start_unix': start_time_unix,
                    'end_unix': end_time_unix,
                    'duration_minutes': (end_time_unix - start_time_unix) // 60000
                }]
            
            missing_ranges = []
            
            # Проверяем начало
            if existing_times[0] > start_time_unix:
                missing_ranges.append({
                    'start_unix': start_time_unix,
                    'end_unix': existing_times[0],
                    'duration_minutes': (existing_times[0] - start_time_unix) // 60000
                })
            
            # Проверяем пропуски между существующими данными
            for i in range(len(existing_times) - 1):
                current_time = existing_times[i]
                next_time = existing_times[i + 1]
                expected_next = current_time + 60000  # Следующая минута
                
                if next_time > expected_next:
                    missing_ranges.append({
                        'start_unix': expected_next,
                        'end_unix': next_time,
                        'duration_minutes': (next_time - expected_next) // 60000
                    })
            
            # Проверяем конец
            if existing_times[-1] < end_time_unix - 60000:
                missing_ranges.append({
                    'start_unix': existing_times[-1] + 60000,
                    'end_unix': end_time_unix,
                    'duration_minutes': (end_time_unix - existing_times[-1] - 60000) // 60000
                })
            
            return missing_ranges
            
        except Exception as e:
            logger.error(f"❌ Ошибка поиска пропущенных диапазонов для {symbol}: {e}")
            return []

    async def optimize_missing_data_loading(self, symbol: str, hours: int) -> List[Dict]:
        """Оптимизация загрузки недостающих данных"""
        try:
            end_time_unix = int(datetime.utcnow().timestamp() * 1000)
            start_time_unix = end_time_unix - (hours * 60 * 60 * 1000)
            
            missing_ranges = await self._find_missing_ranges(symbol, start_time_unix, end_time_unix)
            
            # Объединяем близкие диапазоны для оптимизации
            optimized_ranges = []
            if missing_ranges:
                current_range = missing_ranges[0].copy()
                
                for next_range in missing_ranges[1:]:
                    # Если диапазоны близко (меньше 10 минут), объединяем
                    if next_range['start_unix'] - current_range['end_unix'] <= 10 * 60000:
                        current_range['end_unix'] = next_range['end_unix']
                        current_range['duration_minutes'] = (current_range['end_unix'] - current_range['start_unix']) // 60000
                    else:
                        optimized_ranges.append(current_range)
                        current_range = next_range.copy()
                
                optimized_ranges.append(current_range)
            
            return optimized_ranges
            
        except Exception as e:
            logger.error(f"❌ Ошибка оптимизации загрузки для {symbol}: {e}")
            return []

    async def get_symbol_data_info(self, symbol: str, hours: int) -> Dict:
        """Получение детальной информации о данных символа"""
        try:
            cursor = self.connection.cursor(cursor_factory=RealDictCursor)
            
            # Рассчитываем временные границы
            end_time_unix = int(datetime.utcnow().timestamp() * 1000)
            start_time_unix = end_time_unix - (hours * 60 * 60 * 1000)
            expected_candles = hours * 60
            
            # Получаем общую статистику
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_candles,
                    MIN(open_time_unix) as first_candle_unix,
                    MAX(open_time_unix) as last_candle_unix,
                    COUNT(CASE WHEN is_closed = true THEN 1 END) as closed_candles
                FROM kline_data 
                WHERE symbol = %s 
                AND open_time_unix >= %s 
                AND open_time_unix < %s
            """, (symbol, start_time_unix, end_time_unix))
            
            result = cursor.fetchone()
            total_existing = result['total_candles'] or 0
            first_candle_unix = result['first_candle_unix']
            last_candle_unix = result['last_candle_unix']
            closed_candles = result['closed_candles'] or 0
            
            # Находим пропуски
            missing_ranges = await self._find_missing_ranges(symbol, start_time_unix, end_time_unix)
            
            # Рассчитываем качество данных
            integrity_percentage = (total_existing / expected_candles * 100) if expected_candles > 0 else 0
            
            # Определяем качество
            if integrity_percentage >= 95:
                quality = 'excellent'
                quality_text = 'Отличное'
            elif integrity_percentage >= 85:
                quality = 'good'
                quality_text = 'Хорошее'
            elif integrity_percentage >= 70:
                quality = 'fair'
                quality_text = 'Удовлетворительное'
            elif integrity_percentage >= 50:
                quality = 'poor'
                quality_text = 'Плохое'
            else:
                quality = 'critical'
                quality_text = 'Критическое'
            
            cursor.close()
            
            return {
                'symbol': symbol,
                'total_candles': total_existing,
                'expected_candles': expected_candles,
                'closed_candles': closed_candles,
                'integrity_percentage': round(integrity_percentage, 1),
                'quality': quality,
                'quality_text': quality_text,
                'first_candle_unix': first_candle_unix,
                'last_candle_unix': last_candle_unix,
                'first_candle_time': datetime.fromtimestamp(first_candle_unix / 1000).isoformat() if first_candle_unix else None,
                'last_candle_time': datetime.fromtimestamp(last_candle_unix / 1000).isoformat() if last_candle_unix else None,
                'missing_ranges': missing_ranges,
                'missing_count': len(missing_ranges),
                'has_gaps': len(missing_ranges) > 0
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения информации о данных для {symbol}: {e}")
            return {
                'symbol': symbol,
                'total_candles': 0,
                'expected_candles': expected_candles,
                'closed_candles': 0,
                'integrity_percentage': 0,
                'quality': 'critical',
                'quality_text': 'Критическое',
                'first_candle_unix': None,
                'last_candle_unix': None,
                'first_candle_time': None,
                'last_candle_time': None,
                'missing_ranges': [],
                'missing_count': 0,
                'has_gaps': False
            }

    async def check_data_integrity(self, symbol: str, hours: int) -> Dict:
        """Проверка целостности данных для символа"""
        return await self.get_symbol_data_info(symbol, hours)

    async def get_watchlist(self) -> List[str]:
        """Получение списка активных торговых пар"""
        try:
            cursor = self.connection.cursor()
            cursor.execute("SELECT symbol FROM watchlist WHERE is_active = TRUE ORDER BY symbol")
            symbols = [row[0] for row in cursor.fetchall()]
            cursor.close()
            return symbols
        except Exception as e:
            logger.error(f"❌ Ошибка получения watchlist: {e}")
            return []

    async def get_watchlist_details(self) -> List[Dict]:
        """Получение детального списка торговых пар с информацией о данных"""
        try:
            cursor = self.connection.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT id, symbol, is_active, price_drop_percentage, 
                       current_price, historical_price, created_at, updated_at
                FROM watchlist 
                ORDER BY price_drop_percentage DESC NULLS LAST, symbol
            """)
            
            pairs = cursor.fetchall()
            cursor.close()
            
            # Добавляем информацию о данных для каждой пары
            retention_hours = 2  # Можно получить из настроек
            analysis_hours = 1
            total_hours = retention_hours + analysis_hours + 1
            
            enriched_pairs = []
            for pair in pairs:
                pair_dict = dict(pair)
                
                # Получаем информацию о данных
                data_info = await self.get_symbol_data_info(pair['symbol'], total_hours)
                pair_dict['data_info'] = data_info
                
                enriched_pairs.append(pair_dict)
            
            return enriched_pairs
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения детального watchlist: {e}")
            return []

    async def add_to_watchlist(self, symbol: str, price_drop: float = None, 
                             current_price: float = None, historical_price: float = None):
        """Добавление торговой пары в watchlist"""
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                INSERT INTO watchlist (symbol, price_drop_percentage, current_price, historical_price, updated_at)
                VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (symbol) 
                DO UPDATE SET 
                    price_drop_percentage = EXCLUDED.price_drop_percentage,
                    current_price = EXCLUDED.current_price,
                    historical_price = EXCLUDED.historical_price,
                    updated_at = CURRENT_TIMESTAMP
            """, (symbol, price_drop, current_price, historical_price))
            cursor.close()
            logger.info(f"✅ Добавлена/обновлена пара {symbol} в watchlist")
        except Exception as e:
            logger.error(f"❌ Ошибка добавления {symbol} в watchlist: {e}")

    async def remove_from_watchlist(self, symbol: str = None, item_id: int = None):
        """Удаление торговой пары из watchlist"""
        try:
            cursor = self.connection.cursor()
            if item_id:
                cursor.execute("DELETE FROM watchlist WHERE id = %s", (item_id,))
            elif symbol:
                cursor.execute("DELETE FROM watchlist WHERE symbol = %s", (symbol,))
            cursor.close()
            logger.info(f"✅ Удалена пара из watchlist")
        except Exception as e:
            logger.error(f"❌ Ошибка удаления из watchlist: {e}")

    async def update_watchlist_item(self, item_id: int, symbol: str, is_active: bool):
        """Обновление элемента watchlist"""
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                UPDATE watchlist 
                SET symbol = %s, is_active = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (symbol, is_active, item_id))
            cursor.close()
            logger.info(f"✅ Обновлена пара {symbol} в watchlist")
        except Exception as e:
            logger.error(f"❌ Ошибка обновления watchlist: {e}")

    async def get_historical_long_volumes(self, symbol: str, hours: int, 
                                        offset_minutes: int = 0, volume_type: str = 'long') -> List[float]:
        """Получение исторических объемов LONG свечей"""
        try:
            cursor = self.connection.cursor()
            
            # Рассчитываем временные границы
            end_time = datetime.utcnow() - timedelta(minutes=offset_minutes)
            start_time = end_time - timedelta(hours=hours)
            
            end_time_unix = int(end_time.timestamp() * 1000)
            start_time_unix = int(start_time.timestamp() * 1000)
            
            # Формируем условие в зависимости от типа объема
            if volume_type == 'long':
                condition = "AND is_long = TRUE"
            elif volume_type == 'short':
                condition = "AND is_long = FALSE"
            else:  # 'all'
                condition = ""
            
            cursor.execute(f"""
                SELECT volume_usdt 
                FROM kline_data 
                WHERE symbol = %s 
                AND open_time_unix >= %s 
                AND open_time_unix < %s 
                AND is_closed = TRUE
                {condition}
                ORDER BY open_time_unix
            """, (symbol, start_time_unix, end_time_unix))
            
            volumes = [float(row[0]) for row in cursor.fetchall()]
            cursor.close()
            
            return volumes
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения исторических объемов для {symbol}: {e}")
            return []

    async def get_recent_candles(self, symbol: str, count: int) -> List[Dict]:
        """Получение последних свечей для символа"""
        try:
            cursor = self.connection.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT open_time_unix as timestamp, open_price as open, high_price as high,
                       low_price as low, close_price as close, volume, is_long, is_closed
                FROM kline_data 
                WHERE symbol = %s AND is_closed = TRUE
                ORDER BY open_time_unix DESC 
                LIMIT %s
            """, (symbol, count))
            
            candles = [dict(row) for row in cursor.fetchall()]
            cursor.close()
            
            # Возвращаем в хронологическом порядке
            return list(reversed(candles))
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения последних свечей для {symbol}: {e}")
            return []

    async def save_alert(self, alert_data: Dict) -> int:
        """Сохранение алерта в базу данных"""
        try:
            cursor = self.connection.cursor()
            
            cursor.execute("""
                INSERT INTO alerts (
                    symbol, alert_type, price, volume_ratio, consecutive_count,
                    current_volume_usdt, average_volume_usdt, is_true_signal, is_closed,
                    has_imbalance, imbalance_data, candle_data, order_book_snapshot,
                    message, timestamp, close_timestamp
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                alert_data['symbol'],
                alert_data['alert_type'],
                alert_data['price'],
                alert_data.get('volume_ratio'),
                alert_data.get('consecutive_count'),
                alert_data.get('current_volume_usdt'),
                alert_data.get('average_volume_usdt'),
                alert_data.get('is_true_signal'),
                alert_data.get('is_closed', False),
                alert_data.get('has_imbalance', False),
                json.dumps(alert_data.get('imbalance_data')) if alert_data.get('imbalance_data') else None,
                json.dumps(alert_data.get('candle_data')) if alert_data.get('candle_data') else None,
                json.dumps(alert_data.get('order_book_snapshot')) if alert_data.get('order_book_snapshot') else None,
                alert_data.get('message'),
                alert_data['timestamp'],
                alert_data.get('close_timestamp')
            ))
            
            alert_id = cursor.fetchone()[0]
            cursor.close()
            
            return alert_id
            
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения алерта: {e}")
            return 0

    async def get_all_alerts(self, limit: int = 1000) -> Dict:
        """Получение всех алертов"""
        try:
            cursor = self.connection.cursor(cursor_factory=RealDictCursor)
            
            # Получаем алерты по объему
            cursor.execute("""
                SELECT * FROM alerts 
                WHERE alert_type = 'volume_spike'
                ORDER BY close_timestamp DESC, timestamp DESC 
                LIMIT %s
            """, (limit,))
            volume_alerts = [dict(row) for row in cursor.fetchall()]
            
            # Получаем алерты по последовательности
            cursor.execute("""
                SELECT * FROM alerts 
                WHERE alert_type = 'consecutive_long'
                ORDER BY close_timestamp DESC, timestamp DESC 
                LIMIT %s
            """, (limit,))
            consecutive_alerts = [dict(row) for row in cursor.fetchall()]
            
            # Получаем приоритетные алерты
            cursor.execute("""
                SELECT * FROM alerts 
                WHERE alert_type = 'priority'
                ORDER BY close_timestamp DESC, timestamp DESC 
                LIMIT %s
            """, (limit,))
            priority_alerts = [dict(row) for row in cursor.fetchall()]
            
            cursor.close()
            
            return {
                'volume_alerts': volume_alerts,
                'consecutive_alerts': consecutive_alerts,
                'priority_alerts': priority_alerts,
                'alerts': volume_alerts + consecutive_alerts + priority_alerts
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения алертов: {e}")
            return {
                'volume_alerts': [],
                'consecutive_alerts': [],
                'priority_alerts': [],
                'alerts': []
            }

    async def get_alerts_by_type(self, alert_type: str, limit: int = 50) -> List[Dict]:
        """Получение алертов по типу"""
        try:
            cursor = self.connection.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT * FROM alerts 
                WHERE alert_type = %s
                ORDER BY close_timestamp DESC, timestamp DESC 
                LIMIT %s
            """, (alert_type, limit))
            
            alerts = [dict(row) for row in cursor.fetchall()]
            cursor.close()
            
            return alerts
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения алертов по типу {alert_type}: {e}")
            return []

    async def clear_alerts(self, alert_type: str):
        """Очистка алертов по типу"""
        try:
            cursor = self.connection.cursor()
            cursor.execute("DELETE FROM alerts WHERE alert_type = %s", (alert_type,))
            cursor.close()
            logger.info(f"✅ Очищены алерты типа {alert_type}")
        except Exception as e:
            logger.error(f"❌ Ошибка очистки алертов {alert_type}: {e}")

    async def get_recent_volume_alerts(self, symbol: str, minutes_back: int) -> List[Dict]:
        """Получение недавних объемных алертов"""
        try:
            cursor = self.connection.cursor(cursor_factory=RealDictCursor)
            
            cutoff_time = datetime.utcnow() - timedelta(minutes=minutes_back)
            
            cursor.execute("""
                SELECT * FROM alerts 
                WHERE symbol = %s 
                AND alert_type = 'volume_spike'
                AND timestamp >= %s
                ORDER BY timestamp DESC
            """, (symbol, cutoff_time))
            
            alerts = [dict(row) for row in cursor.fetchall()]
            cursor.close()
            
            return alerts
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения недавних объемных алертов для {symbol}: {e}")
            return []

    async def get_chart_data(self, symbol: str, hours: int = 1, alert_time: str = None) -> List[Dict]:
        """Получение данных для графика"""
        try:
            cursor = self.connection.cursor(cursor_factory=RealDictCursor)
            
            if alert_time:
                # Если указано время алерта, центрируем данные вокруг него
                center_time = datetime.fromisoformat(alert_time.replace('Z', '+00:00'))
                start_time = center_time - timedelta(hours=hours/2)
                end_time = center_time + timedelta(hours=hours/2)
            else:
                # Иначе берем последние N часов
                end_time = datetime.utcnow()
                start_time = end_time - timedelta(hours=hours)
            
            start_time_unix = int(start_time.timestamp() * 1000)
            end_time_unix = int(end_time.timestamp() * 1000)
            
            cursor.execute("""
                SELECT 
                    open_time_unix as timestamp,
                    open_price as open,
                    high_price as high,
                    low_price as low,
                    close_price as close,
                    volume,
                    volume_usdt,
                    is_long
                FROM kline_data 
                WHERE symbol = %s 
                AND open_time_unix >= %s 
                AND open_time_unix <= %s
                ORDER BY open_time_unix
            """, (symbol, start_time_unix, end_time_unix))
            
            chart_data = [dict(row) for row in cursor.fetchall()]
            cursor.close()
            
            return chart_data
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения данных графика для {symbol}: {e}")
            return []

    async def cleanup_old_data(self, retention_hours: int):
        """Очистка старых данных"""
        try:
            cursor = self.connection.cursor()
            
            # Удаляем старые данные свечей
            cutoff_time_unix = int((datetime.utcnow() - timedelta(hours=retention_hours)).timestamp() * 1000)
            
            cursor.execute("""
                DELETE FROM kline_data 
                WHERE open_time_unix < %s
            """, (cutoff_time_unix,))
            
            deleted_candles = cursor.rowcount
            
            # Удаляем старые алерты (старше 7 дней)
            cutoff_time_alerts = datetime.utcnow() - timedelta(days=7)
            cursor.execute("""
                DELETE FROM alerts 
                WHERE created_at < %s
            """, (cutoff_time_alerts,))
            
            deleted_alerts = cursor.rowcount
            cursor.close()
            
            logger.info(f"✅ Очистка завершена: удалено {deleted_candles} свечей, {deleted_alerts} алертов")
            
        except Exception as e:
            logger.error(f"❌ Ошибка очистки старых данных: {e}")

    def close(self):
        """Закрытие соединения с базой данных"""
        if self.connection:
            self.connection.close()
            logger.info("✅ Соединение с базой данных закрыто")