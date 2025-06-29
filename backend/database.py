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
        """Создание необходимых таблиц с UTC временем"""
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
                    color VARCHAR(7) DEFAULT '#FFD700',
                    sort_order INTEGER DEFAULT 0,
                    created_at_ms BIGINT DEFAULT EXTRACT(EPOCH FROM NOW()) * 1000,
                    updated_at_ms BIGINT DEFAULT EXTRACT(EPOCH FROM NOW()) * 1000,
                    favorite_added_at_ms BIGINT,
                    created_at_readable VARCHAR(30),
                    updated_at_readable VARCHAR(30),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Создаем таблицу избранного
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS favorites (
                    id SERIAL PRIMARY KEY,
                    symbol VARCHAR(20) NOT NULL UNIQUE,
                    notes TEXT,
                    color VARCHAR(7) DEFAULT '#FFD700',
                    sort_order INTEGER DEFAULT 0,
                    created_at_ms BIGINT DEFAULT EXTRACT(EPOCH FROM NOW()) * 1000,
                    updated_at_ms BIGINT DEFAULT EXTRACT(EPOCH FROM NOW()) * 1000,
                    created_at_readable VARCHAR(30),
                    updated_at_readable VARCHAR(30),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Создаем основную таблицу для исторических данных свечей (UTC время)
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

            # Создаем обновленную таблицу алертов с UTC временем
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

            # Создаем таблицу для бумажной торговли
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS paper_trades (
                    id SERIAL PRIMARY KEY,
                    symbol VARCHAR(20) NOT NULL,
                    trade_type VARCHAR(10) NOT NULL CHECK (trade_type IN ('LONG', 'SHORT')),
                    entry_price DECIMAL(20, 8) NOT NULL,
                    quantity DECIMAL(20, 8) NOT NULL,
                    stop_loss DECIMAL(20, 8),
                    take_profit DECIMAL(20, 8),
                    risk_amount DECIMAL(20, 8) NOT NULL,
                    risk_percentage DECIMAL(5, 2) NOT NULL,
                    potential_profit DECIMAL(20, 8),
                    potential_loss DECIMAL(20, 8),
                    risk_reward_ratio DECIMAL(10, 2),
                    status VARCHAR(20) DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'CLOSED', 'CANCELLED')),
                    exit_price DECIMAL(20, 8),
                    exit_reason VARCHAR(50),
                    pnl DECIMAL(20, 8),
                    pnl_percentage DECIMAL(10, 2),
                    notes TEXT,
                    alert_id INTEGER REFERENCES alerts(id),
                    opened_at_ms BIGINT DEFAULT EXTRACT(EPOCH FROM NOW()) * 1000,
                    closed_at_ms BIGINT,
                    opened_at_readable VARCHAR(30),
                    closed_at_readable VARCHAR(30),
                    opened_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    closed_at TIMESTAMP
                )
            """)

            # Создаем таблицу настроек торговли
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trading_settings (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(50) DEFAULT 'default',
                    account_balance DECIMAL(20, 8) DEFAULT 10000.00,
                    max_risk_per_trade DECIMAL(5, 2) DEFAULT 2.00,
                    max_open_trades INTEGER DEFAULT 5,
                    default_stop_loss_percentage DECIMAL(5, 2) DEFAULT 2.00,
                    default_take_profit_percentage DECIMAL(5, 2) DEFAULT 6.00,
                    auto_calculate_quantity BOOLEAN DEFAULT TRUE,
                    created_at_ms BIGINT DEFAULT EXTRACT(EPOCH FROM NOW()) * 1000,
                    updated_at_ms BIGINT DEFAULT EXTRACT(EPOCH FROM NOW()) * 1000,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id)
                )
            """)

            # Вставляем настройки по умолчанию
            cursor.execute("""
                INSERT INTO trading_settings (user_id) 
                VALUES ('default') 
                ON CONFLICT (user_id) DO NOTHING
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
                CREATE INDEX IF NOT EXISTS idx_paper_trades_symbol_status 
                ON paper_trades(symbol, status)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_paper_trades_opened_at_ms 
                ON paper_trades(opened_at_ms DESC)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_favorites_sort_order 
                ON favorites(sort_order)
            """)

            cursor.close()
            logger.info("Таблицы с UTC временем успешно созданы")

        except Exception as e:
            logger.error(f"Ошибка создания таблиц: {e}")
            raise

    async def update_tables(self):
        """Обновление существующих таблиц для добавления новых столбцов"""
        try:
            cursor = self.connection.cursor()

            # Добавляем новые столбцы в существующие таблицы, если их нет
            tables_to_update = [
                ('watchlist', [
                    ('is_favorite', 'BOOLEAN DEFAULT FALSE'),
                    ('notes', 'TEXT'),
                    ('color', 'VARCHAR(7) DEFAULT \'#FFD700\''),
                    ('sort_order', 'INTEGER DEFAULT 0'),
                    ('favorite_added_at_ms', 'BIGINT'),
                    ('created_at_ms', 'BIGINT'),
                    ('updated_at_ms', 'BIGINT'),
                    ('created_at_readable', 'VARCHAR(30)'),
                    ('updated_at_readable', 'VARCHAR(30)')
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

            # Заполняем UTC столбцы из существующих timestamp столбцов
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
            logger.info("Таблицы успешно обновлены для UTC времени")

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

    def _utc_to_readable(self, utc_timestamp_ms: int) -> str:
        """Преобразование UTC времени в читаемый формат"""
        try:
            dt = datetime.fromtimestamp(utc_timestamp_ms / 1000, tz=timezone.utc)
            return dt.strftime('%d.%m.%Y %H:%M:%S:%f')[:-3]  # Убираем последние 3 цифры микросекунд
        except:
            return ""

    async def check_data_integrity(self, symbol: str, hours: int) -> Dict:
        """Проверка целостности исторических данных с UTC временем"""
        try:
            cursor = self.connection.cursor()

            # Определяем временные границы в UTC формате
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

    # Методы для работы с избранным
    async def get_favorites(self) -> List[Dict]:
        """Получить список избранных торговых пар"""
        try:
            cursor = self.connection.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT f.*, w.is_active, w.price_drop_percentage, w.current_price, w.historical_price
                FROM favorites f
                LEFT JOIN watchlist w ON f.symbol = w.symbol
                ORDER BY f.sort_order, f.created_at_ms DESC
            """)

            result = cursor.fetchall()
            cursor.close()

            return [dict(row) for row in result]

        except Exception as e:
            logger.error(f"Ошибка получения избранного: {e}")
            return []

    async def add_to_favorites(self, symbol: str, notes: str = None, color: str = '#FFD700'):
        """Добавить торговую пару в избранное"""
        try:
            cursor = self.connection.cursor()
            current_time_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
            readable_time = self._utc_to_readable(current_time_ms)

            # Получаем максимальный sort_order
            cursor.execute("SELECT COALESCE(MAX(sort_order), -1) + 1 FROM favorites")
            sort_order = cursor.fetchone()[0]

            cursor.execute("""
                INSERT INTO favorites (symbol, notes, color, sort_order, created_at_ms, updated_at_ms, 
                                     created_at_readable, updated_at_readable) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s) 
                ON CONFLICT (symbol) DO UPDATE SET
                    notes = EXCLUDED.notes,
                    color = EXCLUDED.color,
                    updated_at_ms = EXCLUDED.updated_at_ms,
                    updated_at_readable = EXCLUDED.updated_at_readable,
                    updated_at = CURRENT_TIMESTAMP
            """, (symbol, notes, color, sort_order, current_time_ms, current_time_ms, 
                  readable_time, readable_time))

            # Обновляем watchlist
            cursor.execute("""
                UPDATE watchlist 
                SET is_favorite = TRUE, 
                    favorite_added_at_ms = %s,
                    updated_at_ms = %s,
                    updated_at_readable = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE symbol = %s
            """, (current_time_ms, current_time_ms, readable_time, symbol))

            cursor.close()

        except Exception as e:
            logger.error(f"Ошибка добавления в избранное: {e}")

    async def remove_from_favorites(self, symbol: str):
        """Удалить торговую пару из избранного"""
        try:
            cursor = self.connection.cursor()
            current_time_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
            readable_time = self._utc_to_readable(current_time_ms)

            cursor.execute("DELETE FROM favorites WHERE symbol = %s", (symbol,))

            # Обновляем watchlist
            cursor.execute("""
                UPDATE watchlist 
                SET is_favorite = FALSE, 
                    favorite_added_at_ms = NULL,
                    updated_at_ms = %s,
                    updated_at_readable = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE symbol = %s
            """, (current_time_ms, readable_time, symbol))

            cursor.close()

        except Exception as e:
            logger.error(f"Ошибка удаления из избранного: {e}")

    async def update_favorite(self, symbol: str, notes: str = None, color: str = None, sort_order: int = None):
        """Обновить информацию об избранной паре"""
        try:
            cursor = self.connection.cursor()
            current_time_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
            readable_time = self._utc_to_readable(current_time_ms)

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

            if update_fields:
                update_fields.extend([
                    "updated_at_ms = %s",
                    "updated_at_readable = %s",
                    "updated_at = CURRENT_TIMESTAMP"
                ])
                params.extend([current_time_ms, readable_time, symbol])

                query = f"UPDATE favorites SET {', '.join(update_fields)} WHERE symbol = %s"
                cursor.execute(query, params)

            cursor.close()

        except Exception as e:
            logger.error(f"Ошибка обновления избранной пары: {e}")

    async def reorder_favorites(self, symbol_order: List[str]):
        """Изменить порядок избранных пар"""
        try:
            cursor = self.connection.cursor()
            current_time_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
            readable_time = self._utc_to_readable(current_time_ms)

            for index, symbol in enumerate(symbol_order):
                cursor.execute("""
                    UPDATE favorites 
                    SET sort_order = %s, 
                        updated_at_ms = %s,
                        updated_at_readable = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE symbol = %s
                """, (index, current_time_ms, readable_time, symbol))

            cursor.close()

        except Exception as e:
            logger.error(f"Ошибка изменения порядка избранных пар: {e}")

    # Методы для бумажной торговли
    async def get_trading_settings(self, user_id: str = 'default') -> Dict:
        """Получить настройки торговли"""
        try:
            cursor = self.connection.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT * FROM trading_settings WHERE user_id = %s
            """, (user_id,))

            result = cursor.fetchone()
            cursor.close()

            return dict(result) if result else {}

        except Exception as e:
            logger.error(f"Ошибка получения настроек торговли: {e}")
            return {}

    async def update_trading_settings(self, settings: Dict, user_id: str = 'default'):
        """Обновить настройки торговли"""
        try:
            cursor = self.connection.cursor()
            current_time_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

            cursor.execute("""
                UPDATE trading_settings 
                SET account_balance = %s,
                    max_risk_per_trade = %s,
                    max_open_trades = %s,
                    default_stop_loss_percentage = %s,
                    default_take_profit_percentage = %s,
                    auto_calculate_quantity = %s,
                    updated_at_ms = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id = %s
            """, (
                settings.get('account_balance'),
                settings.get('max_risk_per_trade'),
                settings.get('max_open_trades'),
                settings.get('default_stop_loss_percentage'),
                settings.get('default_take_profit_percentage'),
                settings.get('auto_calculate_quantity'),
                current_time_ms,
                user_id
            ))

            cursor.close()

        except Exception as e:
            logger.error(f"Ошибка обновления настроек торговли: {e}")

    async def create_paper_trade(self, trade_data: Dict) -> int:
        """Создать бумажную сделку"""
        try:
            cursor = self.connection.cursor()
            current_time_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
            readable_time = self._utc_to_readable(current_time_ms)

            cursor.execute("""
                INSERT INTO paper_trades 
                (symbol, trade_type, entry_price, quantity, stop_loss, take_profit,
                 risk_amount, risk_percentage, potential_profit, potential_loss,
                 risk_reward_ratio, notes, alert_id, opened_at_ms, opened_at_readable)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                trade_data['symbol'],
                trade_data['trade_type'],
                trade_data['entry_price'],
                trade_data['quantity'],
                trade_data.get('stop_loss'),
                trade_data.get('take_profit'),
                trade_data['risk_amount'],
                trade_data['risk_percentage'],
                trade_data.get('potential_profit'),
                trade_data.get('potential_loss'),
                trade_data.get('risk_reward_ratio'),
                trade_data.get('notes'),
                trade_data.get('alert_id'),
                current_time_ms,
                readable_time
            ))

            trade_id = cursor.fetchone()[0]
            cursor.close()

            return trade_id

        except Exception as e:
            logger.error(f"Ошибка создания бумажной сделки: {e}")
            return None

    async def get_paper_trades(self, status: str = None, limit: int = 100) -> List[Dict]:
        """Получить список бумажных сделок"""
        try:
            cursor = self.connection.cursor(cursor_factory=RealDictCursor)
            
            query = """
                SELECT pt.*, a.alert_type, a.message as alert_message
                FROM paper_trades pt
                LEFT JOIN alerts a ON pt.alert_id = a.id
            """
            params = []

            if status:
                query += " WHERE pt.status = %s"
                params.append(status)

            query += " ORDER BY pt.opened_at_ms DESC LIMIT %s"
            params.append(limit)

            cursor.execute(query, params)
            result = cursor.fetchall()
            cursor.close()

            return [dict(row) for row in result]

        except Exception as e:
            logger.error(f"Ошибка получения бумажных сделок: {e}")
            return []

    async def close_paper_trade(self, trade_id: int, exit_price: float, exit_reason: str = 'MANUAL'):
        """Закрыть бумажную сделку"""
        try:
            cursor = self.connection.cursor()
            current_time_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
            readable_time = self._utc_to_readable(current_time_ms)

            # Получаем данные сделки
            cursor.execute("""
                SELECT * FROM paper_trades WHERE id = %s AND status = 'OPEN'
            """, (trade_id,))
            
            trade = cursor.fetchone()
            if not trade:
                return False

            # Рассчитываем PnL
            entry_price = float(trade[3])  # entry_price
            quantity = float(trade[4])     # quantity
            trade_type = trade[2]          # trade_type

            if trade_type == 'LONG':
                pnl = (exit_price - entry_price) * quantity
            else:  # SHORT
                pnl = (entry_price - exit_price) * quantity

            pnl_percentage = (pnl / (entry_price * quantity)) * 100

            # Обновляем сделку
            cursor.execute("""
                UPDATE paper_trades 
                SET status = 'CLOSED',
                    exit_price = %s,
                    exit_reason = %s,
                    pnl = %s,
                    pnl_percentage = %s,
                    closed_at_ms = %s,
                    closed_at_readable = %s,
                    closed_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (exit_price, exit_reason, pnl, pnl_percentage, 
                  current_time_ms, readable_time, trade_id))

            cursor.close()
            return True

        except Exception as e:
            logger.error(f"Ошибка закрытия бумажной сделки: {e}")
            return False

    async def get_trading_statistics(self) -> Dict:
        """Получить статистику торговли"""
        try:
            cursor = self.connection.cursor()

            # Общая статистика
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_trades,
                    COUNT(CASE WHEN status = 'OPEN' THEN 1 END) as open_trades,
                    COUNT(CASE WHEN status = 'CLOSED' THEN 1 END) as closed_trades,
                    COUNT(CASE WHEN status = 'CLOSED' AND pnl > 0 THEN 1 END) as winning_trades,
                    COUNT(CASE WHEN status = 'CLOSED' AND pnl < 0 THEN 1 END) as losing_trades,
                    COALESCE(SUM(CASE WHEN status = 'CLOSED' THEN pnl END), 0) as total_pnl,
                    COALESCE(AVG(CASE WHEN status = 'CLOSED' THEN pnl_percentage END), 0) as avg_pnl_percentage,
                    COALESCE(MAX(CASE WHEN status = 'CLOSED' THEN pnl END), 0) as max_profit,
                    COALESCE(MIN(CASE WHEN status = 'CLOSED' THEN pnl END), 0) as max_loss
                FROM paper_trades
            """)

            stats = cursor.fetchone()
            cursor.close()

            if stats:
                total_trades, open_trades, closed_trades, winning_trades, losing_trades, \
                total_pnl, avg_pnl_percentage, max_profit, max_loss = stats

                win_rate = (winning_trades / closed_trades * 100) if closed_trades > 0 else 0

                return {
                    'total_trades': total_trades,
                    'open_trades': open_trades,
                    'closed_trades': closed_trades,
                    'winning_trades': winning_trades,
                    'losing_trades': losing_trades,
                    'win_rate': round(win_rate, 2),
                    'total_pnl': float(total_pnl),
                    'avg_pnl_percentage': float(avg_pnl_percentage),
                    'max_profit': float(max_profit),
                    'max_loss': float(max_loss)
                }

            return {}

        except Exception as e:
            logger.error(f"Ошибка получения статистики торговли: {e}")
            return {}

    # Остальные методы остаются без изменений, но с заменой datetime.utcnow() на datetime.now(timezone.utc)
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
                       created_at_readable, updated_at_readable,
                       created_at, updated_at
                FROM watchlist 
                ORDER BY 
                    is_favorite DESC,
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
            readable_time = self._utc_to_readable(current_time_ms)

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

    async def save_kline_data(self, symbol: str, kline_data: Dict, is_closed: bool = False):
        """Сохранение данных свечи в базу данных с UTC временем"""
        try:
            cursor = self.connection.cursor()

            # Получаем UTC время из данных биржи
            open_time_ms = int(kline_data['start'])
            close_time_ms = int(kline_data['end'])

            # Определяем, является ли свеча LONG
            is_long = float(kline_data['close']) > float(kline_data['open'])

            # Рассчитываем объем в USDT
            volume_usdt = float(kline_data['volume']) * float(kline_data['close'])

            # Создаем читаемые временные метки
            open_time_readable = self._utc_to_readable(open_time_ms)
            close_time_readable = self._utc_to_readable(close_time_ms)
            current_time_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
            created_at_readable = self._utc_to_readable(current_time_ms)

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
        """Сохранение алерта в базу данных с UTC временем"""
        try:
            cursor = self.connection.cursor()

            # Преобразуем timestamp в UTC время
            alert_timestamp_ms = int(alert_data['timestamp']) if isinstance(alert_data['timestamp'], (int, float)) else int(datetime.fromisoformat(str(alert_data['timestamp']).replace('Z', '+00:00')).timestamp() * 1000)
            close_timestamp_ms = None
            if alert_data.get('close_timestamp'):
                if isinstance(alert_data['close_timestamp'], (int, float)):
                    close_timestamp_ms = int(alert_data['close_timestamp'])
                else:
                    close_timestamp_ms = int(datetime.fromisoformat(str(alert_data['close_timestamp']).replace('Z', '+00:00')).timestamp() * 1000)

            # Создаем читаемые временные метки
            alert_timestamp_readable = self._utc_to_readable(alert_timestamp_ms)
            close_timestamp_readable = self._utc_to_readable(close_timestamp_ms) if close_timestamp_ms else None
            current_time_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
            created_at_readable = self._utc_to_readable(current_time_ms)

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

    async def get_all_alerts(self, limit: int = 100) -> Dict[str, List[Dict]]:
        """Получить все алерты, разделенные по типам с сортировкой по UTC времени"""
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

    async def cleanup_old_data(self, retention_hours: int = 2):
        """Очистка старых данных с UTC временем"""
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

    def close(self):
        """Закрытие соединения с базой данных"""
        if self.connection:
            self.connection.close()