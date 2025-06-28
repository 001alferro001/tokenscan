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
        """Создание необходимых таблиц с UNIX временем"""
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
                    created_at_unix BIGINT DEFAULT EXTRACT(EPOCH FROM NOW()) * 1000,
                    updated_at_unix BIGINT DEFAULT EXTRACT(EPOCH FROM NOW()) * 1000,
                    created_at_readable VARCHAR(30),
                    updated_at_readable VARCHAR(30),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Создаем основную таблицу для исторических данных свечей (UNIX время)
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
                    is_closed BOOLEAN DEFAULT TRUE,
                    open_time_readable VARCHAR(30),
                    close_time_readable VARCHAR(30),
                    created_at_unix BIGINT DEFAULT EXTRACT(EPOCH FROM NOW()) * 1000,
                    created_at_readable VARCHAR(30),
                    open_time BIGINT,
                    close_time BIGINT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(symbol, open_time_unix)
                )
            """)

            # Создаем таблицу для потоковых данных (с миллисекундами)
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
                    is_closed BOOLEAN DEFAULT FALSE,
                    last_update_unix BIGINT DEFAULT EXTRACT(EPOCH FROM NOW()) * 1000,
                    open_time_readable VARCHAR(30),
                    close_time_readable VARCHAR(30),
                    last_update_readable VARCHAR(30),
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
                    alert_timestamp_readable VARCHAR(30),
                    close_timestamp_readable VARCHAR(30),
                    candle_data JSONB,
                    preliminary_alert JSONB,
                    imbalance_data JSONB,
                    order_book_snapshot JSONB,
                    created_at_unix BIGINT DEFAULT EXTRACT(EPOCH FROM NOW()) * 1000,
                    updated_at_unix BIGINT DEFAULT EXTRACT(EPOCH FROM NOW()) * 1000,
                    created_at_readable VARCHAR(30),
                    updated_at_readable VARCHAR(30),
                    alert_timestamp TIMESTAMP,
                    close_timestamp TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Создаем индексы для оптимизации запросов
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_kline_symbol_time_unix 
                ON kline_data(symbol, open_time_unix)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_kline_symbol_long_time_unix 
                ON kline_data(symbol, is_long, open_time_unix)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_kline_stream_symbol_time_unix 
                ON kline_stream(symbol, open_time_unix)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_alerts_symbol_type_time_unix 
                ON alerts(symbol, alert_type, alert_timestamp_unix)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_alerts_type_created_unix 
                ON alerts(alert_type, created_at_unix)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_alerts_close_timestamp_unix 
                ON alerts(close_timestamp_unix DESC NULLS LAST)
            """)

            cursor.close()
            logger.info("Таблицы с UNIX временем успешно созданы")

        except Exception as e:
            logger.error(f"Ошибка создания таблиц: {e}")
            raise

    async def update_tables(self):
        """Обновление существующих таблиц для добавления UNIX столбцов"""
        try:
            cursor = self.connection.cursor()

            # Добавляем UNIX столбцы в существующие таблицы, если их нет
            tables_to_update = [
                ('watchlist', [
                    ('created_at_unix', 'BIGINT'),
                    ('updated_at_unix', 'BIGINT'),
                    ('created_at_readable', 'VARCHAR(30)'),
                    ('updated_at_readable', 'VARCHAR(30)')
                ]),
                ('kline_data', [
                    ('open_time_unix', 'BIGINT'),
                    ('close_time_unix', 'BIGINT'),
                    ('is_closed', 'BOOLEAN DEFAULT TRUE'),
                    ('open_time_readable', 'VARCHAR(30)'),
                    ('close_time_readable', 'VARCHAR(30)'),
                    ('created_at_unix', 'BIGINT'),
                    ('created_at_readable', 'VARCHAR(30)')
                ]),
                ('alerts', [
                    ('alert_timestamp_unix', 'BIGINT'),
                    ('close_timestamp_unix', 'BIGINT'),
                    ('alert_timestamp_readable', 'VARCHAR(30)'),
                    ('close_timestamp_readable', 'VARCHAR(30)'),
                    ('created_at_unix', 'BIGINT'),
                    ('updated_at_unix', 'BIGINT'),
                    ('created_at_readable', 'VARCHAR(30)'),
                    ('updated_at_readable', 'VARCHAR(30)')
                ])
            ]

            for table_name, columns in tables_to_update:
                for column_name, column_type in columns:
                    try:
                        cursor.execute(f"""
                            ALTER TABLE {table_name} 
                            ADD COLUMN IF NOT EXISTS {column_name} {column_type}
                        """)
                    except Exception as e:
                        logger.debug(f"Столбец {column_name} уже существует в {table_name}: {e}")

            # Заполняем UNIX столбцы из существующих timestamp столбцов
            cursor.execute("""
                UPDATE kline_data 
                SET open_time_unix = EXTRACT(EPOCH FROM TO_TIMESTAMP(open_time/1000)) * 1000,
                    close_time_unix = EXTRACT(EPOCH FROM TO_TIMESTAMP(close_time/1000)) * 1000
                WHERE open_time_unix IS NULL AND open_time IS NOT NULL
            """)

            cursor.execute("""
                UPDATE alerts 
                SET alert_timestamp_unix = EXTRACT(EPOCH FROM alert_timestamp) * 1000,
                    close_timestamp_unix = EXTRACT(EPOCH FROM close_timestamp) * 1000
                WHERE alert_timestamp_unix IS NULL AND alert_timestamp IS NOT NULL
            """)

            # Заполняем читаемые столбцы
            await self._update_readable_timestamps()

            cursor.close()
            logger.info("Таблицы успешно обновлены для UNIX времени")

        except Exception as e:
            logger.error(f"Ошибка обновления таблиц: {e}")

    async def _update_readable_timestamps(self):
        """Обновление читаемых временных меток"""
        try:
            cursor = self.connection.cursor()

            # Обновляем читаемые метки для kline_data
            cursor.execute("""
                UPDATE kline_data 
                SET open_time_readable = TO_CHAR(TO_TIMESTAMP(open_time_unix/1000), 'DD.MM.YYYY HH24:MI:SS:MS'),
                    close_time_readable = TO_CHAR(TO_TIMESTAMP(close_time_unix/1000), 'DD.MM.YYYY HH24:MI:SS:MS'),
                    created_at_readable = TO_CHAR(TO_TIMESTAMP(created_at_unix/1000), 'DD.MM.YYYY HH24:MI:SS:MS')
                WHERE open_time_unix IS NOT NULL AND open_time_readable IS NULL
            """)

            # Обновляем читаемые метки для alerts
            cursor.execute("""
                UPDATE alerts 
                SET alert_timestamp_readable = TO_CHAR(TO_TIMESTAMP(alert_timestamp_unix/1000), 'DD.MM.YYYY HH24:MI:SS:MS'),
                    close_timestamp_readable = TO_CHAR(TO_TIMESTAMP(close_timestamp_unix/1000), 'DD.MM.YYYY HH24:MI:SS:MS'),
                    created_at_readable = TO_CHAR(TO_TIMESTAMP(created_at_unix/1000), 'DD.MM.YYYY HH24:MI:SS:MS'),
                    updated_at_readable = TO_CHAR(TO_TIMESTAMP(updated_at_unix/1000), 'DD.MM.YYYY HH24:MI:SS:MS')
                WHERE alert_timestamp_unix IS NOT NULL AND alert_timestamp_readable IS NULL
            """)

            cursor.close()

        except Exception as e:
            logger.error(f"Ошибка обновления читаемых временных меток: {e}")

    def _unix_to_readable(self, unix_timestamp: int) -> str:
        """Преобразование UNIX времени в читаемый формат"""
        try:
            dt = datetime.utcfromtimestamp(unix_timestamp / 1000)
            return dt.strftime('%d.%m.%Y %H:%M:%S:%f')[:-3]  # Убираем последние 3 цифры микросекунд
        except:
            return ""

    async def check_data_integrity(self, symbol: str, hours: int) -> Dict:
        """Проверка целостности исторических данных с UNIX временем"""
        try:
            cursor = self.connection.cursor()

            # Определяем временные границы в UNIX формате
            current_time_unix = int(datetime.utcnow().timestamp() * 1000)
            # Округляем до начала текущей минуты
            current_minute_unix = (current_time_unix // 60000) * 60000
            end_time_unix = current_minute_unix
            start_time_unix = end_time_unix - (hours * 60 * 60 * 1000)

            # Получаем существующие данные
            cursor.execute("""
                SELECT open_time_unix FROM kline_data 
                WHERE symbol = %s AND open_time_unix >= %s AND open_time_unix < %s
                ORDER BY open_time_unix
            """, (symbol, start_time_unix, end_time_unix))

            existing_times = [row[0] for row in cursor.fetchall()]
            cursor.close()

            # Генерируем ожидаемые временные метки (каждую минуту с нулями)
            expected_times = []
            current_time_ms = start_time_unix
            while current_time_ms < end_time_unix:
                expected_times.append(current_time_ms)
                current_time_ms += 60000  # +1 минута

            # Находим недостающие периоды
            missing_times = [t for t in expected_times if t not in existing_times]

            # Исключаем самые последние 2-3 минуты
            cutoff_time_unix = end_time_unix - (3 * 60 * 1000)
            missing_times = [t for t in missing_times if t < cutoff_time_unix]

            total_expected = len([t for t in expected_times if t < cutoff_time_unix])
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
                       created_at_readable, updated_at_readable,
                       created_at, updated_at
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
            current_time_unix = int(datetime.utcnow().timestamp() * 1000)
            readable_time = self._unix_to_readable(current_time_unix)

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
                    updated_at_readable = EXCLUDED.updated_at_readable,
                    updated_at = CURRENT_TIMESTAMP
            """, (symbol, price_drop, current_price, historical_price,
                  current_time_unix, current_time_unix, readable_time, readable_time))

            cursor.close()

        except Exception as e:
            logger.error(f"Ошибка добавления в watchlist: {e}")

    async def update_watchlist_item(self, item_id: int, symbol: str, is_active: bool):
        """Обновить элемент watchlist"""
        try:
            cursor = self.connection.cursor()
            current_time_unix = int(datetime.utcnow().timestamp() * 1000)
            readable_time = self._unix_to_readable(current_time_unix)

            cursor.execute("""
                UPDATE watchlist 
                SET symbol = %s, is_active = %s, 
                    updated_at_unix = %s, updated_at_readable = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (symbol, is_active, current_time_unix, readable_time, item_id))

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

    async def save_kline_data(self, symbol: str, kline_data: Dict, is_closed: bool = False):
        """Сохранение данных свечи в базу данных с UNIX временем"""
        try:
            cursor = self.connection.cursor()

            # Получаем UNIX время из данных биржи
            open_time_unix = int(kline_data['start'])
            close_time_unix = int(kline_data['end'])

            # Определяем, является ли свеча LONG
            is_long = float(kline_data['close']) > float(kline_data['open'])

            # Рассчитываем объем в USDT
            volume_usdt = float(kline_data['volume']) * float(kline_data['close'])

            # Создаем читаемые временные метки
            open_time_readable = self._unix_to_readable(open_time_unix)
            close_time_readable = self._unix_to_readable(close_time_unix)
            current_time_unix = int(datetime.utcnow().timestamp() * 1000)
            created_at_readable = self._unix_to_readable(current_time_unix)

            if is_closed:
                # Сохраняем в основную таблицу исторических данных
                cursor.execute("""
                    INSERT INTO kline_data 
                    (symbol, open_time_unix, close_time_unix, open_price, high_price, 
                     low_price, close_price, volume, volume_usdt, is_long, is_closed,
                     open_time_readable, close_time_readable, created_at_unix, created_at_readable,
                     open_time, close_time)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                    float(kline_data['volume']), volume_usdt, is_long, is_closed,
                    open_time_readable, close_time_readable, current_time_unix, created_at_readable,
                    open_time_unix, close_time_unix  # Для совместимости
                ))
            else:
                # Сохраняем в таблицу потоковых данных
                cursor.execute("""
                    INSERT INTO kline_stream 
                    (symbol, open_time_unix, close_time_unix, open_price, high_price, 
                     low_price, close_price, volume, volume_usdt, is_long, is_closed,
                     last_update_unix, open_time_readable, close_time_readable, last_update_readable)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (symbol, open_time_unix) DO UPDATE SET
                        close_time_unix = EXCLUDED.close_time_unix,
                        high_price = GREATEST(kline_stream.high_price, EXCLUDED.high_price),
                        low_price = LEAST(kline_stream.low_price, EXCLUDED.low_price),
                        close_price = EXCLUDED.close_price,
                        volume = EXCLUDED.volume,
                        volume_usdt = EXCLUDED.volume_usdt,
                        is_long = EXCLUDED.is_long,
                        last_update_unix = EXCLUDED.last_update_unix,
                        last_update_readable = EXCLUDED.last_update_readable
                """, (
                    symbol, open_time_unix, close_time_unix,
                    float(kline_data['open']), float(kline_data['high']),
                    float(kline_data['low']), float(kline_data['close']),
                    float(kline_data['volume']), volume_usdt, is_long, is_closed,
                    current_time_unix, open_time_readable, close_time_readable, created_at_readable
                ))

            cursor.close()

        except Exception as e:
            logger.error(f"Ошибка сохранения данных свечи: {e}")

    async def save_alert(self, alert_data: Dict) -> int:
        """Сохранение алерта в базу данных с UNIX временем"""
        try:
            cursor = self.connection.cursor()

            # Преобразуем datetime в UNIX время
            alert_timestamp_unix = int(alert_data['timestamp'].timestamp() * 1000) if isinstance(
                alert_data['timestamp'], datetime) else int(alert_data['timestamp'])
            close_timestamp_unix = None
            if alert_data.get('close_timestamp'):
                if isinstance(alert_data['close_timestamp'], datetime):
                    close_timestamp_unix = int(alert_data['close_timestamp'].timestamp() * 1000)
                else:
                    close_timestamp_unix = int(alert_data['close_timestamp'])

            # Создаем читаемые временные метки
            alert_timestamp_readable = self._unix_to_readable(alert_timestamp_unix)
            close_timestamp_readable = self._unix_to_readable(close_timestamp_unix) if close_timestamp_unix else None
            current_time_unix = int(datetime.utcnow().timestamp() * 1000)
            created_at_readable = self._unix_to_readable(current_time_unix)

            # Подготавливаем JSON данные (исправляем проблему с парсингом)
            candle_data_json = None
            if 'candle_data' in alert_data and alert_data['candle_data']:
                if isinstance(alert_data['candle_data'], str):
                    candle_data_json = alert_data['candle_data']
                else:
                    candle_data_json = json.dumps(alert_data['candle_data'])

            preliminary_alert_json = None
            if 'preliminary_alert' in alert_data and alert_data['preliminary_alert']:
                if isinstance(alert_data['preliminary_alert'], str):
                    preliminary_alert_json = alert_data['preliminary_alert']
                else:
                    preliminary_alert_json = json.dumps(alert_data['preliminary_alert'], default=str)

            imbalance_data_json = None
            if 'imbalance_data' in alert_data and alert_data['imbalance_data']:
                if isinstance(alert_data['imbalance_data'], str):
                    imbalance_data_json = alert_data['imbalance_data']
                else:
                    imbalance_data_json = json.dumps(alert_data['imbalance_data'])

            order_book_snapshot_json = None
            if 'order_book_snapshot' in alert_data and alert_data['order_book_snapshot']:
                if isinstance(alert_data['order_book_snapshot'], str):
                    order_book_snapshot_json = alert_data['order_book_snapshot']
                else:
                    order_book_snapshot_json = json.dumps(alert_data['order_book_snapshot'])

            cursor.execute("""
                INSERT INTO alerts 
                (symbol, alert_type, price, volume_ratio, consecutive_count,
                 current_volume_usdt, average_volume_usdt, is_true_signal, 
                 is_closed, has_imbalance, message, 
                 alert_timestamp_unix, close_timestamp_unix,
                 alert_timestamp_readable, close_timestamp_readable,
                 created_at_unix, updated_at_unix, created_at_readable, updated_at_readable,
                 candle_data, preliminary_alert, imbalance_data, order_book_snapshot,
                 alert_timestamp, close_timestamp)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                alert_timestamp_readable,
                close_timestamp_readable,
                current_time_unix,
                current_time_unix,
                created_at_readable,
                created_at_readable,
                candle_data_json,
                preliminary_alert_json,
                imbalance_data_json,
                order_book_snapshot_json,
                alert_data['timestamp'] if isinstance(alert_data['timestamp'], datetime) else datetime.utcfromtimestamp(
                    alert_timestamp_unix / 1000),
                alert_data.get('close_timestamp') if isinstance(alert_data.get('close_timestamp'), datetime) else (
                    datetime.utcfromtimestamp(close_timestamp_unix / 1000) if close_timestamp_unix else None)
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

            # Преобразуем datetime в UNIX время
            close_timestamp_unix = None
            if alert_data.get('close_timestamp'):
                if isinstance(alert_data['close_timestamp'], datetime):
                    close_timestamp_unix = int(alert_data['close_timestamp'].timestamp() * 1000)
                else:
                    close_timestamp_unix = int(alert_data['close_timestamp'])

            close_timestamp_readable = self._unix_to_readable(close_timestamp_unix) if close_timestamp_unix else None
            current_time_unix = int(datetime.utcnow().timestamp() * 1000)
            updated_at_readable = self._unix_to_readable(current_time_unix)

            # Подготавливаем JSON данные
            candle_data_json = None
            if 'candle_data' in alert_data and alert_data['candle_data']:
                if isinstance(alert_data['candle_data'], str):
                    candle_data_json = alert_data['candle_data']
                else:
                    candle_data_json = json.dumps(alert_data['candle_data'])

            imbalance_data_json = None
            if 'imbalance_data' in alert_data and alert_data['imbalance_data']:
                if isinstance(alert_data['imbalance_data'], str):
                    imbalance_data_json = alert_data['imbalance_data']
                else:
                    imbalance_data_json = json.dumps(alert_data['imbalance_data'])

            cursor.execute("""
                UPDATE alerts 
                SET price = %s, volume_ratio = %s, consecutive_count = %s,
                    current_volume_usdt = %s, average_volume_usdt = %s,
                    is_true_signal = %s, is_closed = %s, has_imbalance = %s, message = %s,
                    close_timestamp_unix = %s, close_timestamp_readable = %s,
                    updated_at_unix = %s, updated_at_readable = %s,
                    candle_data = %s, imbalance_data = %s,
                    close_timestamp = %s, updated_at = CURRENT_TIMESTAMP
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
                close_timestamp_readable,
                current_time_unix,
                updated_at_readable,
                candle_data_json,
                imbalance_data_json,
                alert_data.get('close_timestamp') if isinstance(alert_data.get('close_timestamp'), datetime) else (
                    datetime.utcfromtimestamp(close_timestamp_unix / 1000) if close_timestamp_unix else None),
                alert_id
            ))

            cursor.close()

        except Exception as e:
            logger.error(f"Ошибка обновления алерта: {e}")

    async def get_alerts_by_type(self, alert_type: str, limit: int = 50) -> List[Dict]:
        """Получить алерты по типу с сортировкой по UNIX времени"""
        try:
            cursor = self.connection.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT id, symbol, alert_type, price, volume_ratio, consecutive_count,
                       current_volume_usdt, average_volume_usdt, is_true_signal, 
                       is_closed, has_imbalance, message, telegram_sent, 
                       alert_timestamp_unix, close_timestamp_unix,
                       alert_timestamp_readable, close_timestamp_readable,
                       candle_data, preliminary_alert, imbalance_data, 
                       order_book_snapshot, created_at_unix, updated_at_unix,
                       alert_timestamp as timestamp, close_timestamp, created_at, updated_at
                FROM alerts 
                WHERE alert_type = %s
                ORDER BY COALESCE(close_timestamp_unix, alert_timestamp_unix) DESC
                LIMIT %s
            """, (alert_type, limit))

            result = cursor.fetchall()
            cursor.close()

            # Парсим JSON данные с проверкой типов
            alerts = []
            for row in result:
                alert = dict(row)

                # Безопасный парсинг JSON
                for json_field in ['candle_data', 'preliminary_alert', 'imbalance_data', 'order_book_snapshot']:
                    if alert[json_field]:
                        try:
                            if isinstance(alert[json_field], str):
                                alert[json_field] = json.loads(alert[json_field])
                            # Если уже dict/list, оставляем как есть
                        except (json.JSONDecodeError, TypeError) as e:
                            logger.warning(f"Ошибка парсинга {json_field} для алерта {alert['id']}: {e}")
                            alert[json_field] = None

                alerts.append(alert)

            return alerts

        except Exception as e:
            logger.error(f"Ошибка получения алертов по типу {alert_type}: {e}")
            return []

    async def get_all_alerts(self, limit: int = 100) -> Dict[str, List[Dict]]:
        """Получить все алерты, разделенные по типам с сортировкой по UNIX времени"""
        try:
            cursor = self.connection.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT id, symbol, alert_type, price, volume_ratio, consecutive_count,
                       current_volume_usdt, average_volume_usdt, is_true_signal, 
                       is_closed, has_imbalance, message, telegram_sent,
                       alert_timestamp_unix, close_timestamp_unix,
                       alert_timestamp_readable, close_timestamp_readable,
                       candle_data, preliminary_alert, imbalance_data,
                       order_book_snapshot, created_at_unix, updated_at_unix,
                       alert_timestamp as timestamp, close_timestamp, created_at, updated_at
                FROM alerts 
                ORDER BY COALESCE(close_timestamp_unix, alert_timestamp_unix) DESC
                LIMIT %s
            """, (limit,))

            all_alerts_raw = cursor.fetchall()
            cursor.close()

            # Парсим JSON данные с проверкой типов
            all_alerts = []
            for row in all_alerts_raw:
                alert = dict(row)

                # Безопасный парсинг JSON
                for json_field in ['candle_data', 'preliminary_alert', 'imbalance_data', 'order_book_snapshot']:
                    if alert[json_field]:
                        try:
                            if isinstance(alert[json_field], str):
                                alert[json_field] = json.loads(alert[json_field])
                            # Если уже dict/list, оставляем как есть
                        except (json.JSONDecodeError, TypeError) as e:
                            logger.warning(f"Ошибка парсинга {json_field} для алерта {alert['id']}: {e}")
                            alert[json_field] = None

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

    async def get_historical_long_volumes(self, symbol: str, hours: int, offset_minutes: int = 0,
                                          volume_type: str = 'long') -> List[float]:
        """Получить объемы свечей за указанный период с UNIX временем"""
        try:
            cursor = self.connection.cursor()

            # Рассчитываем временные границы в UNIX формате
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

    async def get_recent_candles(self, symbol: str, count: int) -> List[Dict]:
        """Получить последние свечи для символа"""
        try:
            cursor = self.connection.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT open_time_unix as timestamp, open_price as open, high_price as high,
                       low_price as low, close_price as close, volume, volume_usdt, is_long, is_closed
                FROM kline_data 
                WHERE symbol = %s AND is_closed = TRUE
                ORDER BY open_time_unix DESC
                LIMIT %s
            """, (symbol, count))

            result = cursor.fetchall()
            cursor.close()

            candles = []
            for row in result:
                candles.append({
                    'timestamp': int(row['timestamp']),
                    'open': float(row['open']),
                    'high': float(row['high']),
                    'low': float(row['low']),
                    'close': float(row['close']),
                    'volume': float(row['volume']),
                    'volume_usdt': float(row['volume_usdt']),
                    'is_long': row['is_long'],
                    'is_closed': row['is_closed']
                })

            return list(reversed(candles))  # Возвращаем в хронологическом порядке

        except Exception as e:
            logger.error(f"Ошибка получения последних свечей для {symbol}: {e}")
            return []

    async def get_chart_data(self, symbol: str, hours: int = 1, alert_time: str = None) -> List[Dict]:
        """Получить данные для построения графика с UNIX временем"""
        try:
            cursor = self.connection.cursor(cursor_factory=RealDictCursor)

            # Определяем временные границы в UNIX формате
            if alert_time:
                try:
                    alert_dt = datetime.fromisoformat(alert_time.replace('Z', '+00:00'))
                    end_time_unix = int(alert_dt.timestamp() * 1000)
                except:
                    end_time_unix = int(datetime.utcnow().timestamp() * 1000)
            else:
                end_time_unix = int(datetime.utcnow().timestamp() * 1000)

            start_time_unix = end_time_unix - (hours * 60 * 60 * 1000)

            cursor.execute("""
                SELECT open_time_unix as timestamp, open_price as open, high_price as high,
                       low_price as low, close_price as close, volume, volume_usdt, is_long
                FROM kline_data 
                WHERE symbol = %s 
                AND open_time_unix >= %s 
                AND open_time_unix <= %s
                AND is_closed = TRUE
                ORDER BY open_time_unix
            """, (symbol, start_time_unix, end_time_unix))

            result = cursor.fetchall()
            cursor.close()

            chart_data = []
            for row in result:
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

            logger.info(f"Получено {len(chart_data)} свечей для {symbol} за период {hours}ч")
            return chart_data

        except Exception as e:
            logger.error(f"Ошибка получения данных графика для {symbol}: {e}")
            return []

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

            # Очищаем потоковые данные
            cursor.execute("""
                DELETE FROM kline_stream 
                WHERE open_time_unix < %s
            """, (cutoff_time_unix,))

            deleted_stream = cursor.rowcount

            # Удаляем старые алерты (старше 24 часов)
            alert_cutoff_unix = int((datetime.utcnow() - timedelta(hours=24)).timestamp() * 1000)
            cursor.execute("""
                DELETE FROM alerts 
                WHERE created_at_unix < %s
            """, (alert_cutoff_unix,))

            deleted_alerts = cursor.rowcount

            cursor.close()

            logger.info(
                f"Очищено {deleted_klines} записей свечей, {deleted_stream} потоковых записей и {deleted_alerts} алертов")

        except Exception as e:
            logger.error(f"Ошибка очистки старых данных: {e}")

    async def mark_telegram_sent(self, alert_id: int):
        """Отметить алерт как отправленный в Telegram"""
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                UPDATE alerts SET telegram_sent = TRUE WHERE id = %s
            """, (alert_id,))
            cursor.close()

        except Exception as e:
            logger.error(f"Ошибка отметки Telegram: {e}")

    def close(self):
        """Закрытие соединения с базой данных"""
        if self.connection:
            self.connection.close()