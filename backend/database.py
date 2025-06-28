import asyncio
import logging
from typing import List, Dict, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta
import os
import json

logger = logging.getLogger(__name__)


class DatabaseManager:
    def __init__(self):
        self.connection = None
        self.db_config = {
            'host': os.getenv('DB_HOST', 'localhost'),
            'port': os.getenv('DB_PORT', '5432'),
            'database': os.getenv('DB_NAME', 'tradingbase'),
            'user': os.getenv('DB_USER', 'postgres'),
            'password': os.getenv('DB_PASSWORD', 'password')
        }

    async def initialize(self):
        """Инициализация подключения к базе данных"""
        try:
            self.connection = psycopg2.connect(**self.db_config)
            self.connection.autocommit = True

            # Создаем необходимые таблицы
            await self.create_tables()

            # Обновляем существующие таблицы
            await self.update_tables()

            logger.info("База данных успешно инициализирована")

        except Exception as e:
            logger.error(f"Ошибка подключения к базе данных: {e}")
            raise

    async def create_tables(self):
        """Создание необходимых таблиц с UTC временем"""
        try:
            cursor = self.connection.cursor()

            # Создаем таблицу watchlist
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS watchlist (
                    id SERIAL PRIMARY KEY,
                    symbol VARCHAR(20) NOT NULL UNIQUE,
                    is_active BOOLEAN DEFAULT TRUE,
                    price_drop_percentage DECIMAL(5, 2),
                    current_price DECIMAL(20, 8),
                    historical_price DECIMAL(20, 8),
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT (NOW() AT TIME ZONE 'UTC'),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT (NOW() AT TIME ZONE 'UTC')
                )
            """)

            # Создаем основную таблицу для исторических данных (UTC время)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS kline_data (
                    id SERIAL PRIMARY KEY,
                    symbol VARCHAR(20) NOT NULL,
                    open_time BIGINT NOT NULL,
                    close_time BIGINT NOT NULL,
                    open_price DECIMAL(20, 8) NOT NULL,
                    high_price DECIMAL(20, 8) NOT NULL,
                    low_price DECIMAL(20, 8) NOT NULL,
                    close_price DECIMAL(20, 8) NOT NULL,
                    volume DECIMAL(20, 8) NOT NULL,
                    volume_usdt DECIMAL(20, 8) NOT NULL,
                    is_long BOOLEAN NOT NULL,
                    is_closed BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT (NOW() AT TIME ZONE 'UTC'),
                    UNIQUE(symbol, open_time)
                )
            """)

            # Создаем временную таблицу для потоковых данных (UTC время)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS kline_stream (
                    id SERIAL PRIMARY KEY,
                    symbol VARCHAR(20) NOT NULL,
                    open_time BIGINT NOT NULL,
                    close_time BIGINT NOT NULL,
                    open_price DECIMAL(20, 8) NOT NULL,
                    high_price DECIMAL(20, 8) NOT NULL,
                    low_price DECIMAL(20, 8) NOT NULL,
                    close_price DECIMAL(20, 8) NOT NULL,
                    volume DECIMAL(20, 8) NOT NULL,
                    volume_usdt DECIMAL(20, 8) NOT NULL,
                    is_long BOOLEAN NOT NULL,
                    last_update TIMESTAMP WITH TIME ZONE DEFAULT (NOW() AT TIME ZONE 'UTC'),
                    UNIQUE(symbol, open_time)
                )
            """)

            # Создаем обновленную таблицу алертов (UTC время)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS alerts (
                    id SERIAL PRIMARY KEY,
                    symbol VARCHAR(20) NOT NULL,
                    alert_type VARCHAR(50) NOT NULL,
                    price DECIMAL(20, 8) NOT NULL,
                    volume_ratio DECIMAL(10, 2),
                    consecutive_count INTEGER,
                    current_volume_usdt DECIMAL(20, 8),
                    average_volume_usdt DECIMAL(20, 8),
                    is_true_signal BOOLEAN,
                    is_closed BOOLEAN DEFAULT FALSE,
                    has_imbalance BOOLEAN DEFAULT FALSE,
                    message TEXT,
                    telegram_sent BOOLEAN DEFAULT FALSE,
                    alert_timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
                    close_timestamp TIMESTAMP WITH TIME ZONE,
                    candle_data JSONB,
                    preliminary_alert JSONB,
                    imbalance_data JSONB,
                    order_book_snapshot JSONB,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT (NOW() AT TIME ZONE 'UTC'),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT (NOW() AT TIME ZONE 'UTC')
                )
            """)

            # Создаем индексы для оптимизации запросов
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_kline_symbol_time 
                ON kline_data(symbol, open_time DESC)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_kline_symbol_long_time 
                ON kline_data(symbol, is_long, open_time DESC)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_kline_stream_symbol_time 
                ON kline_stream(symbol, open_time)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_alerts_symbol_type_time 
                ON alerts(symbol, alert_type, alert_timestamp DESC)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_alerts_type_created 
                ON alerts(alert_type, created_at DESC)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_alerts_close_timestamp 
                ON alerts(close_timestamp DESC NULLS LAST)
            """)

            cursor.close()
            logger.info("Таблицы успешно созданы с UTC временем")

        except Exception as e:
            logger.error(f"Ошибка создания таблиц: {e}")
            raise

    async def update_tables(self):
        """Обновление существующих таблиц для добавления новых колонок"""
        try:
            cursor = self.connection.cursor()

            # Добавляем колонку is_closed в kline_data если её нет
            cursor.execute("""
                ALTER TABLE kline_data 
                ADD COLUMN IF NOT EXISTS is_closed BOOLEAN DEFAULT FALSE
            """)

            # Обновляем существующие записи - помечаем все как закрытые
            cursor.execute("""
                UPDATE kline_data 
                SET is_closed = TRUE 
                WHERE is_closed IS NULL OR is_closed = FALSE
            """)

            # Обновляем колонки времени на UTC если они не UTC
            cursor.execute("""
                ALTER TABLE watchlist 
                ALTER COLUMN created_at TYPE TIMESTAMP WITH TIME ZONE USING created_at AT TIME ZONE 'UTC',
                ALTER COLUMN updated_at TYPE TIMESTAMP WITH TIME ZONE USING updated_at AT TIME ZONE 'UTC'
            """)

            cursor.execute("""
                ALTER TABLE kline_data 
                ALTER COLUMN created_at TYPE TIMESTAMP WITH TIME ZONE USING created_at AT TIME ZONE 'UTC'
            """)

            cursor.execute("""
                ALTER TABLE kline_stream 
                ALTER COLUMN last_update TYPE TIMESTAMP WITH TIME ZONE USING last_update AT TIME ZONE 'UTC'
            """)

            cursor.execute("""
                ALTER TABLE alerts 
                ALTER COLUMN alert_timestamp TYPE TIMESTAMP WITH TIME ZONE USING alert_timestamp AT TIME ZONE 'UTC',
                ALTER COLUMN close_timestamp TYPE TIMESTAMP WITH TIME ZONE USING close_timestamp AT TIME ZONE 'UTC',
                ALTER COLUMN created_at TYPE TIMESTAMP WITH TIME ZONE USING created_at AT TIME ZONE 'UTC',
                ALTER COLUMN updated_at TYPE TIMESTAMP WITH TIME ZONE USING updated_at AT TIME ZONE 'UTC'
            """)

            cursor.close()

        except Exception as e:
            logger.error(f"Ошибка обновления таблиц: {e}")

    async def save_kline_data(self, symbol: str, kline_data: Dict, is_closed: bool = False):
        """Сохранение данных свечи с разделением на исторические и потоковые"""
        try:
            cursor = self.connection.cursor()

            # Определяем, является ли свеча LONG (зеленой)
            is_long = float(kline_data['close']) > float(kline_data['open'])
            volume_usdt = float(kline_data['volume']) * float(kline_data['close'])
            open_time = int(kline_data['start'])

            if is_closed:
                # Закрытая свеча - сохраняем в основную таблицу
                cursor.execute("""
                    INSERT INTO kline_data 
                    (symbol, open_time, close_time, open_price, high_price, 
                     low_price, close_price, volume, volume_usdt, is_long, is_closed, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW() AT TIME ZONE 'UTC')
                    ON CONFLICT (symbol, open_time) DO UPDATE SET
                        close_time = EXCLUDED.close_time,
                        open_price = EXCLUDED.open_price,
                        high_price = EXCLUDED.high_price,
                        low_price = EXCLUDED.low_price,
                        close_price = EXCLUDED.close_price,
                        volume = EXCLUDED.volume,
                        volume_usdt = EXCLUDED.volume_usdt,
                        is_long = EXCLUDED.is_long,
                        is_closed = EXCLUDED.is_closed
                """, (
                    symbol, open_time, int(kline_data['end']),
                    float(kline_data['open']), float(kline_data['high']),
                    float(kline_data['low']), float(kline_data['close']),
                    float(kline_data['volume']), volume_usdt, is_long, True
                ))

                # Удаляем из потоковой таблицы
                cursor.execute("""
                    DELETE FROM kline_stream 
                    WHERE symbol = %s AND open_time = %s
                """, (symbol, open_time))

                # Очищаем старые данные из основной таблицы
                await self._cleanup_old_kline_data(symbol, cursor)

            else:
                # Формирующаяся свеча - сохраняем в потоковую таблицу
                cursor.execute("""
                    INSERT INTO kline_stream 
                    (symbol, open_time, close_time, open_price, high_price, 
                     low_price, close_price, volume, volume_usdt, is_long, last_update)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW() AT TIME ZONE 'UTC')
                    ON CONFLICT (symbol, open_time) DO UPDATE SET
                        close_time = EXCLUDED.close_time,
                        high_price = GREATEST(kline_stream.high_price, EXCLUDED.high_price),
                        low_price = LEAST(kline_stream.low_price, EXCLUDED.low_price),
                        close_price = EXCLUDED.close_price,
                        volume = EXCLUDED.volume,
                        volume_usdt = EXCLUDED.volume_usdt,
                        is_long = EXCLUDED.is_long,
                        last_update = NOW() AT TIME ZONE 'UTC'
                """, (
                    symbol, open_time, int(kline_data['end']),
                    float(kline_data['open']), float(kline_data['high']),
                    float(kline_data['low']), float(kline_data['close']),
                    float(kline_data['volume']), volume_usdt, is_long
                ))

            cursor.close()

        except Exception as e:
            logger.error(f"Ошибка сохранения данных свечи: {e}")

    async def _cleanup_old_kline_data(self, symbol: str, cursor):
        """Очистка старых данных для символа"""
        try:
            # Получаем настройку периода хранения (по умолчанию 2 часа)
            retention_hours = int(os.getenv('DATA_RETENTION_HOURS', 2))
            cutoff_time = int((datetime.utcnow() - timedelta(hours=retention_hours)).timestamp() * 1000)
            
            cursor.execute("""
                DELETE FROM kline_data 
                WHERE symbol = %s AND open_time < %s
            """, (symbol, cutoff_time))
            
            deleted_count = cursor.rowcount
            if deleted_count > 0:
                logger.debug(f"Удалено {deleted_count} старых свечей для {symbol}")

        except Exception as e:
            logger.error(f"Ошибка очистки старых данных для {symbol}: {e}")

    async def get_chart_data(self, symbol: str, hours: int = 1, alert_time: str = None) -> List[Dict]:
        """Получить данные для построения графика (включая текущую формирующуюся свечу)"""
        try:
            cursor = self.connection.cursor(cursor_factory=RealDictCursor)

            # Определяем временные границы
            if alert_time:
                try:
                    alert_dt = datetime.fromisoformat(alert_time.replace('Z', '+00:00'))
                    end_time = int(alert_dt.timestamp() * 1000)
                    # Для алертов показываем данные включая время алерта + 2 минуты
                    end_time += 120000  # +2 минуты
                    include_current = False
                except:
                    end_time = int(datetime.utcnow().timestamp() * 1000)
                    include_current = True
            else:
                end_time = int(datetime.utcnow().timestamp() * 1000)
                include_current = True
            
            start_time = end_time - (hours * 60 * 60 * 1000)

            # Получаем закрытые свечи из основной таблицы
            cursor.execute("""
                SELECT open_time as timestamp, open_price as open, high_price as high,
                       low_price as low, close_price as close, volume, volume_usdt, is_long, TRUE as is_closed
                FROM kline_data 
                WHERE symbol = %s 
                AND open_time >= %s 
                AND open_time <= %s
                AND is_closed = TRUE
                ORDER BY open_time
            """, (symbol, start_time, end_time))

            closed_candles = cursor.fetchall()

            chart_data = []
            for row in closed_candles:
                chart_data.append({
                    'timestamp': int(row['timestamp']),
                    'open': float(row['open']),
                    'high': float(row['high']),
                    'low': float(row['low']),
                    'close': float(row['close']),
                    'volume': float(row['volume']),
                    'volume_usdt': float(row['volume_usdt']),
                    'is_long': row['is_long']
                })

            # Добавляем текущую формирующуюся свечу, если нужно
            if include_current:
                cursor.execute("""
                    SELECT open_time as timestamp, open_price as open, high_price as high,
                           low_price as low, close_price as close, volume, volume_usdt, is_long, FALSE as is_closed
                    FROM kline_stream 
                    WHERE symbol = %s 
                    AND open_time > %s
                    ORDER BY open_time DESC
                    LIMIT 1
                """, (symbol, end_time - 180000))  # Ищем свечи за последние 3 минуты

                current_candle = cursor.fetchone()
                if current_candle:
                    chart_data.append({
                        'timestamp': int(current_candle['timestamp']),
                        'open': float(current_candle['open']),
                        'high': float(current_candle['high']),
                        'low': float(current_candle['low']),
                        'close': float(current_candle['close']),
                        'volume': float(current_candle['volume']),
                        'volume_usdt': float(current_candle['volume_usdt']),
                        'is_long': current_candle['is_long']
                    })

            cursor.close()

            # Сортируем по времени
            chart_data.sort(key=lambda x: x['timestamp'])

            logger.info(f"Получено {len(chart_data)} свечей для {symbol} за период {hours}ч (включая текущую: {include_current})")
            return chart_data

        except Exception as e:
            logger.error(f"Ошибка получения данных графика для {symbol}: {e}")
            return []

    async def get_recent_candles(self, symbol: str, count: int = 20) -> List[Dict]:
        """Получить последние свечи для анализа (включая текущую формирующуюся)"""
        try:
            cursor = self.connection.cursor(cursor_factory=RealDictCursor)

            # Получаем закрытые свечи из основной таблицы
            cursor.execute("""
                SELECT open_time as timestamp, open_price as open, high_price as high,
                       low_price as low, close_price as close, volume, volume_usdt, is_long, TRUE as is_closed
                FROM kline_data 
                WHERE symbol = %s 
                AND is_closed = TRUE
                ORDER BY open_time DESC
                LIMIT %s
            """, (symbol, count - 1))

            closed_candles = cursor.fetchall()

            # Получаем текущую формирующуюся свечу из потоковой таблицы
            cursor.execute("""
                SELECT open_time as timestamp, open_price as open, high_price as high,
                       low_price as low, close_price as close, volume, volume_usdt, is_long, FALSE as is_closed
                FROM kline_stream 
                WHERE symbol = %s 
                ORDER BY open_time DESC
                LIMIT 1
            """, (symbol,))

            current_candle = cursor.fetchone()
            cursor.close()

            # Объединяем данные
            all_candles = []
            
            # Добавляем закрытые свечи (в обратном порядке, так как они отсортированы по убыванию)
            for row in reversed(closed_candles):
                all_candles.append({
                    'timestamp': int(row['timestamp']),
                    'open': float(row['open']),
                    'high': float(row['high']),
                    'low': float(row['low']),
                    'close': float(row['close']),
                    'volume': float(row['volume']),
                    'volume_usdt': float(row['volume_usdt']),
                    'is_long': row['is_long'],
                    'is_closed': True
                })

            # Добавляем текущую свечу если есть
            if current_candle:
                all_candles.append({
                    'timestamp': int(current_candle['timestamp']),
                    'open': float(current_candle['open']),
                    'high': float(current_candle['high']),
                    'low': float(current_candle['low']),
                    'close': float(current_candle['close']),
                    'volume': float(current_candle['volume']),
                    'volume_usdt': float(current_candle['volume_usdt']),
                    'is_long': current_candle['is_long'],
                    'is_closed': False
                })

            # Сортируем по времени
            all_candles.sort(key=lambda x: x['timestamp'])

            return all_candles[-count:]  # Возвращаем последние count свечей

        except Exception as e:
            logger.error(f"Ошибка получения последних свечей для {symbol}: {e}")
            return []

    async def cleanup_old_data(self, retention_hours: int = 2):
        """Очистка старых данных"""
        try:
            cursor = self.connection.cursor()
            
            # Удаляем старые данные свечей
            cutoff_time = int((datetime.utcnow() - timedelta(hours=retention_hours)).timestamp() * 1000)
            
            cursor.execute("""
                DELETE FROM kline_data 
                WHERE open_time < %s
            """, (cutoff_time,))
            
            deleted_klines = cursor.rowcount
            
            # Очищаем старые потоковые данные (старше 5 минут)
            stream_cutoff = datetime.utcnow() - timedelta(minutes=5)
            cursor.execute("""
                DELETE FROM kline_stream 
                WHERE last_update < %s AT TIME ZONE 'UTC'
            """, (stream_cutoff,))
            
            deleted_stream = cursor.rowcount
            
            # Удаляем старые алерты (старше 24 часов)
            alert_cutoff = datetime.utcnow() - timedelta(hours=24)
            cursor.execute("""
                DELETE FROM alerts 
                WHERE created_at < %s AT TIME ZONE 'UTC'
            """, (alert_cutoff,))
            
            deleted_alerts = cursor.rowcount
            
            cursor.close()
            
            logger.info(f"Очищено {deleted_klines} записей свечей, {deleted_stream} потоковых записей и {deleted_alerts} алертов")

        except Exception as e:
            logger.error(f"Ошибка очистки старых данных: {e}")

    # Остальные методы остаются без изменений, но с UTC временем
    async def get_watchlist(self) -> List[str]:
        """Получить список активных торговых пар"""
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT symbol FROM watchlist 
                WHERE is_active = TRUE 
                ORDER BY symbol
            """)

            pairs = [row[0] for row in cursor.fetchall()]
            cursor.close()

            return pairs

        except Exception as e:
            logger.error(f"Ошибка получения watchlist: {e}")
            return []

    async def get_watchlist_details(self) -> List[Dict]:
        """Получить детальную информацию о торговых парах в watchlist"""
        try:
            cursor = self.connection.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT id, symbol, is_active, price_drop_percentage, 
                       current_price, historical_price, created_at, updated_at
                FROM watchlist 
                ORDER BY 
                    CASE WHEN price_drop_percentage IS NOT NULL THEN price_drop_percentage ELSE 0 END DESC,
                    symbol ASC
            """)

            result = cursor.fetchall()
            cursor.close()

            return [dict(row) for row in result]

        except Exception as e:
            logger.error(f"Ошибка получения детальной информации watchlist: {e}")
            return []

    async def add_to_watchlist(self, symbol: str, price_drop: float = None,
                               current_price: float = None, historical_price: float = None):
        """Добавить торговую пару в watchlist"""
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                INSERT INTO watchlist (symbol, price_drop_percentage, current_price, historical_price, created_at, updated_at) 
                VALUES (%s, %s, %s, %s, NOW() AT TIME ZONE 'UTC', NOW() AT TIME ZONE 'UTC') 
                ON CONFLICT (symbol) DO UPDATE SET
                    is_active = TRUE,
                    price_drop_percentage = EXCLUDED.price_drop_percentage,
                    current_price = EXCLUDED.current_price,
                    historical_price = EXCLUDED.historical_price,
                    updated_at = NOW() AT TIME ZONE 'UTC'
            """, (symbol, price_drop, current_price, historical_price))

            cursor.close()

        except Exception as e:
            logger.error(f"Ошибка добавления в watchlist: {e}")

    async def update_watchlist_item(self, item_id: int, symbol: str, is_active: bool):
        """Обновить элемент watchlist"""
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                UPDATE watchlist 
                SET symbol = %s, is_active = %s, updated_at = NOW() AT TIME ZONE 'UTC'
                WHERE id = %s
            """, (symbol, is_active, item_id))

            cursor.close()

        except Exception as e:
            logger.error(f"Ошибка обновления watchlist: {e}")

    async def remove_from_watchlist(self, symbol: str = None, item_id: int = None):
        """Удалить торговую пару из watchlist"""
        try:
            cursor = self.connection.cursor()
            
            if item_id:
                cursor.execute("DELETE FROM watchlist WHERE id = %s", (item_id,))
            elif symbol:
                cursor.execute("DELETE FROM watchlist WHERE symbol = %s", (symbol,))

            cursor.close()

        except Exception as e:
            logger.error(f"Ошибка удаления из watchlist: {e}")

    async def check_data_integrity(self, symbol: str, hours: int) -> Dict:
        """Улучшенная проверка целостности исторических данных"""
        try:
            cursor = self.connection.cursor()
            
            # Определяем временные границы
            current_time = datetime.utcnow()
            current_minute = current_time.replace(second=0, microsecond=0)
            end_time = int(current_minute.timestamp() * 1000)
            start_time = end_time - (hours * 60 * 60 * 1000)
            
            # Получаем существующие данные (только закрытые свечи)
            cursor.execute("""
                SELECT open_time FROM kline_data 
                WHERE symbol = %s AND open_time >= %s AND open_time < %s
                AND is_closed = TRUE
                ORDER BY open_time
            """, (symbol, start_time, end_time))
            
            existing_times = [row[0] for row in cursor.fetchall()]
            cursor.close()
            
            # Генерируем ожидаемые временные метки
            expected_times = []
            current_time_ms = start_time
            cutoff_time = end_time - (3 * 60 * 1000)  # Исключаем последние 3 минуты
            
            while current_time_ms < cutoff_time:
                expected_times.append(current_time_ms)
                current_time_ms += 60000
            
            # Находим недостающие периоды
            missing_times = [t for t in expected_times if t not in existing_times]
            
            total_expected = len(expected_times)
            total_existing = len([t for t in existing_times if t < cutoff_time])
            
            return {
                'total_expected': total_expected,
                'total_existing': total_existing,
                'missing_count': len(missing_times),
                'missing_periods': missing_times,
                'integrity_percentage': (total_existing / total_expected) * 100 if total_expected > 0 else 100
            }
            
        except Exception as e:
            logger.error(f"Ошибка проверки целостности данных для {symbol}: {e}")
            return {
                'total_expected': 0,
                'total_existing': 0,
                'missing_count': 0,
                'missing_periods': [],
                'integrity_percentage': 0
            }

    async def get_historical_long_volumes(self, symbol: str, hours: int, offset_minutes: int = 0, 
                                        volume_type: str = 'long') -> List[float]:
        """Получить объемы свечей за указанный период с настройками смещения и типа"""
        try:
            cursor = self.connection.cursor()

            # Рассчитываем временные границы с учетом смещения
            current_time = int(datetime.utcnow().timestamp() * 1000)
            end_time = current_time - (offset_minutes * 60 * 1000)
            start_time = end_time - (hours * 60 * 60 * 1000)

            # Формируем условие в зависимости от типа объемов
            if volume_type == 'long':
                condition = "AND is_long = TRUE"
            elif volume_type == 'short':
                condition = "AND is_long = FALSE"
            else:  # 'all'
                condition = ""

            # Получаем данные только из основной таблицы (закрытые свечи)
            cursor.execute(f"""
                SELECT volume_usdt FROM kline_data 
                WHERE symbol = %s 
                {condition}
                AND open_time >= %s 
                AND open_time < %s
                AND is_closed = TRUE
                ORDER BY open_time
            """, (symbol, start_time, end_time))

            volumes = [float(row[0]) for row in cursor.fetchall()]
            cursor.close()

            return volumes

        except Exception as e:
            logger.error(f"Ошибка получения исторических объемов: {e}")
            return []

    async def save_alert(self, alert_data: Dict) -> int:
        """Сохранение алерта в базу данных"""
        try:
            cursor = self.connection.cursor()
            
            # Подготавливаем данные для сохранения
            candle_data_json = None
            if 'candle_data' in alert_data:
                candle_data_json = json.dumps(alert_data['candle_data'])
            
            preliminary_alert_json = None
            if 'preliminary_alert' in alert_data:
                preliminary_alert_json = json.dumps(alert_data['preliminary_alert'], default=str)
            
            imbalance_data_json = None
            if 'imbalance_data' in alert_data and alert_data['imbalance_data']:
                imbalance_data_json = json.dumps(alert_data['imbalance_data'])
            
            order_book_snapshot_json = None
            if 'order_book_snapshot' in alert_data and alert_data['order_book_snapshot']:
                order_book_snapshot_json = json.dumps(alert_data['order_book_snapshot'])
            
            cursor.execute("""
                INSERT INTO alerts 
                (symbol, alert_type, price, volume_ratio, consecutive_count,
                 current_volume_usdt, average_volume_usdt, is_true_signal, 
                 is_closed, has_imbalance, message, alert_timestamp, close_timestamp,
                 candle_data, preliminary_alert, imbalance_data, order_book_snapshot,
                 created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 
                        NOW() AT TIME ZONE 'UTC', NOW() AT TIME ZONE 'UTC')
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
                alert_data.get('message', ''),
                alert_data['timestamp'],
                alert_data.get('close_timestamp'),
                candle_data_json,
                preliminary_alert_json,
                imbalance_data_json,
                order_book_snapshot_json
            ))

            alert_id = cursor.fetchone()[0]
            cursor.close()
            
            return alert_id

        except Exception as e:
            logger.error(f"Ошибка сохранения алерта: {e}")
            return None

    async def update_alert(self, alert_id: int, alert_data: Dict):
        """Обновление алерта"""
        try:
            cursor = self.connection.cursor()
            
            candle_data_json = None
            if 'candle_data' in alert_data:
                candle_data_json = json.dumps(alert_data['candle_data'])
            
            imbalance_data_json = None
            if 'imbalance_data' in alert_data and alert_data['imbalance_data']:
                imbalance_data_json = json.dumps(alert_data['imbalance_data'])
            
            cursor.execute("""
                UPDATE alerts 
                SET price = %s, volume_ratio = %s, consecutive_count = %s,
                    current_volume_usdt = %s, average_volume_usdt = %s,
                    is_true_signal = %s, is_closed = %s, has_imbalance = %s, message = %s,
                    close_timestamp = %s, candle_data = %s, imbalance_data = %s, 
                    updated_at = NOW() AT TIME ZONE 'UTC'
                WHERE id = %s
            """, (
                alert_data['price'],
                alert_data.get('volume_ratio'),
                alert_data.get('consecutive_count'),
                alert_data.get('current_volume_usdt'),
                alert_data.get('average_volume_usdt'),
                alert_data.get('is_true_signal'),
                alert_data.get('is_closed', False),
                alert_data.get('has_imbalance', False),
                alert_data.get('message', ''),
                alert_data.get('close_timestamp'),
                candle_data_json,
                imbalance_data_json,
                alert_id
            ))

            cursor.close()

        except Exception as e:
            logger.error(f"Ошибка обновления алерта: {e}")

    async def get_alerts_by_type(self, alert_type: str, limit: int = 50) -> List[Dict]:
        """Получить алерты по типу с сортировкой по времени закрытия"""
        try:
            cursor = self.connection.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT id, symbol, alert_type, price, volume_ratio, consecutive_count,
                       current_volume_usdt, average_volume_usdt, is_true_signal, 
                       is_closed, has_imbalance, message, telegram_sent, alert_timestamp as timestamp,
                       close_timestamp, candle_data, preliminary_alert, imbalance_data, 
                       order_book_snapshot, created_at, updated_at
                FROM alerts 
                WHERE alert_type = %s
                ORDER BY COALESCE(close_timestamp, alert_timestamp) DESC
                LIMIT %s
            """, (alert_type, limit))

            result = cursor.fetchall()
            cursor.close()

            # Парсим JSON данные
            alerts = []
            for row in result:
                alert = dict(row)
                if alert['candle_data']:
                    alert['candle_data'] = json.loads(alert['candle_data'])
                if alert['preliminary_alert']:
                    alert['preliminary_alert'] = json.loads(alert['preliminary_alert'])
                if alert['imbalance_data']:
                    alert['imbalance_data'] = json.loads(alert['imbalance_data'])
                if alert['order_book_snapshot']:
                    alert['order_book_snapshot'] = json.loads(alert['order_book_snapshot'])
                alerts.append(alert)

            return alerts

        except Exception as e:
            logger.error(f"Ошибка получения алертов по типу {alert_type}: {e}")
            return []

    async def get_all_alerts(self, limit: int = 100) -> Dict[str, List[Dict]]:
        """Получить все алерты, разделенные по типам с сортировкой по времени закрытия"""
        try:
            cursor = self.connection.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT id, symbol, alert_type, price, volume_ratio, consecutive_count,
                       current_volume_usdt, average_volume_usdt, is_true_signal, 
                       is_closed, has_imbalance, message, telegram_sent, alert_timestamp as timestamp,
                       close_timestamp, candle_data, preliminary_alert, imbalance_data,
                       order_book_snapshot, created_at, updated_at
                FROM alerts 
                ORDER BY COALESCE(close_timestamp, alert_timestamp) DESC
                LIMIT %s
            """, (limit,))

            all_alerts_raw = cursor.fetchall()
            cursor.close()

            # Парсим JSON данные
            all_alerts = []
            for row in all_alerts_raw:
                alert = dict(row)
                if alert['candle_data']:
                    alert['candle_data'] = json.loads(alert['candle_data'])
                if alert['preliminary_alert']:
                    alert['preliminary_alert'] = json.loads(alert['preliminary_alert'])
                if alert['imbalance_data']:
                    alert['imbalance_data'] = json.loads(alert['imbalance_data'])
                if alert['order_book_snapshot']:
                    alert['order_book_snapshot'] = json.loads(alert['order_book_snapshot'])
                all_alerts.append(alert)

            # Разделяем по типам
            result = {
                'alerts': all_alerts,
                'volume_alerts': [a for a in all_alerts if a['alert_type'] == 'volume_spike'],
                'consecutive_alerts': [a for a in all_alerts if a['alert_type'] == 'consecutive_long'],
                'priority_alerts': [a for a in all_alerts if a['alert_type'] == 'priority']
            }

            return result

        except Exception as e:
            logger.error(f"Ошибка получения всех алертов: {e}")
            return {'alerts': [], 'volume_alerts': [], 'consecutive_alerts': [], 'priority_alerts': []}

    async def clear_alerts(self, alert_type: str = None):
        """Очистить алерты"""
        try:
            cursor = self.connection.cursor()
            
            if alert_type:
                cursor.execute("DELETE FROM alerts WHERE alert_type = %s", (alert_type,))
            else:
                cursor.execute("DELETE FROM alerts")

            cursor.close()

        except Exception as e:
            logger.error(f"Ошибка очистки алертов: {e}")

    async def get_recent_volume_alerts(self, symbol: str, minutes_back: int) -> List[Dict]:
        """Получить недавние объемные алерты для символа"""
        try:
            cursor = self.connection.cursor(cursor_factory=RealDictCursor)
            
            cutoff_time = datetime.utcnow() - timedelta(minutes=minutes_back)
            
            cursor.execute("""
                SELECT * FROM alerts 
                WHERE symbol = %s 
                AND alert_type = 'volume_spike'
                AND alert_timestamp >= %s AT TIME ZONE 'UTC'
                ORDER BY alert_timestamp DESC
            """, (symbol, cutoff_time))

            result = cursor.fetchall()
            cursor.close()

            return [dict(row) for row in result]

        except Exception as e:
            logger.error(f"Ошибка получения недавних объемных алертов для {symbol}: {e}")
            return []

    async def mark_telegram_sent(self, alert_id: int):
        """Отметить алерт как отправленный в Telegram"""
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                UPDATE alerts SET telegram_sent = TRUE, updated_at = NOW() AT TIME ZONE 'UTC' 
                WHERE id = %s
            """, (alert_id,))
            cursor.close()

        except Exception as e:
            logger.error(f"Ошибка отметки Telegram: {e}")

    def close(self):
        """Закрытие соединения с базой данных"""
        if self.connection:
            self.connection.close()