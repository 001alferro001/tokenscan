import asyncio
import logging
from typing import List, Dict, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta, timezone
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
                    is_favorite BOOLEAN DEFAULT FALSE,
                    price_drop_percentage DECIMAL(5, 2),
                    current_price DECIMAL(20, 8),
                    historical_price DECIMAL(20, 8),
                    notes TEXT,
                    color VARCHAR(20) DEFAULT '#FFD700',
                    sort_order INTEGER,
                    favorite_added_at_ms BIGINT,
                    created_at_ms BIGINT DEFAULT EXTRACT(EPOCH FROM NOW()) * 1000,
                    updated_at_ms BIGINT DEFAULT EXTRACT(EPOCH FROM NOW()) * 1000,
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
                    open_time_ms BIGINT NOT NULL,
                    close_time_ms BIGINT NOT NULL,
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
                    created_at_ms BIGINT DEFAULT EXTRACT(EPOCH FROM NOW()) * 1000,
                    created_at_readable VARCHAR(30),
                    open_time BIGINT,
                    close_time BIGINT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(symbol, open_time_ms)
                )
            """)

            # Создаем таблицу для потоковых данных (с миллисекундами)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS kline_stream (
                    id SERIAL PRIMARY KEY,
                    symbol VARCHAR(20) NOT NULL,
                    open_time_ms BIGINT NOT NULL,
                    close_time_ms BIGINT NOT NULL,
                    open_price DECIMAL(20, 8) NOT NULL,
                    high_price DECIMAL(20, 8) NOT NULL,
                    low_price DECIMAL(20, 8) NOT NULL,
                    close_price DECIMAL(20, 8) NOT NULL,
                    volume DECIMAL(20, 8) NOT NULL,
                    volume_usdt DECIMAL(20, 8) NOT NULL,
                    is_long BOOLEAN NOT NULL,
                    is_closed BOOLEAN DEFAULT FALSE,
                    last_update_ms BIGINT DEFAULT EXTRACT(EPOCH FROM NOW()) * 1000,
                    open_time_readable VARCHAR(30),
                    close_time_readable VARCHAR(30),
                    last_update_readable VARCHAR(30),
                    UNIQUE(symbol, open_time_ms)
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
                    alert_timestamp_ms BIGINT NOT NULL,
                    close_timestamp_ms BIGINT,
                    alert_timestamp_readable VARCHAR(30),
                    close_timestamp_readable VARCHAR(30),
                    candle_data JSONB,
                    preliminary_alert JSONB,
                    imbalance_data JSONB,
                    order_book_snapshot JSONB,
                    created_at_ms BIGINT DEFAULT EXTRACT(EPOCH FROM NOW()) * 1000,
                    updated_at_ms BIGINT DEFAULT EXTRACT(EPOCH FROM NOW()) * 1000,
                    created_at_readable VARCHAR(30),
                    updated_at_readable VARCHAR(30),
                    alert_timestamp TIMESTAMP,
                    close_timestamp TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Таблица для бумажной торговли
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS paper_trades (
                    id SERIAL PRIMARY KEY,
                    symbol VARCHAR(20) NOT NULL,
                    trade_type VARCHAR(10) NOT NULL,
                    entry_price DECIMAL(20, 8) NOT NULL,
                    quantity DECIMAL(20, 8) NOT NULL,
                    stop_loss DECIMAL(20, 8),
                    take_profit DECIMAL(20, 8),
                    risk_amount DECIMAL(20, 2),
                    risk_percentage DECIMAL(5, 2),
                    potential_profit DECIMAL(20, 2),
                    potential_loss DECIMAL(20, 2),
                    risk_reward_ratio DECIMAL(10, 2),
                    status VARCHAR(20) DEFAULT 'OPEN',
                    exit_price DECIMAL(20, 8),
                    exit_reason VARCHAR(50),
                    pnl DECIMAL(20, 2),
                    pnl_percentage DECIMAL(10, 2),
                    notes TEXT,
                    alert_id INTEGER,
                    opened_at_ms BIGINT NOT NULL,
                    closed_at_ms BIGINT,
                    created_at_ms BIGINT DEFAULT EXTRACT(EPOCH FROM NOW()) * 1000,
                    updated_at_ms BIGINT DEFAULT EXTRACT(EPOCH FROM NOW()) * 1000
                )
            """)

            # Таблица для настроек торговли
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trading_settings (
                    id SERIAL PRIMARY KEY,
                    account_balance DECIMAL(20, 2) DEFAULT 10000,
                    max_risk_per_trade DECIMAL(5, 2) DEFAULT 2.0,
                    max_open_trades INTEGER DEFAULT 5,
                    default_stop_loss_percentage DECIMAL(5, 2) DEFAULT 2.0,
                    default_take_profit_percentage DECIMAL(5, 2) DEFAULT 6.0,
                    auto_calculate_quantity BOOLEAN DEFAULT TRUE,
                    api_key TEXT,
                    api_secret TEXT,
                    enable_real_trading BOOLEAN DEFAULT FALSE,
                    default_leverage INTEGER DEFAULT 1,
                    default_margin_type VARCHAR(20) DEFAULT 'isolated',
                    confirm_trades BOOLEAN DEFAULT TRUE,
                    updated_at_ms BIGINT DEFAULT EXTRACT(EPOCH FROM NOW()) * 1000
                )
            """)

            # Таблица для реальных сделок
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS real_trades (
                    id SERIAL PRIMARY KEY,
                    symbol VARCHAR(20) NOT NULL,
                    trade_type VARCHAR(10) NOT NULL,
                    entry_price DECIMAL(20, 8) NOT NULL,
                    quantity DECIMAL(20, 8) NOT NULL,
                    stop_loss DECIMAL(20, 8),
                    take_profit DECIMAL(20, 8),
                    risk_amount DECIMAL(20, 2),
                    risk_percentage DECIMAL(5, 2),
                    potential_profit DECIMAL(20, 2),
                    potential_loss DECIMAL(20, 2),
                    risk_reward_ratio DECIMAL(10, 2),
                    status VARCHAR(20) DEFAULT 'PENDING',
                    exit_price DECIMAL(20, 8),
                    exit_reason VARCHAR(50),
                    pnl DECIMAL(20, 2),
                    pnl_percentage DECIMAL(10, 2),
                    notes TEXT,
                    alert_id INTEGER,
                    order_id VARCHAR(100),
                    leverage INTEGER DEFAULT 1,
                    margin_type VARCHAR(20) DEFAULT 'isolated',
                    opened_at_ms BIGINT NOT NULL,
                    closed_at_ms BIGINT,
                    created_at_ms BIGINT DEFAULT EXTRACT(EPOCH FROM NOW()) * 1000,
                    updated_at_ms BIGINT DEFAULT EXTRACT(EPOCH FROM NOW()) * 1000
                )
            """)

            # Создаем индексы для оптимизации запросов
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_kline_symbol_time_ms 
                ON kline_data(symbol, open_time_ms)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_kline_symbol_long_time_ms 
                ON kline_data(symbol, is_long, open_time_ms)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_kline_stream_symbol_time_ms 
                ON kline_stream(symbol, open_time_ms)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_alerts_symbol_type_time_ms 
                ON alerts(symbol, alert_type, alert_timestamp_ms)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_alerts_type_created_ms 
                ON alerts(alert_type, created_at_ms)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_alerts_close_timestamp_ms 
                ON alerts(close_timestamp_ms DESC NULLS LAST)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_paper_trades_symbol 
                ON paper_trades(symbol)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_paper_trades_status 
                ON paper_trades(status)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_real_trades_symbol 
                ON real_trades(symbol)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_real_trades_status 
                ON real_trades(status)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_real_trades_order_id 
                ON real_trades(order_id)
            """)

            cursor.close()
            logger.info("Таблицы с UNIX временем успешно созданы")

            # Проверяем, есть ли настройки торговли, если нет - создаем
            await self._initialize_trading_settings()

        except Exception as e:
            logger.error(f"Ошибка создания таблиц: {e}")
            raise

    async def _initialize_trading_settings(self):
        """Инициализация настроек торговли, если они отсутствуют"""
        try:
            cursor = self.connection.cursor()
            cursor.execute("SELECT COUNT(*) FROM trading_settings")
            count = cursor.fetchone()[0]
            
            if count == 0:
                cursor.execute("""
                    INSERT INTO trading_settings 
                    (account_balance, max_risk_per_trade, max_open_trades, 
                     default_stop_loss_percentage, default_take_profit_percentage, 
                     auto_calculate_quantity, enable_real_trading, default_leverage, 
                     default_margin_type, confirm_trades, updated_at_ms)
                    VALUES (10000, 2.0, 5, 2.0, 6.0, TRUE, FALSE, 1, 'isolated', TRUE, %s)
                """, (int(datetime.now(timezone.utc).timestamp() * 1000),))
                logger.info("Настройки торговли инициализированы")
            
            cursor.close()
        except Exception as e:
            logger.error(f"Ошибка инициализации настроек торговли: {e}")

    async def update_tables(self):
        """Обновление существующих таблиц для добавления UNIX столбцов"""
        try:
            cursor = self.connection.cursor()

            # Добавляем UNIX столбцы в существующие таблицы, если их нет
            tables_to_update = [
                ('watchlist', [
                    ('created_at_ms', 'BIGINT'),
                    ('updated_at_ms', 'BIGINT'),
                    ('created_at_readable', 'VARCHAR(30)'),
                    ('updated_at_readable', 'VARCHAR(30)'),
                    ('is_favorite', 'BOOLEAN DEFAULT FALSE'),
                    ('notes', 'TEXT'),
                    ('color', 'VARCHAR(20) DEFAULT \'#FFD700\''),
                    ('sort_order', 'INTEGER'),
                    ('favorite_added_at_ms', 'BIGINT')
                ]),
                ('kline_data', [
                    ('open_time_ms', 'BIGINT'),
                    ('close_time_ms', 'BIGINT'),
                    ('is_closed', 'BOOLEAN DEFAULT TRUE'),
                    ('open_time_readable', 'VARCHAR(30)'),
                    ('close_time_readable', 'VARCHAR(30)'),
                    ('created_at_ms', 'BIGINT'),
                    ('created_at_readable', 'VARCHAR(30)')
                ]),
                ('alerts', [
                    ('alert_timestamp_ms', 'BIGINT'),
                    ('close_timestamp_ms', 'BIGINT'),
                    ('alert_timestamp_readable', 'VARCHAR(30)'),
                    ('close_timestamp_readable', 'VARCHAR(30)'),
                    ('created_at_ms', 'BIGINT'),
                    ('updated_at_ms', 'BIGINT'),
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
                SET open_time_ms = EXTRACT(EPOCH FROM TO_TIMESTAMP(open_time/1000)) * 1000,
                    close_time_ms = EXTRACT(EPOCH FROM TO_TIMESTAMP(close_time/1000)) * 1000
                WHERE open_time_ms IS NULL AND open_time IS NOT NULL
            """)

            cursor.execute("""
                UPDATE alerts 
                SET alert_timestamp_ms = EXTRACT(EPOCH FROM alert_timestamp) * 1000,
                    close_timestamp_ms = EXTRACT(EPOCH FROM close_timestamp) * 1000
                WHERE alert_timestamp_ms IS NULL AND alert_timestamp IS NOT NULL
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
                SET open_time_readable = TO_CHAR(TO_TIMESTAMP(open_time_ms/1000), 'DD.MM.YYYY HH24:MI:SS:MS'),
                    close_time_readable = TO_CHAR(TO_TIMESTAMP(close_time_ms/1000), 'DD.MM.YYYY HH24:MI:SS:MS'),
                    created_at_readable = TO_CHAR(TO_TIMESTAMP(created_at_ms/1000), 'DD.MM.YYYY HH24:MI:SS:MS')
                WHERE open_time_ms IS NOT NULL AND open_time_readable IS NULL
            """)

            # Обновляем читаемые метки для alerts
            cursor.execute("""
                UPDATE alerts 
                SET alert_timestamp_readable = TO_CHAR(TO_TIMESTAMP(alert_timestamp_ms/1000), 'DD.MM.YYYY HH24:MI:SS:MS'),
                    close_timestamp_readable = TO_CHAR(TO_TIMESTAMP(close_timestamp_ms/1000), 'DD.MM.YYYY HH24:MI:SS:MS'),
                    created_at_readable = TO_CHAR(TO_TIMESTAMP(created_at_ms/1000), 'DD.MM.YYYY HH24:MI:SS:MS'),
                    updated_at_readable = TO_CHAR(TO_TIMESTAMP(updated_at_ms/1000), 'DD.MM.YYYY HH24:MI:SS:MS')
                WHERE alert_timestamp_ms IS NOT NULL AND alert_timestamp_readable IS NULL
            """)

            cursor.close()

        except Exception as e:
            logger.error(f"Ошибка обновления читаемых временных меток: {e}")

    def _ms_to_readable(self, ms_timestamp: int) -> str:
        """Преобразование миллисекунд в читаемый формат"""
        try:
            dt = datetime.fromtimestamp(ms_timestamp / 1000, tz=timezone.utc)
            return dt.strftime('%d.%m.%Y %H:%M:%S:%f')[:-3]  # Убираем последние 3 цифры микросекунд
        except:
            return ""

    async def check_data_integrity(self, symbol: str, hours: int) -> Dict:
        """Проверка целостности исторических данных с UNIX временем"""
        try:
            cursor = self.connection.cursor()

            # Определяем временные границы в UNIX формате
            current_time_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
            # Округляем до начала текущей минуты
            current_minute_ms = (current_time_ms // 60000) * 60000
            end_time_ms = current_minute_ms
            start_time_ms = end_time_ms - (hours * 60 * 60 * 1000)

            # Получаем существующие данные
            cursor.execute("""
                SELECT open_time_ms FROM kline_data 
                WHERE symbol = %s AND open_time_ms >= %s AND open_time_ms < %s
                ORDER BY open_time_ms
            """, (symbol, start_time_ms, end_time_ms))

            existing_times = [row[0] for row in cursor.fetchall()]
            cursor.close()

            # Генерируем ожидаемые временные метки (каждую минуту с нулями)
            expected_times = []
            current_time_ms = start_time_ms
            while current_time_ms < end_time_ms:
                expected_times.append(current_time_ms)
                current_time_ms += 60000  # +1 минута

            # Находим недостающие периоды
            missing_times = [t for t in expected_times if t not in existing_times]

            # Исключаем самые последние 2-3 минуты
            cutoff_time_ms = end_time_ms - (3 * 60 * 1000)
            missing_times = [t for t in missing_times if t < cutoff_time_ms]

            total_expected = len([t for t in expected_times if t < cutoff_time_ms])
            total_existing = len([t for t in existing_times if t < cutoff_time_ms])

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
                SELECT id, symbol, is_active, is_favorite, price_drop_percentage, 
                       current_price, historical_price, notes, color, sort_order,
                       favorite_added_at_ms, created_at_readable, updated_at_readable,
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
            current_time_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
            readable_time = self._ms_to_readable(current_time_ms)

            cursor.execute("""
                INSERT INTO watchlist (symbol, price_drop_percentage, current_price, historical_price,
                                     created_at_ms, updated_at_ms, created_at_readable, updated_at_readable) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s) 
                ON CONFLICT (symbol) DO UPDATE SET
                    is_active = TRUE,
                    price_drop_percentage = EXCLUDED.price_drop_percentage,
                    current_price = EXCLUDED.current_price,
                    historical_price = EXCLUDED.historical_price,
                    updated_at_ms = EXCLUDED.updated_at_ms,
                    updated_at_readable = EXCLUDED.updated_at_readable,
                    updated_at = CURRENT_TIMESTAMP
            """, (symbol, price_drop, current_price, historical_price,
                  current_time_ms, current_time_ms, readable_time, readable_time))

            cursor.close()

        except Exception as e:
            logger.error(f"Ошибка добавления в watchlist: {e}")

    async def update_watchlist_item(self, item_id: int, symbol: str, is_active: bool):
        """Обновить элемент watchlist"""
        try:
            cursor = self.connection.cursor()
            current_time_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
            readable_time = self._ms_to_readable(current_time_ms)

            cursor.execute("""
                UPDATE watchlist 
                SET symbol = %s, is_active = %s, 
                    updated_at_ms = %s, updated_at_readable = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (symbol, is_active, current_time_ms, readable_time, item_id))

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

    async def get_favorites(self) -> List[Dict]:
        """Получить список избранных торговых пар"""
        try:
            cursor = self.connection.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT id, symbol, is_active, is_favorite, price_drop_percentage, 
                       current_price, historical_price, notes, color, sort_order,
                       favorite_added_at_ms, created_at_readable, updated_at_readable
                FROM watchlist 
                WHERE is_favorite = TRUE
                ORDER BY sort_order, symbol
            """)

            result = cursor.fetchall()
            cursor.close()

            return [dict(row) for row in result]

        except Exception as e:
            logger.error(f"Ошибка получения избранного: {e}")
            return []

    async def add_to_favorites(self, symbol: str, notes: Optional[str] = None, color: Optional[str] = '#FFD700'):
        """Добавить торговую пару в избранное"""
        try:
            cursor = self.connection.cursor()
            current_time_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
            readable_time = self._ms_to_readable(current_time_ms)

            # Получаем максимальный sort_order
            cursor.execute("SELECT MAX(sort_order) FROM watchlist WHERE is_favorite = TRUE")
            max_sort = cursor.fetchone()[0]
            next_sort = (max_sort or 0) + 1

            # Проверяем, есть ли уже такой символ в watchlist
            cursor.execute("SELECT id FROM watchlist WHERE symbol = %s", (symbol,))
            exists = cursor.fetchone()

            if exists:
                # Обновляем существующую запись
                cursor.execute("""
                    UPDATE watchlist 
                    SET is_favorite = TRUE, notes = %s, color = %s, sort_order = %s,
                        favorite_added_at_ms = %s, updated_at_ms = %s, 
                        updated_at_readable = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE symbol = %s
                """, (notes, color, next_sort, current_time_ms, current_time_ms, readable_time, symbol))
            else:
                # Добавляем новую запись
                cursor.execute("""
                    INSERT INTO watchlist 
                    (symbol, is_active, is_favorite, notes, color, sort_order, 
                     favorite_added_at_ms, created_at_ms, updated_at_ms, 
                     created_at_readable, updated_at_readable)
                    VALUES (%s, TRUE, TRUE, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (symbol, notes, color, next_sort, current_time_ms, current_time_ms, 
                      current_time_ms, readable_time, readable_time))

            cursor.close()

        except Exception as e:
            logger.error(f"Ошибка добавления в избранное: {e}")
            raise

    async def remove_from_favorites(self, symbol: str):
        """Удалить торговую пару из избранного"""
        try:
            cursor = self.connection.cursor()
            current_time_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
            readable_time = self._ms_to_readable(current_time_ms)

            cursor.execute("""
                UPDATE watchlist 
                SET is_favorite = FALSE, sort_order = NULL, 
                    updated_at_ms = %s, updated_at_readable = %s, updated_at = CURRENT_TIMESTAMP
                WHERE symbol = %s
            """, (current_time_ms, readable_time, symbol))

            # Обновляем порядок сортировки для оставшихся избранных
            cursor.execute("""
                WITH ranked AS (
                    SELECT id, ROW_NUMBER() OVER (ORDER BY sort_order, symbol) AS new_sort
                    FROM watchlist
                    WHERE is_favorite = TRUE
                )
                UPDATE watchlist w
                SET sort_order = r.new_sort
                FROM ranked r
                WHERE w.id = r.id
            """)

            cursor.close()

        except Exception as e:
            logger.error(f"Ошибка удаления из избранного: {e}")
            raise

    async def update_favorite(self, symbol: str, notes: Optional[str] = None, 
                             color: Optional[str] = None, sort_order: Optional[int] = None):
        """Обновить информацию об избранной паре"""
        try:
            cursor = self.connection.cursor()
            current_time_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
            readable_time = self._ms_to_readable(current_time_ms)

            # Формируем SQL запрос динамически в зависимости от переданных параметров
            update_fields = []
            params = []

            if notes is not None:
                update_fields.append("notes = %s")
                params.append(notes)

            if color is not None:
                update_fields.append("color = %s")
                params.append(color)

            if sort_order is not None:
                update_fields.append("sort_order = %s")
                params.append(sort_order)

            # Добавляем обязательные поля для обновления
            update_fields.extend([
                "updated_at_ms = %s",
                "updated_at_readable = %s",
                "updated_at = CURRENT_TIMESTAMP"
            ])
            params.extend([current_time_ms, readable_time])

            # Добавляем условие WHERE
            params.append(symbol)

            # Формируем и выполняем запрос
            query = f"""
                UPDATE watchlist 
                SET {', '.join(update_fields)}
                WHERE symbol = %s
            """
            cursor.execute(query, params)

            cursor.close()

        except Exception as e:
            logger.error(f"Ошибка обновления избранной пары: {e}")
            raise

    async def reorder_favorites(self, symbol_order: List[str]):
        """Изменить порядок избранных пар"""
        try:
            cursor = self.connection.cursor()
            current_time_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
            
            # Обновляем порядок для каждого символа
            for i, symbol in enumerate(symbol_order):
                cursor.execute("""
                    UPDATE watchlist 
                    SET sort_order = %s, updated_at_ms = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE symbol = %s AND is_favorite = TRUE
                """, (i, current_time_ms, symbol))
            
            cursor.close()

        except Exception as e:
            logger.error(f"Ошибка изменения порядка избранных пар: {e}")
            raise

    async def save_kline_data(self, symbol: str, kline_data: Dict, is_closed: bool = False):
        """Сохранение данных свечи в базу данных с UNIX временем"""
        try:
            cursor = self.connection.cursor()

            # Получаем UNIX время из данных биржи
            open_time_ms = int(kline_data['start'])
            close_time_ms = int(kline_data['end'])

            # Определяем, является ли свеча LONG
            is_long = float(kline_data['close']) > float(kline_data['open'])

            # Рассчитываем объем в USDT
            volume_usdt = float(kline_data['volume']) * float(kline_data['close'])

            # Создаем читаемые временные метки
            open_time_readable = self._ms_to_readable(open_time_ms)
            close_time_readable = self._ms_to_readable(close_time_ms)
            current_time_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
            created_at_readable = self._ms_to_readable(current_time_ms)

            if is_closed:
                # Сохраняем в основную таблицу исторических данных
                cursor.execute("""
                    INSERT INTO kline_data 
                    (symbol, open_time_ms, close_time_ms, open_price, high_price, 
                     low_price, close_price, volume, volume_usdt, is_long, is_closed,
                     open_time_readable, close_time_readable, created_at_ms, created_at_readable,
                     open_time, close_time)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (symbol, open_time_ms) DO UPDATE SET
                        close_time_ms = EXCLUDED.close_time_ms,
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
                    symbol, open_time_ms, close_time_ms,
                    float(kline_data['open']), float(kline_data['high']),
                    float(kline_data['low']), float(kline_data['close']),
                    float(kline_data['volume']), volume_usdt, is_long, is_closed,
                    open_time_readable, close_time_readable, current_time_ms, created_at_readable,
                    open_time_ms, close_time_ms  # Для совместимости
                ))
            else:
                # Сохраняем в таблицу потоковых данных
                cursor.execute("""
                    INSERT INTO kline_stream 
                    (symbol, open_time_ms, close_time_ms, open_price, high_price, 
                     low_price, close_price, volume, volume_usdt, is_long, is_closed,
                     last_update_ms, open_time_readable, close_time_readable, last_update_readable)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (symbol, open_time_ms) DO UPDATE SET
                        close_time_ms = EXCLUDED.close_time_ms,
                        high_price = GREATEST(kline_stream.high_price, EXCLUDED.high_price),
                        low_price = LEAST(kline_stream.low_price, EXCLUDED.low_price),
                        close_price = EXCLUDED.close_price,
                        volume = EXCLUDED.volume,
                        volume_usdt = EXCLUDED.volume_usdt,
                        is_long = EXCLUDED.is_long,
                        last_update_ms = EXCLUDED.last_update_ms,
                        last_update_readable = EXCLUDED.last_update_readable
                """, (
                    symbol, open_time_ms, close_time_ms,
                    float(kline_data['open']), float(kline_data['high']),
                    float(kline_data['low']), float(kline_data['close']),
                    float(kline_data['volume']), volume_usdt, is_long, is_closed,
                    current_time_ms, open_time_readable, close_time_readable, created_at_readable
                ))

            cursor.close()

        except Exception as e:
            logger.error(f"Ошибка сохранения данных свечи: {e}")

    async def save_alert(self, alert_data: Dict) -> int:
        """Сохранение алерта в базу данных с UNIX временем"""
        try:
            cursor = self.connection.cursor()

            # Преобразуем timestamp в миллисекунды UTC
            alert_timestamp_ms = alert_data['timestamp']
            close_timestamp_ms = alert_data.get('close_timestamp')

            # Создаем читаемые временные метки
            alert_timestamp_readable = self._ms_to_readable(alert_timestamp_ms)
            close_timestamp_readable = self._ms_to_readable(close_timestamp_ms) if close_timestamp_ms else None
            current_time_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
            created_at_readable = self._ms_to_readable(current_time_ms)

            # Подготавливаем JSON данные
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
                 alert_timestamp_ms, close_timestamp_ms,
                 alert_timestamp_readable, close_timestamp_readable,
                 created_at_ms, updated_at_ms, created_at_readable, updated_at_readable,
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
                alert_timestamp_ms,
                close_timestamp_ms,
                alert_timestamp_readable,
                close_timestamp_readable,
                current_time_ms,
                current_time_ms,
                created_at_readable,
                created_at_readable,
                candle_data_json,
                preliminary_alert_json,
                imbalance_data_json,
                order_book_snapshot_json,
                datetime.fromtimestamp(alert_timestamp_ms / 1000, tz=timezone.utc),
                datetime.fromtimestamp(close_timestamp_ms / 1000, tz=timezone.utc) if close_timestamp_ms else None
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

            # Преобразуем timestamp в UNIX время
            close_timestamp_ms = alert_data.get('close_timestamp')

            close_timestamp_readable = self._ms_to_readable(close_timestamp_ms) if close_timestamp_ms else None
            current_time_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
            updated_at_readable = self._ms_to_readable(current_time_ms)

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
                    close_timestamp_ms = %s, close_timestamp_readable = %s,
                    updated_at_ms = %s, updated_at_readable = %s,
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
                close_timestamp_ms,
                close_timestamp_readable,
                current_time_ms,
                updated_at_readable,
                candle_data_json,
                imbalance_data_json,
                datetime.fromtimestamp(close_timestamp_ms / 1000, tz=timezone.utc) if close_timestamp_ms else None,
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
                       alert_timestamp_ms, close_timestamp_ms,
                       alert_timestamp_readable, close_timestamp_readable,
                       candle_data, preliminary_alert, imbalance_data, 
                       order_book_snapshot, created_at_ms, updated_at_ms,
                       alert_timestamp as timestamp, close_timestamp, created_at, updated_at
                FROM alerts 
                WHERE alert_type = %s
                ORDER BY COALESCE(close_timestamp_ms, alert_timestamp_ms) DESC
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
                       alert_timestamp_ms, close_timestamp_ms,
                       alert_timestamp_readable, close_timestamp_readable,
                       candle_data, preliminary_alert, imbalance_data,
                       order_book_snapshot, created_at_ms, updated_at_ms,
                       alert_timestamp as timestamp, close_timestamp, created_at, updated_at
                FROM alerts 
                ORDER BY COALESCE(close_timestamp_ms, alert_timestamp_ms) DESC
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
            current_time_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
            end_time_ms = current_time_ms - (offset_minutes * 60 * 1000)
            start_time_ms = end_time_ms - (hours * 60 * 60 * 1000)

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
                AND open_time_ms >= %s 
                AND open_time_ms < %s
                AND is_closed = TRUE
                ORDER BY open_time_ms
            """, (symbol, start_time_ms, end_time_ms))

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
                SELECT open_time_ms as timestamp, open_price as open, high_price as high,
                       low_price as low, close_price as close, volume, volume_usdt, is_long, is_closed
                FROM kline_data 
                WHERE symbol = %s AND is_closed = TRUE
                ORDER BY open_time_ms DESC
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
                    end_time_ms = int(alert_dt.timestamp() * 1000)
                except:
                    end_time_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
            else:
                end_time_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

            start_time_ms = end_time_ms - (hours * 60 * 60 * 1000)

            cursor.execute("""
                SELECT open_time_ms as timestamp, open_price as open, high_price as high,
                       low_price as low, close_price as close, volume, volume_usdt, is_long
                FROM kline_data 
                WHERE symbol = %s 
                AND open_time_ms >= %s 
                AND open_time_ms <= %s
                AND is_closed = TRUE
                ORDER BY open_time_ms
            """, (symbol, start_time_ms, end_time_ms))

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

            cutoff_time_ms = int((datetime.now(timezone.utc) - timedelta(minutes=minutes_back)).timestamp() * 1000)

            cursor.execute("""
                SELECT * FROM alerts 
                WHERE symbol = %s 
                AND alert_type = 'volume_spike'
                AND alert_timestamp_ms >= %s
                ORDER BY alert_timestamp_ms DESC
            """, (symbol, cutoff_time_ms))

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
            cutoff_time_ms = int((datetime.now(timezone.utc) - timedelta(hours=retention_hours)).timestamp() * 1000)

            cursor.execute("""
                DELETE FROM kline_data 
                WHERE open_time_ms < %s
            """, (cutoff_time_ms,))

            deleted_klines = cursor.rowcount

            # Очищаем потоковые данные
            cursor.execute("""
                DELETE FROM kline_stream 
                WHERE open_time_ms < %s
            """, (cutoff_time_ms,))

            deleted_stream = cursor.rowcount

            # Удаляем старые алерты (старше 24 часов)
            alert_cutoff_ms = int((datetime.now(timezone.utc) - timedelta(hours=24)).timestamp() * 1000)
            cursor.execute("""
                DELETE FROM alerts 
                WHERE created_at_ms < %s
            """, (alert_cutoff_ms,))

            deleted_alerts = cursor.rowcount

            cursor.close()

            logger.info(
                f"Очищено {deleted_klines} записей свечей, {deleted_stream} потоковых записей и {deleted_alerts} алертов")

        except Exception as e:
            logger.error(f"Ошибка очистки старых данных: {e}")

    async def cleanup_old_candles(self, symbol: str, retention_hours: int = 2):
        """Очистка старых свечей для конкретного символа"""
        try:
            cursor = self.connection.cursor()

            # Удаляем старые данные свечей
            cutoff_time_ms = int((datetime.now(timezone.utc) - timedelta(hours=retention_hours)).timestamp() * 1000)

            cursor.execute("""
                DELETE FROM kline_data 
                WHERE symbol = %s AND open_time_ms < %s
            """, (symbol, cutoff_time_ms))

            deleted_klines = cursor.rowcount

            # Очищаем потоковые данные
            cursor.execute("""
                DELETE FROM kline_stream 
                WHERE symbol = %s AND open_time_ms < %s
            """, (symbol, cutoff_time_ms))

            deleted_stream = cursor.rowcount

            cursor.close()

            logger.debug(
                f"Очищено {deleted_klines} записей свечей и {deleted_stream} потоковых записей для {symbol}")

        except Exception as e:
            logger.error(f"Ошибка очистки старых данных для {symbol}: {e}")

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

    # Методы для бумажной торговли
    async def get_trading_settings(self) -> Dict:
        """Получить настройки торговли"""
        try:
            cursor = self.connection.cursor(cursor_factory=RealDictCursor)
            cursor.execute("SELECT * FROM trading_settings LIMIT 1")
            result = cursor.fetchone()
            cursor.close()
            
            if result:
                return dict(result)
            else:
                # Если настроек нет, возвращаем значения по умолчанию
                return {
                    'account_balance': 10000,
                    'max_risk_per_trade': 2.0,
                    'max_open_trades': 5,
                    'default_stop_loss_percentage': 2.0,
                    'default_take_profit_percentage': 6.0,
                    'auto_calculate_quantity': True,
                    'enable_real_trading': False,
                    'default_leverage': 1,
                    'default_margin_type': 'isolated',
                    'confirm_trades': True
                }
                
        except Exception as e:
            logger.error(f"Ошибка получения настроек торговли: {e}")
            return {}

    async def update_trading_settings(self, settings: Dict) -> bool:
        """Обновить настройки торговли"""
        try:
            cursor = self.connection.cursor()
            current_time_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
            
            # Получаем текущие настройки
            cursor.execute("SELECT COUNT(*) FROM trading_settings")
            count = cursor.fetchone()[0]
            
            if count == 0:
                # Вставляем новую запись
                fields = []
                values = []
                placeholders = []
                
                for key, value in settings.items():
                    fields.append(key)
                    values.append(value)
                    placeholders.append("%s")
                
                fields.append("updated_at_ms")
                values.append(current_time_ms)
                placeholders.append("%s")
                
                query = f"""
                    INSERT INTO trading_settings 
                    ({', '.join(fields)})
                    VALUES ({', '.join(placeholders)})
                """
                cursor.execute(query, values)
            else:
                # Обновляем существующую запись
                set_clauses = []
                values = []
                
                for key, value in settings.items():
                    set_clauses.append(f"{key} = %s")
                    values.append(value)
                
                set_clauses.append("updated_at_ms = %s")
                values.append(current_time_ms)
                
                query = f"""
                    UPDATE trading_settings 
                    SET {', '.join(set_clauses)}
                """
                cursor.execute(query, values)
            
            cursor.close()
            return True
            
        except Exception as e:
            logger.error(f"Ошибка обновления настроек торговли: {e}")
            return False

    async def create_paper_trade(self, trade_data: Dict) -> Optional[int]:
        """Создать бумажную сделку"""
        try:
            cursor = self.connection.cursor()
            current_time_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
            
            # Формируем SQL запрос динамически
            fields = ["symbol", "trade_type", "entry_price", "quantity", "opened_at_ms"]
            values = [
                trade_data["symbol"], 
                trade_data["trade_type"], 
                trade_data["entry_price"], 
                trade_data["quantity"],
                current_time_ms
            ]
            placeholders = ["%s", "%s", "%s", "%s", "%s"]
            
            # Добавляем опциональные поля
            optional_fields = [
                "stop_loss", "take_profit", "risk_amount", "risk_percentage", 
                "potential_profit", "potential_loss", "risk_reward_ratio", 
                "notes", "alert_id"
            ]
            
            for field in optional_fields:
                if field in trade_data and trade_data[field] is not None:
                    fields.append(field)
                    values.append(trade_data[field])
                    placeholders.append("%s")
            
            query = f"""
                INSERT INTO paper_trades 
                ({', '.join(fields)})
                VALUES ({', '.join(placeholders)})
                RETURNING id
            """
            
            cursor.execute(query, values)
            trade_id = cursor.fetchone()[0]
            cursor.close()
            
            return trade_id
            
        except Exception as e:
            logger.error(f"Ошибка создания бумажной сделки: {e}")
            return None

    async def get_paper_trades(self, status: Optional[str] = None, limit: int = 100) -> List[Dict]:
        """Получить список бумажных сделок"""
        try:
            cursor = self.connection.cursor(cursor_factory=RealDictCursor)
            
            if status:
                cursor.execute("""
                    SELECT * FROM paper_trades 
                    WHERE status = %s
                    ORDER BY opened_at_ms DESC
                    LIMIT %s
                """, (status, limit))
            else:
                cursor.execute("""
                    SELECT * FROM paper_trades 
                    ORDER BY opened_at_ms DESC
                    LIMIT %s
                """, (limit,))
            
            result = cursor.fetchall()
            cursor.close()
            
            return [dict(row) for row in result]
            
        except Exception as e:
            logger.error(f"Ошибка получения бумажных сделок: {e}")
            return []

    async def close_paper_trade(self, trade_id: int, exit_price: float, exit_reason: str = "MANUAL") -> bool:
        """Закрыть бумажную сделку"""
        try:
            cursor = self.connection.cursor()
            current_time_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
            
            # Получаем данные сделки
            cursor.execute("""
                SELECT trade_type, entry_price, quantity, risk_amount
                FROM paper_trades
                WHERE id = %s AND status = 'OPEN'
            """, (trade_id,))
            
            trade = cursor.fetchone()
            if not trade:
                return False
            
            trade_type, entry_price, quantity, risk_amount = trade
            
            # Рассчитываем P&L
            if trade_type == 'LONG':
                pnl = (exit_price - entry_price) * quantity
            else:  # SHORT
                pnl = (entry_price - exit_price) * quantity
            
            # Рассчитываем P&L в процентах
            position_size = entry_price * quantity
            pnl_percentage = (pnl / position_size) * 100 if position_size > 0 else 0
            
            # Обновляем сделку
            cursor.execute("""
                UPDATE paper_trades
                SET status = 'CLOSED',
                    exit_price = %s,
                    exit_reason = %s,
                    pnl = %s,
                    pnl_percentage = %s,
                    closed_at_ms = %s,
                    updated_at_ms = %s
                WHERE id = %s AND status = 'OPEN'
            """, (
                exit_price,
                exit_reason,
                pnl,
                pnl_percentage,
                current_time_ms,
                current_time_ms,
                trade_id
            ))
            
            updated = cursor.rowcount > 0
            cursor.close()
            
            return updated
            
        except Exception as e:
            logger.error(f"Ошибка закрытия бумажной сделки: {e}")
            return False

    async def get_trading_statistics(self) -> Dict:
        """Получить статистику торговли"""
        try:
            cursor = self.connection.cursor()
            
            # Общее количество сделок
            cursor.execute("SELECT COUNT(*) FROM paper_trades")
            total_trades = cursor.fetchone()[0]
            
            # Количество открытых сделок
            cursor.execute("SELECT COUNT(*) FROM paper_trades WHERE status = 'OPEN'")
            open_trades = cursor.fetchone()[0]
            
            # Количество закрытых сделок
            cursor.execute("SELECT COUNT(*) FROM paper_trades WHERE status = 'CLOSED'")
            closed_trades = cursor.fetchone()[0]
            
            # Выигрышные и проигрышные сделки
            cursor.execute("SELECT COUNT(*) FROM paper_trades WHERE status = 'CLOSED' AND pnl > 0")
            winning_trades = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM paper_trades WHERE status = 'CLOSED' AND pnl <= 0")
            losing_trades = cursor.fetchone()[0]
            
            # Винрейт
            win_rate = (winning_trades / closed_trades * 100) if closed_trades > 0 else 0
            
            # Общий P&L
            cursor.execute("SELECT COALESCE(SUM(pnl), 0) FROM paper_trades WHERE status = 'CLOSED'")
            total_pnl = cursor.fetchone()[0]
            
            # Средний P&L в процентах
            cursor.execute("SELECT COALESCE(AVG(pnl_percentage), 0) FROM paper_trades WHERE status = 'CLOSED'")
            avg_pnl_percentage = cursor.fetchone()[0]
            
            # Максимальная прибыль и убыток
            cursor.execute("SELECT COALESCE(MAX(pnl), 0) FROM paper_trades WHERE status = 'CLOSED'")
            max_profit = cursor.fetchone()[0]
            
            cursor.execute("SELECT COALESCE(MIN(pnl), 0) FROM paper_trades WHERE status = 'CLOSED'")
            max_loss = cursor.fetchone()[0]
            
            cursor.close()
            
            return {
                'total_trades': total_trades,
                'open_trades': open_trades,
                'closed_trades': closed_trades,
                'winning_trades': winning_trades,
                'losing_trades': losing_trades,
                'win_rate': win_rate,
                'total_pnl': float(total_pnl),
                'avg_pnl_percentage': float(avg_pnl_percentage),
                'max_profit': float(max_profit),
                'max_loss': float(max_loss)
            }
            
        except Exception as e:
            logger.error(f"Ошибка получения статистики торговли: {e}")
            return {
                'total_trades': 0,
                'open_trades': 0,
                'closed_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0,
                'total_pnl': 0,
                'avg_pnl_percentage': 0,
                'max_profit': 0,
                'max_loss': 0
            }

    # Методы для реальной торговли
    async def create_real_trade(self, trade_data: Dict) -> Optional[int]:
        """Создать реальную сделку"""
        try:
            cursor = self.connection.cursor()
            current_time_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
            
            # Формируем SQL запрос динамически
            fields = ["symbol", "trade_type", "entry_price", "quantity", "opened_at_ms", "leverage", "margin_type"]
            values = [
                trade_data["symbol"], 
                trade_data["trade_type"], 
                trade_data["entry_price"], 
                trade_data["quantity"],
                current_time_ms,
                trade_data.get("leverage", 1),
                trade_data.get("margin_type", "isolated")
            ]
            placeholders = ["%s", "%s", "%s", "%s", "%s", "%s", "%s"]
            
            # Добавляем опциональные поля
            optional_fields = [
                "stop_loss", "take_profit", "risk_amount", "risk_percentage", 
                "potential_profit", "potential_loss", "risk_reward_ratio", 
                "notes", "alert_id", "order_id"
            ]
            
            for field in optional_fields:
                if field in trade_data and trade_data[field] is not None:
                    fields.append(field)
                    values.append(trade_data[field])
                    placeholders.append("%s")
            
            query = f"""
                INSERT INTO real_trades 
                ({', '.join(fields)})
                VALUES ({', '.join(placeholders)})
                RETURNING id
            """
            
            cursor.execute(query, values)
            trade_id = cursor.fetchone()[0]
            cursor.close()
            
            return trade_id
            
        except Exception as e:
            logger.error(f"Ошибка создания реальной сделки: {e}")
            return None

    async def get_real_trades(self, status: Optional[str] = None, limit: int = 100) -> List[Dict]:
        """Получить список реальных сделок"""
        try:
            cursor = self.connection.cursor(cursor_factory=RealDictCursor)
            
            if status:
                cursor.execute("""
                    SELECT * FROM real_trades 
                    WHERE status = %s
                    ORDER BY opened_at_ms DESC
                    LIMIT %s
                """, (status, limit))
            else:
                cursor.execute("""
                    SELECT * FROM real_trades 
                    ORDER BY opened_at_ms DESC
                    LIMIT %s
                """, (limit,))
            
            result = cursor.fetchall()
            cursor.close()
            
            return [dict(row) for row in result]
            
        except Exception as e:
            logger.error(f"Ошибка получения реальных сделок: {e}")
            return []

    async def update_real_trade(self, trade_id: int, update_data: Dict) -> bool:
        """Обновить реальную сделку"""
        try:
            cursor = self.connection.cursor()
            current_time_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
            
            # Формируем SQL запрос динамически
            set_clauses = []
            values = []
            
            for key, value in update_data.items():
                set_clauses.append(f"{key} = %s")
                values.append(value)
            
            set_clauses.append("updated_at_ms = %s")
            values.append(current_time_ms)
            
            values.append(trade_id)  # Для WHERE условия
            
            query = f"""
                UPDATE real_trades 
                SET {', '.join(set_clauses)}
                WHERE id = %s
            """
            
            cursor.execute(query, values)
            updated = cursor.rowcount > 0
            cursor.close()
            
            return updated
            
        except Exception as e:
            logger.error(f"Ошибка обновления реальной сделки: {e}")
            return False

    async def close_real_trade(self, trade_id: int, exit_price: float, exit_reason: str = "MANUAL") -> bool:
        """Закрыть реальную сделку"""
        try:
            cursor = self.connection.cursor()
            current_time_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
            
            # Получаем данные сделки
            cursor.execute("""
                SELECT trade_type, entry_price, quantity, risk_amount
                FROM real_trades
                WHERE id = %s AND status = 'OPEN'
            """, (trade_id,))
            
            trade = cursor.fetchone()
            if not trade:
                return False
            
            trade_type, entry_price, quantity, risk_amount = trade
            
            # Рассчитываем P&L
            if trade_type == 'LONG':
                pnl = (exit_price - entry_price) * quantity
            else:  # SHORT
                pnl = (entry_price - exit_price) * quantity
            
            # Рассчитываем P&L в процентах
            position_size = entry_price * quantity
            pnl_percentage = (pnl / position_size) * 100 if position_size > 0 else 0
            
            # Обновляем сделку
            cursor.execute("""
                UPDATE real_trades
                SET status = 'CLOSED',
                    exit_price = %s,
                    exit_reason = %s,
                    pnl = %s,
                    pnl_percentage = %s,
                    closed_at_ms = %s,
                    updated_at_ms = %s
                WHERE id = %s AND status = 'OPEN'
            """, (
                exit_price,
                exit_reason,
                pnl,
                pnl_percentage,
                current_time_ms,
                current_time_ms,
                trade_id
            ))
            
            updated = cursor.rowcount > 0
            cursor.close()
            
            return updated
            
        except Exception as e:
            logger.error(f"Ошибка закрытия реальной сделки: {e}")
            return False

    async def get_real_trading_statistics(self) -> Dict:
        """Получить статистику реальной торговли"""
        try:
            cursor = self.connection.cursor()
            
            # Общее количество сделок
            cursor.execute("SELECT COUNT(*) FROM real_trades")
            total_trades = cursor.fetchone()[0]
            
            # Количество открытых сделок
            cursor.execute("SELECT COUNT(*) FROM real_trades WHERE status = 'OPEN'")
            open_trades = cursor.fetchone()[0]
            
            # Количество закрытых сделок
            cursor.execute("SELECT COUNT(*) FROM real_trades WHERE status = 'CLOSED'")
            closed_trades = cursor.fetchone()[0]
            
            # Выигрышные и проигрышные сделки
            cursor.execute("SELECT COUNT(*) FROM real_trades WHERE status = 'CLOSED' AND pnl > 0")
            winning_trades = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM real_trades WHERE status = 'CLOSED' AND pnl <= 0")
            losing_trades = cursor.fetchone()[0]
            
            # Винрейт
            win_rate = (winning_trades / closed_trades * 100) if closed_trades > 0 else 0
            
            # Общий P&L
            cursor.execute("SELECT COALESCE(SUM(pnl), 0) FROM real_trades WHERE status = 'CLOSED'")
            total_pnl = cursor.fetchone()[0]
            
            # Средний P&L в процентах
            cursor.execute("SELECT COALESCE(AVG(pnl_percentage), 0) FROM real_trades WHERE status = 'CLOSED'")
            avg_pnl_percentage = cursor.fetchone()[0]
            
            # Максимальная прибыль и убыток
            cursor.execute("SELECT COALESCE(MAX(pnl), 0) FROM real_trades WHERE status = 'CLOSED'")
            max_profit = cursor.fetchone()[0]
            
            cursor.execute("SELECT COALESCE(MIN(pnl), 0) FROM real_trades WHERE status = 'CLOSED'")
            max_loss = cursor.fetchone()[0]
            
            cursor.close()
            
            return {
                'total_trades': total_trades,
                'open_trades': open_trades,
                'closed_trades': closed_trades,
                'winning_trades': winning_trades,
                'losing_trades': losing_trades,
                'win_rate': win_rate,
                'total_pnl': float(total_pnl),
                'avg_pnl_percentage': float(avg_pnl_percentage),
                'max_profit': float(max_profit),
                'max_loss': float(max_loss)
            }
            
        except Exception as e:
            logger.error(f"Ошибка получения статистики реальной торговли: {e}")
            return {
                'total_trades': 0,
                'open_trades': 0,
                'closed_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0,
                'total_pnl': 0,
                'avg_pnl_percentage': 0,
                'max_profit': 0,
                'max_loss': 0
            }

    def close(self):
        """Закрытие соединения с базой данных"""
        if self.connection:
            self.connection.close()