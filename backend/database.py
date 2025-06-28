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

            logger.info("База данных успешно инициализирована с UNIX временем")

        except Exception as e:
            logger.error(f"Ошибка подключения к базе данных: {e}")
            raise

    def _unix_to_readable(self, unix_timestamp: int) -> str:
        """Преобразование UNIX timestamp в читаемый формат ДД.ММ.ГГГГ ЧЧ:ММ:СС:МС"""
        try:
            # Преобразуем миллисекунды в секунды
            timestamp_seconds = unix_timestamp / 1000
            dt = datetime.utcfromtimestamp(timestamp_seconds)
            
            # Извлекаем миллисекунды
            milliseconds = unix_timestamp % 1000
            
            # Форматируем в нужный вид: ДД.ММ.ГГГГ ЧЧ:ММ:СС:МС
            return f"{dt.strftime('%d.%m.%Y %H:%M:%S')}:{milliseconds:03d}"
        except:
            return "Invalid timestamp"

    async def create_tables(self):
        """Создание необходимых таблиц с UNIX временем"""
        try:
            cursor = self.connection.cursor()

            # Создаем таблицу watchlist с UNIX временем
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS watchlist (
                    id SERIAL PRIMARY KEY,
                    symbol VARCHAR(20) NOT NULL UNIQUE,
                    is_active BOOLEAN DEFAULT TRUE,
                    price_drop_percentage DECIMAL(5, 2),
                    current_price DECIMAL(20, 8),
                    historical_price DECIMAL(20, 8),
                    created_at_unix BIGINT DEFAULT EXTRACT(EPOCH FROM NOW() AT TIME ZONE 'UTC') * 1000,
                    updated_at_unix BIGINT DEFAULT EXTRACT(EPOCH FROM NOW() AT TIME ZONE 'UTC') * 1000,
                    created_at_readable TEXT DEFAULT '',
                    updated_at_readable TEXT DEFAULT ''
                )
            """)

            # Создаем основную таблицу для исторических данных с UNIX временем
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS kline_data (
                    id SERIAL PRIMARY KEY,
                    symbol VARCHAR(20) NOT NULL,
                    open_time_unix BIGINT NOT NULL,
                    close_time_unix BIGINT NOT NULL,
                    open_price DECIMAL(20, 8) NOT NULL,
                    high_price DECIMAL(20, 8) NOT NULL,
                    low_price DECIMAL(20, 8) NOT NULL,
                    close_price DECIMAL(20, 8) NOT NULL,
                    volume DECIMAL(20, 8) NOT NULL,
                    volume_usdt DECIMAL(20, 8) NOT NULL,
                    is_long BOOLEAN NOT NULL,
                    is_closed BOOLEAN DEFAULT FALSE,
                    created_at_unix BIGINT DEFAULT EXTRACT(EPOCH FROM NOW() AT TIME ZONE 'UTC') * 1000,
                    open_time_readable TEXT DEFAULT '',
                    close_time_readable TEXT DEFAULT '',
                    created_at_readable TEXT DEFAULT '',
                    UNIQUE(symbol, open_time_unix)
                )
            """)

            # Создаем временную таблицу для потоковых данных с UNIX временем
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS kline_stream (
                    id SERIAL PRIMARY KEY,
                    symbol VARCHAR(20) NOT NULL,
                    open_time_unix BIGINT NOT NULL,
                    close_time_unix BIGINT NOT NULL,
                    open_price DECIMAL(20, 8) NOT NULL,
                    high_price DECIMAL(20, 8) NOT NULL,
                    low_price DECIMAL(20, 8) NOT NULL,
                    close_price DECIMAL(20, 8) NOT NULL,
                    volume DECIMAL(20, 8) NOT NULL,
                    volume_usdt DECIMAL(20, 8) NOT NULL,
                    is_long BOOLEAN NOT NULL,
                    last_update_unix BIGINT DEFAULT EXTRACT(EPOCH FROM NOW() AT TIME ZONE 'UTC') * 1000,
                    open_time_readable TEXT DEFAULT '',
                    close_time_readable TEXT DEFAULT '',
                    last_update_readable TEXT DEFAULT '',
                    UNIQUE(symbol, open_time_unix)
                )
            """)

            # Создаем обновленную таблицу алертов с UNIX временем
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
                    alert_timestamp_unix BIGINT NOT NULL,
                    close_timestamp_unix BIGINT,
                    candle_data JSONB,
                    preliminary_alert JSONB,
                    imbalance_data JSONB,
                    order_book_snapshot JSONB,
                    created_at_unix BIGINT DEFAULT EXTRACT(EPOCH FROM NOW() AT TIME ZONE 'UTC') * 1000,
                    updated_at_unix BIGINT DEFAULT EXTRACT(EPOCH FROM NOW() AT TIME ZONE 'UTC') * 1000,
                    alert_timestamp_readable TEXT DEFAULT '',
                    close_timestamp_readable TEXT DEFAULT '',
                    created_at_readable TEXT DEFAULT '',
                    updated_at_readable TEXT DEFAULT ''
                )
            """)

            # Создаем индексы для оптимизации запросов
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_kline_symbol_time_unix 
                ON kline_data(symbol, open_time_unix DESC)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_kline_symbol_long_time_unix 
                ON kline_data(symbol, is_long, open_time_unix DESC)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_kline_stream_symbol_time_unix 
                ON kline_stream(symbol, open_time_unix)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_alerts_symbol_type_time_unix 
                ON alerts(symbol, alert_type, alert_timestamp_unix DESC)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_alerts_type_created_unix 
                ON alerts(alert_type, created_at_unix DESC)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_alerts_close_timestamp_unix 
                ON alerts(close_timestamp_unix DESC NULLS LAST)
            """)

            cursor.close()
            logger.info("Таблицы успешно созданы с UNIX временем")

        except Exception as e:
            logger.error(f"Ошибка создания таблиц: {e}")
            raise

    async def update_tables(self):
        """Обновление существующих таблиц для добавления UNIX времени"""
        try:
            cursor = self.connection.cursor()

            # Добавляем UNIX колонки в watchlist если их нет
            cursor.execute("""
                ALTER TABLE watchlist 
                ADD COLUMN IF NOT EXISTS created_at_unix BIGINT DEFAULT EXTRACT(EPOCH FROM NOW() AT TIME ZONE 'UTC') * 1000,
                ADD COLUMN IF NOT EXISTS updated_at_unix BIGINT DEFAULT EXTRACT(EPOCH FROM NOW() AT TIME ZONE 'UTC') * 1000,
                ADD COLUMN IF NOT EXISTS created_at_readable TEXT DEFAULT '',
                ADD COLUMN IF NOT EXISTS updated_at_readable TEXT DEFAULT ''
            """)

            # Добавляем UNIX колонки в kline_data если их нет
            cursor.execute("""
                ALTER TABLE kline_data 
                ADD COLUMN IF NOT EXISTS open_time_unix BIGINT,
                ADD COLUMN IF NOT EXISTS close_time_unix BIGINT,
                ADD COLUMN IF NOT EXISTS created_at_unix BIGINT DEFAULT EXTRACT(EPOCH FROM NOW() AT TIME ZONE 'UTC') * 1000,
                ADD COLUMN IF NOT EXISTS open_time_readable TEXT DEFAULT '',
                ADD COLUMN IF NOT EXISTS close_time_readable TEXT DEFAULT '',
                ADD COLUMN IF NOT EXISTS created_at_readable TEXT DEFAULT '',
                ADD COLUMN IF NOT EXISTS is_closed BOOLEAN DEFAULT FALSE
            """)

            # Добавляем UNIX колонки в kline_stream если их нет
            cursor.execute("""
                ALTER TABLE kline_stream 
                ADD COLUMN IF NOT EXISTS open_time_unix BIGINT,
                ADD COLUMN IF NOT EXISTS close_time_unix BIGINT,
                ADD COLUMN IF NOT EXISTS last_update_unix BIGINT DEFAULT EXTRACT(EPOCH FROM NOW() AT TIME ZONE 'UTC') * 1000,
                ADD COLUMN IF NOT EXISTS open_time_readable TEXT DEFAULT '',
                ADD COLUMN IF NOT EXISTS close_time_readable TEXT DEFAULT '',
                ADD COLUMN IF NOT EXISTS last_update_readable TEXT DEFAULT ''
            """)

            # Добавляем UNIX колонки в alerts если их нет
            cursor.execute("""
                ALTER TABLE alerts 
                ADD COLUMN IF NOT EXISTS alert_timestamp_unix BIGINT,
                ADD COLUMN IF NOT EXISTS close_timestamp_unix BIGINT,
                ADD COLUMN IF NOT EXISTS created_at_unix BIGINT DEFAULT EXTRACT(EPOCH FROM NOW() AT TIME ZONE 'UTC') * 1000,
                ADD COLUMN IF NOT EXISTS updated_at_unix BIGINT DEFAULT EXTRACT(EPOCH FROM NOW() AT TIME ZONE 'UTC') * 1000,
                ADD COLUMN IF NOT EXISTS alert_timestamp_readable TEXT DEFAULT '',
                ADD COLUMN IF NOT EXISTS close_timestamp_readable TEXT DEFAULT '',
                ADD COLUMN IF NOT EXISTS created_at_readable TEXT DEFAULT '',
                ADD COLUMN IF NOT EXISTS updated_at_readable TEXT DEFAULT ''
            """)

            # Мигрируем существующие данные из старых колонок в UNIX формат
            await self._migrate_existing_data(cursor)

            cursor.close()

        except Exception as e:
            logger.error(f"Ошибка обновления таблиц: {e}")

    async def _migrate_existing_data(self, cursor):
        """Миграция существующих данных в UNIX формат"""
        try:
            # Мигрируем kline_data если есть старые колонки
            cursor.execute("""
                SELECT column_name FROM information_schema.columns 
                WHERE table_name = 'kline_data' AND column_name = 'open_time'
            """)
            
            if cursor.fetchone():
                logger.info("Миграция kline_data в UNIX формат...")
                cursor.execute("""
                    UPDATE kline_data 
                    SET open_time_unix = open_time,
                        close_time_unix = close_time,
                        open_time_readable = '',
                        close_time_readable = '',
                        created_at_readable = ''
                    WHERE open_time_unix IS NULL
                """)

            # Мигрируем alerts если есть старые колонки
            cursor.execute("""
                SELECT column_name FROM information_schema.columns 
                WHERE table_name = 'alerts' AND column_name = 'alert_timestamp'
            """)
            
            if cursor.fetchone():
                logger.info("Миграция alerts в UNIX формат...")
                cursor.execute("""
                    UPDATE alerts 
                    SET alert_timestamp_unix = EXTRACT(EPOCH FROM alert_timestamp) * 1000,
                        close_timestamp_unix = EXTRACT(EPOCH FROM close_timestamp) * 1000,
                        alert_timestamp_readable = '',
                        close_timestamp_readable = '',
                        created_at_readable = '',
                        updated_at_readable = ''
                    WHERE alert_timestamp_unix IS NULL
                """)

            logger.info("Миграция данных завершена")

        except Exception as e:
            logger.error(f"Ошибка миграции данных: {e}")

    async def save_kline_data(self, symbol: str, kline_data: Dict, is_closed: bool = False):
        """Сохранение данных свечи с UNIX временем"""
        try:
            cursor = self.connection.cursor()

            # Определяем, является ли свеча LONG (зеленой)
            is_long = float(kline_data['close']) > float(kline_data['open'])
            volume_usdt = float(kline_data['volume']) * float(kline_data['close'])
            
            # UNIX время от биржи (уже в миллисекундах)
            open_time_unix = int(kline_data['start'])
            close_time_unix = int(kline_data['end'])
            
            # Для исторических данных - округляем до минут с нулями (1687958700000)
            # Для потоковых данных - оставляем миллисекунды, но для закрытых свечей - с нулями
            if is_closed:
                # Закрытые свечи всегда с нулями в конце
                open_time_unix = (open_time_unix // 60000) * 60000
                close_time_unix = (close_time_unix // 60000) * 60000
            
            # Создаем читаемые форматы времени
            open_time_readable = self._unix_to_readable(open_time_unix)
            close_time_readable = self._unix_to_readable(close_time_unix)
            created_at_unix = int(datetime.utcnow().timestamp() * 1000)
            created_at_readable = self._unix_to_readable(created_at_unix)

            if is_closed:
                # Закрытая свеча - сохраняем в основную таблицу
                cursor.execute("""
                    INSERT INTO kline_data 
                    (symbol, open_time_unix, close_time_unix, open_price, high_price, 
                     low_price, close_price, volume, volume_usdt, is_long, is_closed, 
                     created_at_unix, open_time_readable, close_time_readable, created_at_readable)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (symbol, open_time_unix) DO UPDATE SET
                        close_time_unix = EXCLUDED.close_time_unix,
                        open_price = EXCLUDED.open_price,
                        high_price = EXCLUDED.high_price,
                        low_price = EXCLUDED.low_price,
                        close_price = EXCLUDED.close_price,
                        volume = EXCLUDED.volume,
                        volume_usdt = EXCLUDED.volume_usdt,
                        is_long = EXCLUDED.is_long,
                        is_closed = EXCLUDED.is_closed,
                        close_time_readable = EXCLUDED.close_time_readable
                """, (
                    symbol, open_time_unix, close_time_unix,
                    float(kline_data['open']), float(kline_data['high']),
                    float(kline_data['low']), float(kline_data['close']),
                    float(kline_data['volume']), volume_usdt, is_long, True,
                    created_at_unix, open_time_readable, close_time_readable, created_at_readable
                ))

                # Удаляем из потоковой таблицы
                cursor.execute("""
                    DELETE FROM kline_stream 
                    WHERE symbol = %s AND open_time_unix = %s
                """, (symbol, open_time_unix))

                # Очищаем старые данные из основной таблицы
                await self._cleanup_old_kline_data(symbol, cursor)

            else:
                # Формирующаяся свеча - сохраняем в потоковую таблицу (с миллисекундами)
                last_update_unix = int(datetime.utcnow().timestamp() * 1000)
                last_update_readable = self._unix_to_readable(last_update_unix)
                
                cursor.execute("""
                    INSERT INTO kline_stream 
                    (symbol, open_time_unix, close_time_unix, open_price, high_price, 
                     low_price, close_price, volume, volume_usdt, is_long, last_update_unix,
                     open_time_readable, close_time_readable, last_update_readable)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (symbol, open_time_unix) DO UPDATE SET
                        close_time_unix = EXCLUDED.close_time_unix,
                        high_price = GREATEST(kline_stream.high_price, EXCLUDED.high_price),
                        low_price = LEAST(kline_stream.low_price, EXCLUDED.low_price),
                        close_price = EXCLUDED.close_price,
                        volume = EXCLUDED.volume,
                        volume_usdt = EXCLUDED.volume_usdt,
                        is_long = EXCLUDED.is_long,
                        last_update_unix = EXCLUDED.last_update_unix,
                        close_time_readable = EXCLUDED.close_time_readable,
                        last_update_readable = EXCLUDED.last_update_readable
                """, (
                    symbol, open_time_unix, close_time_unix,
                    float(kline_data['open']), float(kline_data['high']),
                    float(kline_data['low']), float(kline_data['close']),
                    float(kline_data['volume']), volume_usdt, is_long, last_update_unix,
                    open_time_readable, close_time_readable, last_update_readable
                ))

            cursor.close()

        except Exception as e:
            logger.error(f"Ошибка сохранения данных свечи: {e}")

    async def _cleanup_old_kline_data(self, symbol: str, cursor):
        """Очистка старых данных для символа"""
        try:
            # Получаем настройку периода хранения (по умолчанию 2 часа)
            retention_hours = int(os.getenv('DATA_RETENTION_HOURS', 2))
            cutoff_time_unix = int((datetime.utcnow() - timedelta(hours=retention_hours)).timestamp() * 1000)
            
            cursor.execute("""
                DELETE FROM kline_data 
                WHERE symbol = %s AND open_time_unix < %s
            """, (symbol, cutoff_time_unix))
            
            deleted_count = cursor.rowcount
            if deleted_count > 0:
                logger.debug(f"Удалено {deleted_count} старых свечей для {symbol}")

        except Exception as e:
            logger.error(f"Ошибка очистки старых данных для {symbol}: {e}")

    async def get_chart_data(self, symbol: str, hours: int = 1, alert_time: str = None) -> List[Dict]:
        """Получить данные для построения графика (включая текущую формирующуюся свечу)"""
        try:
            cursor = self.connection.cursor(cursor_factory=RealDictCursor)

            # Определяем временные границы в UNIX формате
            if alert_time:
                try:
                    alert_dt = datetime.fromisoformat(alert_time.replace('Z', '+00:00'))
                    end_time_unix = int(alert_dt.timestamp() * 1000)
                    # Для алертов показываем данные включая время алерта + 2 минуты
                    end_time_unix += 120000  # +2 минуты
                    include_current = False
                except:
                    end_time_unix = int(datetime.utcnow().timestamp() * 1000)
                    include_current = True
            else:
                end_time_unix = int(datetime.utcnow().timestamp() * 1000)
                include_current = True
            
            start_time_unix = end_time_unix - (hours * 60 * 60 * 1000)

            # Получаем закрытые свечи из основной таблицы
            cursor.execute("""
                SELECT open_time_unix as timestamp, open_price as open, high_price as high,
                       low_price as low, close_price as close, volume, volume_usdt, is_long, 
                       TRUE as is_closed, open_time_readable, close_time_readable
                FROM kline_data 
                WHERE symbol = %s 
                AND open_time_unix >= %s 
                AND open_time_unix <= %s
                AND is_closed = TRUE
                ORDER BY open_time_unix
            """, (symbol, start_time_unix, end_time_unix))

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
                    'is_long': row['is_long'],
                    'readable_time': row['open_time_readable']
                })

            # Добавляем текущую формирующуюся свечу, если нужно
            if include_current:
                cursor.execute("""
                    SELECT open_time_unix as timestamp, open_price as open, high_price as high,
                           low_price as low, close_price as close, volume, volume_usdt, is_long, 
                           FALSE as is_closed, open_time_readable, close_time_readable
                    FROM kline_stream 
                    WHERE symbol = %s 
                    AND open_time_unix > %s
                    ORDER BY open_time_unix DESC
                    LIMIT 1
                """, (symbol, end_time_unix - 180000))  # Ищем свечи за последние 3 минуты

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
                        'is_long': current_candle['is_long'],
                        'readable_time': current_candle['open_time_readable']
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
                SELECT open_time_unix as timestamp, open_price as open, high_price as high,
                       low_price as low, close_price as close, volume, volume_usdt, is_long, 
                       TRUE as is_closed, open_time_readable
                FROM kline_data 
                WHERE symbol = %s 
                AND is_closed = TRUE
                ORDER BY open_time_unix DESC
                LIMIT %s
            """, (symbol, count - 1))

            closed_candles = cursor.fetchall()

            # Получаем текущую формирующуюся свечу из потоковой таблицы
            cursor.execute("""
                SELECT open_time_unix as timestamp, open_price as open, high_price as high,
                       low_price as low, close_price as close, volume, volume_usdt, is_long, 
                       FALSE as is_closed, open_time_readable
                FROM kline_stream 
                WHERE symbol = %s 
                ORDER BY open_time_unix DESC
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
                    'is_closed': True,
                    'readable_time': row['open_time_readable']
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
                    'is_closed': False,
                    'readable_time': current_candle['open_time_readable']
                })

            # Сортируем по времени
            all_candles.sort(key=lambda x: x['timestamp'])

            return all_candles[-count:]  # Возвращаем последние count свечей

        except Exception as e:
            logger.error(f"Ошибка получения последних свечей для {symbol}: {e}")
            return []

    async def check_data_integrity(self, symbol: str, hours: int) -> Dict:
        """Проверка целостности исторических данных с UNIX временем"""
        try:
            cursor = self.connection.cursor()
            
            # Определяем временные границы в UNIX формате
            current_time = datetime.utcnow()
            current_minute = current_time.replace(second=0, microsecond=0)
            end_time_unix = int(current_minute.timestamp() * 1000)
            start_time_unix = end_time_unix - (hours * 60 * 60 * 1000)
            
            # Получаем существующие данные (только закрытые свечи)
            cursor.execute("""
                SELECT open_time_unix FROM kline_data 
                WHERE symbol = %s AND open_time_unix >= %s AND open_time_unix < %s
                AND is_closed = TRUE
                ORDER BY open_time_unix
            """, (symbol, start_time_unix, end_time_unix))
            
            existing_times = [row[0] for row in cursor.fetchall()]
            cursor.close()
            
            # Генерируем ожидаемые временные метки (каждую минуту с нулями в конце)
            expected_times = []
            current_time_unix = start_time_unix
            cutoff_time_unix = end_time_unix - (3 * 60 * 1000)  # Исключаем последние 3 минуты
            
            while current_time_unix < cutoff_time_unix:
                # Округляем до минут с нулями в конце (формат 1687958700000)
                rounded_time = (current_time_unix // 60000) * 60000
                expected_times.append(rounded_time)
                current_time_unix += 60000
            
            # Находим недостающие периоды
            missing_times = [t for t in expected_times if t not in existing_times]
            
            total_expected = len(expected_times)
            total_existing = len([t for t in existing_times if t < cutoff_time_unix])
            
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
        """Получить объемы свечей за указанный период с UNIX временем"""
        try:
            cursor = self.connection.cursor()

            # Рассчитываем временные границы с учетом смещения в UNIX формате
            current_time_unix = int(datetime.utcnow().timestamp() * 1000)
            end_time_unix = current_time_unix - (offset_minutes * 60 * 1000)
            start_time_unix = end_time_unix - (hours * 60 * 60 * 1000)

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
                AND open_time_unix >= %s 
                AND open_time_unix < %s
                AND is_closed = TRUE
                ORDER BY open_time_unix
            """, (symbol, start_time_unix, end_time_unix))

            volumes = [float(row[0]) for row in cursor.fetchall()]
            cursor.close()

            return volumes

        except Exception as e:
            logger.error(f"Ошибка получения исторических объемов: {e}")
            return []

    async def save_alert(self, alert_data: Dict) -> int:
        """Сохранение алерта в базу данных с UNIX временем"""
        try:
            cursor = self.connection.cursor()
            
            # Преобразуем datetime в UNIX timestamp
            alert_timestamp_unix = int(alert_data['timestamp'].timestamp() * 1000) if isinstance(alert_data['timestamp'], datetime) else int(alert_data['timestamp'])
            close_timestamp_unix = None
            if alert_data.get('close_timestamp'):
                close_timestamp_unix = int(alert_data['close_timestamp'].timestamp() * 1000) if isinstance(alert_data['close_timestamp'], datetime) else int(alert_data['close_timestamp'])
            
            created_at_unix = int(datetime.utcnow().timestamp() * 1000)
            
            # Создаем читаемые форматы времени
            alert_timestamp_readable = self._unix_to_readable(alert_timestamp_unix)
            close_timestamp_readable = self._unix_to_readable(close_timestamp_unix) if close_timestamp_unix else ''
            created_at_readable = self._unix_to_readable(created_at_unix)
            
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
                 is_closed, has_imbalance, message, alert_timestamp_unix, close_timestamp_unix,
                 candle_data, preliminary_alert, imbalance_data, order_book_snapshot,
                 created_at_unix, updated_at_unix, alert_timestamp_readable, 
                 close_timestamp_readable, created_at_readable, updated_at_readable)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 
                        %s, %s, %s, %s, %s, %s)
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
                alert_timestamp_unix,
                close_timestamp_unix,
                candle_data_json,
                preliminary_alert_json,
                imbalance_data_json,
                order_book_snapshot_json,
                created_at_unix,
                created_at_unix,  # updated_at_unix
                alert_timestamp_readable,
                close_timestamp_readable,
                created_at_readable,
                created_at_readable  # updated_at_readable
            ))

            alert_id = cursor.fetchone()[0]
            cursor.close()
            
            return alert_id

        except Exception as e:
            logger.error(f"Ошибка сохранения алерта: {e}")
            return None

    async def update_alert(self, alert_id: int, alert_data: Dict):
        """Обновление алерта с UNIX временем"""
        try:
            cursor = self.connection.cursor()
            
            # Преобразуем datetime в UNIX timestamp
            close_timestamp_unix = None
            if alert_data.get('close_timestamp'):
                close_timestamp_unix = int(alert_data['close_timestamp'].timestamp() * 1000) if isinstance(alert_data['close_timestamp'], datetime) else int(alert_data['close_timestamp'])
            
            updated_at_unix = int(datetime.utcnow().timestamp() * 1000)
            
            # Создаем читаемые форматы времени
            close_timestamp_readable = self._unix_to_readable(close_timestamp_unix) if close_timestamp_unix else ''
            updated_at_readable = self._unix_to_readable(updated_at_unix)
            
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
                    close_timestamp_unix = %s, candle_data = %s, imbalance_data = %s, 
                    updated_at_unix = %s, close_timestamp_readable = %s, updated_at_readable = %s
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
                close_timestamp_unix,
                candle_data_json,
                imbalance_data_json,
                updated_at_unix,
                close_timestamp_readable,
                updated_at_readable,
                alert_id
            ))

            cursor.close()

        except Exception as e:
            logger.error(f"Ошибка обновления алерта: {e}")

    async def get_alerts_by_type(self, alert_type: str, limit: int = 50) -> List[Dict]:
        """Получить алерты по типу с UNIX временем"""
        try:
            cursor = self.connection.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT id, symbol, alert_type, price, volume_ratio, consecutive_count,
                       current_volume_usdt, average_volume_usdt, is_true_signal, 
                       is_closed, has_imbalance, message, telegram_sent, 
                       alert_timestamp_unix, close_timestamp_unix,
                       alert_timestamp_readable, close_timestamp_readable,
                       candle_data, preliminary_alert, imbalance_data, 
                       order_book_snapshot, created_at_unix, updated_at_unix
                FROM alerts 
                WHERE alert_type = %s
                ORDER BY COALESCE(close_timestamp_unix, alert_timestamp_unix) DESC
                LIMIT %s
            """, (alert_type, limit))

            result = cursor.fetchall()
            cursor.close()

            # Парсим JSON данные и преобразуем UNIX время в ISO формат для фронтенда
            alerts = []
            for row in result:
                alert = dict(row)
                
                # Преобразуем UNIX время в ISO формат для совместимости с фронтендом
                if alert['alert_timestamp_unix']:
                    alert['timestamp'] = datetime.utcfromtimestamp(alert['alert_timestamp_unix'] / 1000).isoformat()
                if alert['close_timestamp_unix']:
                    alert['close_timestamp'] = datetime.utcfromtimestamp(alert['close_timestamp_unix'] / 1000).isoformat()
                
                # Парсим JSON данные
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
        """Получить все алерты с UNIX временем"""
        try:
            cursor = self.connection.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT id, symbol, alert_type, price, volume_ratio, consecutive_count,
                       current_volume_usdt, average_volume_usdt, is_true_signal, 
                       is_closed, has_imbalance, message, telegram_sent,
                       alert_timestamp_unix, close_timestamp_unix,
                       alert_timestamp_readable, close_timestamp_readable,
                       candle_data, preliminary_alert, imbalance_data,
                       order_book_snapshot, created_at_unix, updated_at_unix
                FROM alerts 
                ORDER BY COALESCE(close_timestamp_unix, alert_timestamp_unix) DESC
                LIMIT %s
            """, (limit,))

            all_alerts_raw = cursor.fetchall()
            cursor.close()

            # Парсим JSON данные и преобразуем UNIX время
            all_alerts = []
            for row in all_alerts_raw:
                alert = dict(row)
                
                # Преобразуем UNIX время в ISO формат для совместимости с фронтендом
                if alert['alert_timestamp_unix']:
                    alert['timestamp'] = datetime.utcfromtimestamp(alert['alert_timestamp_unix'] / 1000).isoformat()
                if alert['close_timestamp_unix']:
                    alert['close_timestamp'] = datetime.utcfromtimestamp(alert['close_timestamp_unix'] / 1000).isoformat()
                
                # Парсим JSON данные
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

    async def cleanup_old_data(self, retention_hours: int = 2):
        """Очистка старых данных с UNIX временем"""
        try:
            cursor = self.connection.cursor()
            
            # Удаляем старые данные свечей
            cutoff_time_unix = int((datetime.utcnow() - timedelta(hours=retention_hours)).timestamp() * 1000)
            
            cursor.execute("""
                DELETE FROM kline_data 
                WHERE open_time_unix < %s
            """, (cutoff_time_unix,))
            
            deleted_klines = cursor.rowcount
            
            # Очищаем старые потоковые данные (старше 5 минут)
            stream_cutoff_unix = int((datetime.utcnow() - timedelta(minutes=5)).timestamp() * 1000)
            cursor.execute("""
                DELETE FROM kline_stream 
                WHERE last_update_unix < %s
            """, (stream_cutoff_unix,))
            
            deleted_stream = cursor.rowcount
            
            # Удаляем старые алерты (старше 24 часов)
            alert_cutoff_unix = int((datetime.utcnow() - timedelta(hours=24)).timestamp() * 1000)
            cursor.execute("""
                DELETE FROM alerts 
                WHERE created_at_unix < %s
            """, (alert_cutoff_unix,))
            
            deleted_alerts = cursor.rowcount
            
            cursor.close()
            
            logger.info(f"Очищено {deleted_klines} записей свечей, {deleted_stream} потоковых записей и {deleted_alerts} алертов")

        except Exception as e:
            logger.error(f"Ошибка очистки старых данных: {e}")

    # Остальные методы остаются без изменений, но с обновлением для UNIX времени
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
                       current_price, historical_price, 
                       created_at_unix, updated_at_unix,
                       created_at_readable, updated_at_readable
                FROM watchlist 
                ORDER BY 
                    CASE WHEN price_drop_percentage IS NOT NULL THEN price_drop_percentage ELSE 0 END DESC,
                    symbol ASC
            """)

            result = cursor.fetchall()
            cursor.close()

            # Преобразуем UNIX время в ISO формат для совместимости
            watchlist_items = []
            for row in result:
                item = dict(row)
                if item['created_at_unix']:
                    item['created_at'] = datetime.utcfromtimestamp(item['created_at_unix'] / 1000).isoformat()
                if item['updated_at_unix']:
                    item['updated_at'] = datetime.utcfromtimestamp(item['updated_at_unix'] / 1000).isoformat()
                watchlist_items.append(item)

            return watchlist_items

        except Exception as e:
            logger.error(f"Ошибка получения детальной информации watchlist: {e}")
            return []

    async def add_to_watchlist(self, symbol: str, price_drop: float = None,
                               current_price: float = None, historical_price: float = None):
        """Добавить торговую пару в watchlist с UNIX временем"""
        try:
            cursor = self.connection.cursor()
            
            created_at_unix = int(datetime.utcnow().timestamp() * 1000)
            created_at_readable = self._unix_to_readable(created_at_unix)
            
            cursor.execute("""
                INSERT INTO watchlist (symbol, price_drop_percentage, current_price, historical_price, 
                                     created_at_unix, updated_at_unix, created_at_readable, updated_at_readable) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s) 
                ON CONFLICT (symbol) DO UPDATE SET
                    is_active = TRUE,
                    price_drop_percentage = EXCLUDED.price_drop_percentage,
                    current_price = EXCLUDED.current_price,
                    historical_price = EXCLUDED.historical_price,
                    updated_at_unix = EXCLUDED.updated_at_unix,
                    updated_at_readable = EXCLUDED.updated_at_readable
            """, (symbol, price_drop, current_price, historical_price, 
                  created_at_unix, created_at_unix, created_at_readable, created_at_readable))

            cursor.close()

        except Exception as e:
            logger.error(f"Ошибка добавления в watchlist: {e}")

    async def update_watchlist_item(self, item_id: int, symbol: str, is_active: bool):
        """Обновить элемент watchlist с UNIX временем"""
        try:
            cursor = self.connection.cursor()
            
            updated_at_unix = int(datetime.utcnow().timestamp() * 1000)
            updated_at_readable = self._unix_to_readable(updated_at_unix)
            
            cursor.execute("""
                UPDATE watchlist 
                SET symbol = %s, is_active = %s, updated_at_unix = %s, updated_at_readable = %s
                WHERE id = %s
            """, (symbol, is_active, updated_at_unix, updated_at_readable, item_id))

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

    async def get_recent_volume_alerts(self, symbol: str, minutes_back: int) -> List[Dict]:
        """Получить недавние объемные алерты для символа с UNIX временем"""
        try:
            cursor = self.connection.cursor(cursor_factory=RealDictCursor)
            
            cutoff_time_unix = int((datetime.utcnow() - timedelta(minutes=minutes_back)).timestamp() * 1000)
            
            cursor.execute("""
                SELECT * FROM alerts 
                WHERE symbol = %s 
                AND alert_type = 'volume_spike'
                AND alert_timestamp_unix >= %s
                ORDER BY alert_timestamp_unix DESC
            """, (symbol, cutoff_time_unix))

            result = cursor.fetchall()
            cursor.close()

            return [dict(row) for row in result]

        except Exception as e:
            logger.error(f"Ошибка получения недавних объемных алертов для {symbol}: {e}")
            return []

    async def mark_telegram_sent(self, alert_id: int):
        """Отметить алерт как отправленный в Telegram с UNIX временем"""
        try:
            cursor = self.connection.cursor()
            
            updated_at_unix = int(datetime.utcnow().timestamp() * 1000)
            updated_at_readable = self._unix_to_readable(updated_at_unix)
            
            cursor.execute("""
                UPDATE alerts SET telegram_sent = TRUE, updated_at_unix = %s, updated_at_readable = %s 
                WHERE id = %s
            """, (updated_at_unix, updated_at_readable, alert_id))
            cursor.close()

        except Exception as e:
            logger.error(f"Ошибка отметки Telegram: {e}")

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

    def close(self):
        """Закрытие соединения с базой данных"""
        if self.connection:
            self.connection.close()