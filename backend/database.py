import asyncio
import logging
from typing import List, Dict, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta
import os

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
        """Создание необходимых таблиц"""
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
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Создаем таблицу для хранения исторических данных
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
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(symbol, open_time)
                )
            """)

            # Создаем обновленную таблицу алертов
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
                    message TEXT,
                    telegram_sent BOOLEAN DEFAULT FALSE,
                    alert_timestamp TIMESTAMP NOT NULL,
                    close_timestamp TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Создаем индексы для оптимизации запросов
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_kline_symbol_time 
                ON kline_data(symbol, open_time)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_kline_symbol_long_time 
                ON kline_data(symbol, is_long, open_time)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_alerts_symbol_type_time 
                ON alerts(symbol, alert_type, alert_timestamp)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_alerts_type_created 
                ON alerts(alert_type, created_at)
            """)

            cursor.close()
            logger.info("Таблицы успешно созданы")

        except Exception as e:
            logger.error(f"Ошибка создания таблиц: {e}")
            raise

    async def update_tables(self):
        """Обновление существующих таблиц для добавления новых колонок"""
        try:
            cursor = self.connection.cursor()

            # Проверяем и добавляем новые колонки в таблицу watchlist
            cursor.execute("""
                SELECT column_name FROM information_schema.columns 
                WHERE table_name = 'watchlist' AND column_name = 'price_drop_percentage'
            """)

            if not cursor.fetchone():
                logger.info("Добавление новых колонок в таблицу watchlist...")

                cursor.execute("""
                    ALTER TABLE watchlist 
                    ADD COLUMN IF NOT EXISTS price_drop_percentage DECIMAL(5, 2),
                    ADD COLUMN IF NOT EXISTS current_price DECIMAL(20, 8),
                    ADD COLUMN IF NOT EXISTS historical_price DECIMAL(20, 8),
                    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                """)

                logger.info("Новые колонки добавлены в таблицу watchlist")

            # Обновляем таблицу алертов для новой структуры
            cursor.execute("""
                ALTER TABLE alerts 
                ADD COLUMN IF NOT EXISTS is_true_signal BOOLEAN,
                ADD COLUMN IF NOT EXISTS is_closed BOOLEAN DEFAULT FALSE,
                ADD COLUMN IF NOT EXISTS alert_timestamp TIMESTAMP,
                ADD COLUMN IF NOT EXISTS close_timestamp TIMESTAMP,
                ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            """)

            # Обновляем существующие записи, если alert_timestamp пустой
            cursor.execute("""
                UPDATE alerts 
                SET alert_timestamp = created_at 
                WHERE alert_timestamp IS NULL
            """)

            cursor.close()

        except Exception as e:
            logger.error(f"Ошибка обновления таблиц: {e}")

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
                ORDER BY updated_at DESC
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
                INSERT INTO watchlist (symbol, price_drop_percentage, current_price, historical_price) 
                VALUES (%s, %s, %s, %s) 
                ON CONFLICT (symbol) DO UPDATE SET
                    is_active = TRUE,
                    price_drop_percentage = EXCLUDED.price_drop_percentage,
                    current_price = EXCLUDED.current_price,
                    historical_price = EXCLUDED.historical_price,
                    updated_at = CURRENT_TIMESTAMP
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
                SET symbol = %s, is_active = %s, updated_at = CURRENT_TIMESTAMP
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

    async def save_kline_data(self, symbol: str, kline_data: Dict):
        """Сохранение данных свечи в базу данных"""
        try:
            cursor = self.connection.cursor()

            # Определяем, является ли свеча LONG (зеленой)
            is_long = float(kline_data['close']) > float(kline_data['open'])

            # Рассчитываем объем в USDT
            volume_usdt = float(kline_data['volume']) * float(kline_data['close'])

            cursor.execute("""
                INSERT INTO kline_data 
                (symbol, open_time, close_time, open_price, high_price, 
                 low_price, close_price, volume, volume_usdt, is_long)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (symbol, open_time) DO UPDATE SET
                    close_time = EXCLUDED.close_time,
                    open_price = EXCLUDED.open_price,
                    high_price = EXCLUDED.high_price,
                    low_price = EXCLUDED.low_price,
                    close_price = EXCLUDED.close_price,
                    volume = EXCLUDED.volume,
                    volume_usdt = EXCLUDED.volume_usdt,
                    is_long = EXCLUDED.is_long
            """, (
                symbol,
                int(kline_data['start']),
                int(kline_data['end']),
                float(kline_data['open']),
                float(kline_data['high']),
                float(kline_data['low']),
                float(kline_data['close']),
                float(kline_data['volume']),
                volume_usdt,
                is_long
            ))

            cursor.close()

        except Exception as e:
            logger.error(f"Ошибка сохранения данных свечи: {e}")

    async def save_alert(self, alert_data: Dict) -> int:
        """Сохранение алерта в базу данных"""
        try:
            cursor = self.connection.cursor()
            
            cursor.execute("""
                INSERT INTO alerts 
                (symbol, alert_type, price, volume_ratio, consecutive_count,
                 current_volume_usdt, average_volume_usdt, is_true_signal, 
                 is_closed, message, alert_timestamp, close_timestamp)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                alert_data.get('message', ''),
                alert_data['timestamp'],
                alert_data.get('close_timestamp')
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
            
            cursor.execute("""
                UPDATE alerts 
                SET price = %s, volume_ratio = %s, consecutive_count = %s,
                    current_volume_usdt = %s, average_volume_usdt = %s,
                    is_true_signal = %s, is_closed = %s, message = %s,
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
                alert_data.get('message', ''),
                alert_data.get('close_timestamp'),
                alert_id
            ))

            cursor.close()

        except Exception as e:
            logger.error(f"Ошибка обновления алерта: {e}")

    async def get_alerts_by_type(self, alert_type: str, limit: int = 50) -> List[Dict]:
        """Получить алерты по типу"""
        try:
            cursor = self.connection.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT id, symbol, alert_type, price, volume_ratio, consecutive_count,
                       current_volume_usdt, average_volume_usdt, is_true_signal, 
                       is_closed, message, telegram_sent, alert_timestamp as timestamp,
                       close_timestamp, created_at, updated_at
                FROM alerts 
                WHERE alert_type = %s
                ORDER BY created_at DESC 
                LIMIT %s
            """, (alert_type, limit))

            result = cursor.fetchall()
            cursor.close()

            return [dict(row) for row in result]

        except Exception as e:
            logger.error(f"Ошибка получения алертов по типу {alert_type}: {e}")
            return []

    async def get_all_alerts(self, limit: int = 100) -> Dict[str, List[Dict]]:
        """Получить все алерты, разделенные по типам"""
        try:
            cursor = self.connection.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT id, symbol, alert_type, price, volume_ratio, consecutive_count,
                       current_volume_usdt, average_volume_usdt, is_true_signal, 
                       is_closed, message, telegram_sent, alert_timestamp as timestamp,
                       close_timestamp, created_at, updated_at
                FROM alerts 
                ORDER BY created_at DESC 
                LIMIT %s
            """, (limit,))

            all_alerts = [dict(row) for row in cursor.fetchall()]
            cursor.close()

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

    async def get_historical_long_volumes(self, symbol: str, hours: int, offset_minutes: int = 0) -> List[float]:
        """Получить объемы LONG свечей за указанный период"""
        try:
            cursor = self.connection.cursor()

            # Рассчитываем временные границы
            current_time = int(datetime.now().timestamp() * 1000)
            end_time = current_time - (offset_minutes * 60 * 1000)
            start_time = end_time - (hours * 60 * 60 * 1000)

            cursor.execute("""
                SELECT volume_usdt FROM kline_data 
                WHERE symbol = %s 
                AND is_long = TRUE 
                AND open_time >= %s 
                AND open_time < %s
                ORDER BY open_time
            """, (symbol, start_time, end_time))

            volumes = [float(row[0]) for row in cursor.fetchall()]
            cursor.close()

            return volumes

        except Exception as e:
            logger.error(f"Ошибка получения исторических объемов: {e}")
            return []

    async def get_chart_data(self, symbol: str, hours: int = 1, alert_time: str = None) -> List[Dict]:
        """Получить данные для построения графика"""
        try:
            cursor = self.connection.cursor(cursor_factory=RealDictCursor)

            # Определяем временные границы
            if alert_time:
                end_time = int(datetime.fromisoformat(alert_time.replace('Z', '+00:00')).timestamp() * 1000)
            else:
                end_time = int(datetime.now().timestamp() * 1000)
            
            start_time = end_time - (hours * 60 * 60 * 1000)

            cursor.execute("""
                SELECT open_time as timestamp, open_price as open, high_price as high,
                       low_price as low, close_price as close, volume, volume_usdt, is_long
                FROM kline_data 
                WHERE symbol = %s 
                AND open_time >= %s 
                AND open_time <= %s
                ORDER BY open_time
            """, (symbol, start_time, end_time))

            result = cursor.fetchall()
            cursor.close()

            return [dict(row) for row in result]

        except Exception as e:
            logger.error(f"Ошибка получения данных графика для {symbol}: {e}")
            return []

    async def get_recent_volume_alerts(self, symbol: str, minutes_back: int) -> List[Dict]:
        """Получить недавние объемные алерты для символа"""
        try:
            cursor = self.connection.cursor(cursor_factory=RealDictCursor)
            
            cutoff_time = datetime.now() - timedelta(minutes=minutes_back)
            
            cursor.execute("""
                SELECT * FROM alerts 
                WHERE symbol = %s 
                AND alert_type = 'volume_spike'
                AND alert_timestamp >= %s
                ORDER BY alert_timestamp DESC
            """, (symbol, cutoff_time))

            result = cursor.fetchall()
            cursor.close()

            return [dict(row) for row in result]

        except Exception as e:
            logger.error(f"Ошибка получения недавних объемных алертов для {symbol}: {e}")
            return []

    async def cleanup_old_data(self, retention_hours: int = 2):
        """Очистка старых данных"""
        try:
            cursor = self.connection.cursor()
            
            # Удаляем старые данные свечей
            cutoff_time = int((datetime.now() - timedelta(hours=retention_hours)).timestamp() * 1000)
            
            cursor.execute("""
                DELETE FROM kline_data 
                WHERE open_time < %s
            """, (cutoff_time,))
            
            deleted_klines = cursor.rowcount
            
            # Удаляем старые алерты (старше 24 часов)
            alert_cutoff = datetime.now() - timedelta(hours=24)
            cursor.execute("""
                DELETE FROM alerts 
                WHERE created_at < %s
            """, (alert_cutoff,))
            
            deleted_alerts = cursor.rowcount
            
            cursor.close()
            
            logger.info(f"Очищено {deleted_klines} записей свечей и {deleted_alerts} алертов")

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