import asyncio
import logging
from typing import List, Dict, Optional, Tuple
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
            await self.migrate_tables()

            logger.info("База данных успешно инициализирована")

        except Exception as e:
            logger.error(f"Ошибка подключения к базе данных: {e}")
            raise

    async def create_tables(self):
        """Создание необходимых таблиц только с timestamp в миллисекундах"""
        try:
            cursor = self.connection.cursor()

            # Создаем таблицу watchlist с полем избранного
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS watchlist (
                    id SERIAL PRIMARY KEY,
                    symbol VARCHAR(20) NOT NULL UNIQUE,
                    is_active BOOLEAN DEFAULT TRUE,
                    is_favorite BOOLEAN DEFAULT FALSE,
                    price_drop_percentage DECIMAL(5, 2),
                    current_price DECIMAL(20, 8),
                    historical_price DECIMAL(20, 8),
                    created_at_ms BIGINT DEFAULT EXTRACT(EPOCH FROM NOW()) * 1000,
                    updated_at_ms BIGINT DEFAULT EXTRACT(EPOCH FROM NOW()) * 1000
                )
            """)

            # Создаем таблицу избранного (для дополнительной информации)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS favorites (
                    id SERIAL PRIMARY KEY,
                    symbol VARCHAR(20) NOT NULL UNIQUE,
                    added_at_ms BIGINT DEFAULT EXTRACT(EPOCH FROM NOW()) * 1000,
                    notes TEXT,
                    color VARCHAR(7) DEFAULT '#FFD700',
                    sort_order INTEGER DEFAULT 0
                )
            """)

            # Создаем основную таблицу для исторических данных свечей (только timestamp в мс)
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
                    created_at_ms BIGINT DEFAULT EXTRACT(EPOCH FROM NOW()) * 1000,
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
                    UNIQUE(symbol, open_time_ms)
                )
            """)

            # Создаем обновленную таблицу алертов только с timestamp в мс
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
                    candle_data JSONB,
                    preliminary_alert JSONB,
                    imbalance_data JSONB,
                    order_book_snapshot JSONB,
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

            # Индексы для избранного
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_watchlist_favorite 
                ON watchlist(is_favorite, symbol)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_favorites_sort_order 
                ON favorites(sort_order, symbol)
            """)

            cursor.close()
            logger.info("Таблицы с timestamp в миллисекундах и функциональностью избранного успешно созданы")

        except Exception as e:
            logger.error(f"Ошибка создания таблиц: {e}")
            raise

    async def migrate_tables(self):
        """Миграция существующих таблиц - добавление полей избранного"""
        try:
            cursor = self.connection.cursor()

            # Добавляем поле is_favorite в watchlist, если его нет
            try:
                cursor.execute("""
                    ALTER TABLE watchlist 
                    ADD COLUMN IF NOT EXISTS is_favorite BOOLEAN DEFAULT FALSE
                """)
                logger.debug("Добавлено поле is_favorite в таблицу watchlist")
            except Exception as e:
                logger.debug(f"Поле is_favorite уже существует в watchlist: {e}")

            # Список столбцов для удаления из каждой таблицы
            tables_to_clean = {
                'watchlist': [
                    'created_at_unix', 'updated_at_unix', 'created_at_readable', 
                    'updated_at_readable', 'created_at', 'updated_at'
                ],
                'kline_data': [
                    'open_time_unix', 'close_time_unix', 'open_time_readable', 
                    'close_time_readable', 'created_at_unix', 'created_at_readable',
                    'open_time', 'close_time', 'created_at'
                ],
                'kline_stream': [
                    'open_time_unix', 'close_time_unix', 'open_time_readable',
                    'close_time_readable', 'last_update_readable'
                ],
                'alerts': [
                    'alert_timestamp_unix', 'close_timestamp_unix', 'alert_timestamp_readable',
                    'close_timestamp_readable', 'created_at_unix', 'updated_at_unix',
                    'created_at_readable', 'updated_at_readable', 'alert_timestamp',
                    'close_timestamp', 'created_at', 'updated_at'
                ]
            }

            for table_name, columns_to_drop in tables_to_clean.items():
                for column_name in columns_to_drop:
                    try:
                        cursor.execute(f"""
                            ALTER TABLE {table_name} 
                            DROP COLUMN IF EXISTS {column_name}
                        """)
                        logger.debug(f"Удален столбец {column_name} из таблицы {table_name}")
                    except Exception as e:
                        logger.debug(f"Столбец {column_name} не существует в {table_name}: {e}")

            cursor.close()
            logger.info("Миграция таблиц завершена - добавлена функциональность избранного")

        except Exception as e:
            logger.error(f"Ошибка миграции таблиц: {e}")

    def _ms_to_datetime(self, timestamp_ms: int) -> datetime:
        """Преобразование миллисекунд в datetime"""
        try:
            return datetime.utcfromtimestamp(timestamp_ms / 1000)
        except:
            return datetime.utcnow()

    def _datetime_to_ms(self, dt: datetime) -> int:
        """Преобразование datetime в миллисекунды"""
        try:
            return int(dt.timestamp() * 1000)
        except:
            return int(datetime.utcnow().timestamp() * 1000)

    async def get_data_range_info(self, symbol: str) -> Dict:
        """Получить информацию о диапазоне данных для символа"""
        try:
            cursor = self.connection.cursor()
            
            # Получаем статистику по свечам
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_candles,
                    MIN(open_time_ms) as first_candle_ms,
                    MAX(open_time_ms) as last_candle_ms
                FROM kline_data 
                WHERE symbol = %s AND is_closed = TRUE
            """, (symbol,))
            
            result = cursor.fetchone()
            cursor.close()
            
            if not result or result[0] == 0:
                return {
                    'symbol': symbol,
                    'total_candles': 0,
                    'first_candle': None,
                    'last_candle': None,
                    'missing_candles': 0,
                    'data_range_hours': 0,
                    'expected_candles': 0,
                    'completeness_percentage': 0
                }
            
            total_candles, first_candle_ms, last_candle_ms = result
            
            # Рассчитываем ожидаемое количество свечей
            if first_candle_ms and last_candle_ms:
                time_range_ms = last_candle_ms - first_candle_ms
                expected_candles = int(time_range_ms / 60000) + 1  # +1 для включения последней свечи
                missing_candles = max(0, expected_candles - total_candles)
                completeness_percentage = (total_candles / expected_candles) * 100 if expected_candles > 0 else 0
                data_range_hours = time_range_ms / (60 * 60 * 1000)
            else:
                expected_candles = 0
                missing_candles = 0
                completeness_percentage = 0
                data_range_hours = 0
            
            return {
                'symbol': symbol,
                'total_candles': total_candles,
                'first_candle': self._ms_to_datetime(first_candle_ms) if first_candle_ms else None,
                'last_candle': self._ms_to_datetime(last_candle_ms) if last_candle_ms else None,
                'missing_candles': missing_candles,
                'data_range_hours': round(data_range_hours, 2),
                'expected_candles': expected_candles,
                'completeness_percentage': round(completeness_percentage, 1)
            }
            
        except Exception as e:
            logger.error(f"Ошибка получения информации о диапазоне данных для {symbol}: {e}")
            return {
                'symbol': symbol,
                'total_candles': 0,
                'first_candle': None,
                'last_candle': None,
                'missing_candles': 0,
                'data_range_hours': 0,
                'expected_candles': 0,
                'completeness_percentage': 0
            }

    async def check_data_integrity(self, symbol: str, hours: int) -> Dict:
        """Проверка целостности исторических данных"""
        try:
            cursor = self.connection.cursor()

            # Определяем временные границы
            current_time_ms = int(datetime.utcnow().timestamp() * 1000)
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

            # Генерируем ожидаемые временные метки (каждую минуту)
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

    async def cleanup_old_candles(self, symbol: str, retention_hours: int):
        """Очистка старых свечей для поддержания заданного диапазона"""
        try:
            cursor = self.connection.cursor()
            
            # Определяем границу для удаления старых данных
            current_time_ms = int(datetime.utcnow().timestamp() * 1000)
            cutoff_time_ms = current_time_ms - (retention_hours * 60 * 60 * 1000)
            
            # Удаляем старые данные
            cursor.execute("""
                DELETE FROM kline_data 
                WHERE symbol = %s AND open_time_ms < %s
            """, (symbol, cutoff_time_ms))
            
            deleted_count = cursor.rowcount
            
            # Также очищаем потоковые данные
            cursor.execute("""
                DELETE FROM kline_stream 
                WHERE symbol = %s AND open_time_ms < %s
            """, (symbol, cutoff_time_ms))
            
            cursor.close()
            
            if deleted_count > 0:
                logger.info(f"Удалено {deleted_count} старых свечей для {symbol}")
                
        except Exception as e:
            logger.error(f"Ошибка очистки старых свечей для {symbol}: {e}")

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
                SELECT w.id, w.symbol, w.is_active, w.is_favorite, w.price_drop_percentage, 
                       w.current_price, w.historical_price, 
                       w.created_at_ms, w.updated_at_ms,
                       f.notes, f.color, f.sort_order, f.added_at_ms
                FROM watchlist w
                LEFT JOIN favorites f ON w.symbol = f.symbol
                ORDER BY 
                    w.is_favorite DESC,
                    COALESCE(f.sort_order, 999) ASC,
                    CASE WHEN w.price_drop_percentage IS NOT NULL THEN w.price_drop_percentage ELSE 0 END DESC,
                    w.symbol ASC
            """)

            result = cursor.fetchall()
            cursor.close()

            # Преобразуем timestamp в datetime для совместимости
            watchlist_items = []
            for row in result:
                item = dict(row)
                if item['created_at_ms']:
                    item['created_at'] = self._ms_to_datetime(item['created_at_ms']).isoformat()
                if item['updated_at_ms']:
                    item['updated_at'] = self._ms_to_datetime(item['updated_at_ms']).isoformat()
                if item['added_at_ms']:
                    item['favorite_added_at'] = self._ms_to_datetime(item['added_at_ms']).isoformat()
                
                # Получаем информацию о диапазоне данных
                data_info = await self.get_data_range_info(item['symbol'])
                item['data_info'] = data_info
                
                watchlist_items.append(item)

            return watchlist_items

        except Exception as e:
            logger.error(f"Ошибка получения детальной информации watchlist: {e}")
            return []

    async def get_favorites(self) -> List[Dict]:
        """Получить список избранных торговых пар"""
        try:
            cursor = self.connection.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT w.id, w.symbol, w.is_active, w.price_drop_percentage, 
                       w.current_price, w.historical_price,
                       f.notes, f.color, f.sort_order, f.added_at_ms
                FROM watchlist w
                INNER JOIN favorites f ON w.symbol = f.symbol
                WHERE w.is_favorite = TRUE
                ORDER BY f.sort_order ASC, w.symbol ASC
            """)

            result = cursor.fetchall()
            cursor.close()

            # Преобразуем timestamp в datetime для совместимости
            favorites = []
            for row in result:
                item = dict(row)
                if item['added_at_ms']:
                    item['favorite_added_at'] = self._ms_to_datetime(item['added_at_ms']).isoformat()
                
                # Получаем информацию о диапазоне данных
                data_info = await self.get_data_range_info(item['symbol'])
                item['data_info'] = data_info
                
                favorites.append(item)

            return favorites

        except Exception as e:
            logger.error(f"Ошибка получения избранных пар: {e}")
            return []

    async def add_to_favorites(self, symbol: str, notes: str = None, color: str = '#FFD700', sort_order: int = 0):
        """Добавить торговую пару в избранное"""
        try:
            cursor = self.connection.cursor()
            current_time_ms = int(datetime.utcnow().timestamp() * 1000)

            # Обновляем watchlist
            cursor.execute("""
                UPDATE watchlist 
                SET is_favorite = TRUE, updated_at_ms = %s
                WHERE symbol = %s
            """, (current_time_ms, symbol))

            # Добавляем в таблицу favorites
            cursor.execute("""
                INSERT INTO favorites (symbol, notes, color, sort_order, added_at_ms) 
                VALUES (%s, %s, %s, %s, %s) 
                ON CONFLICT (symbol) DO UPDATE SET
                    notes = EXCLUDED.notes,
                    color = EXCLUDED.color,
                    sort_order = EXCLUDED.sort_order
            """, (symbol, notes, color, sort_order, current_time_ms))

            cursor.close()
            logger.info(f"Пара {symbol} добавлена в избранное")

        except Exception as e:
            logger.error(f"Ошибка добавления в избранное: {e}")

    async def remove_from_favorites(self, symbol: str):
        """Удалить торговую пару из избранного"""
        try:
            cursor = self.connection.cursor()
            current_time_ms = int(datetime.utcnow().timestamp() * 1000)

            # Обновляем watchlist
            cursor.execute("""
                UPDATE watchlist 
                SET is_favorite = FALSE, updated_at_ms = %s
                WHERE symbol = %s
            """, (current_time_ms, symbol))

            # Удаляем из таблицы favorites
            cursor.execute("""
                DELETE FROM favorites WHERE symbol = %s
            """, (symbol,))

            cursor.close()
            logger.info(f"Пара {symbol} удалена из избранного")

        except Exception as e:
            logger.error(f"Ошибка удаления из избранного: {e}")

    async def update_favorite(self, symbol: str, notes: str = None, color: str = None, sort_order: int = None):
        """Обновить информацию об избранной паре"""
        try:
            cursor = self.connection.cursor()

            # Формируем запрос обновления
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
                params.append(symbol)
                cursor.execute(f"""
                    UPDATE favorites 
                    SET {', '.join(update_fields)}
                    WHERE symbol = %s
                """, params)

            cursor.close()
            logger.info(f"Информация об избранной паре {symbol} обновлена")

        except Exception as e:
            logger.error(f"Ошибка обновления избранной пары: {e}")

    async def reorder_favorites(self, symbol_order: List[str]):
        """Изменить порядок избранных пар"""
        try:
            cursor = self.connection.cursor()

            for index, symbol in enumerate(symbol_order):
                cursor.execute("""
                    UPDATE favorites 
                    SET sort_order = %s
                    WHERE symbol = %s
                """, (index, symbol))

            cursor.close()
            logger.info(f"Порядок избранных пар обновлен: {len(symbol_order)} пар")

        except Exception as e:
            logger.error(f"Ошибка изменения порядка избранных пар: {e}")

    async def add_to_watchlist(self, symbol: str, price_drop: float = None,
                               current_price: float = None, historical_price: float = None):
        """Добавить торговую пару в watchlist"""
        try:
            cursor = self.connection.cursor()
            current_time_ms = int(datetime.utcnow().timestamp() * 1000)

            cursor.execute("""
                INSERT INTO watchlist (symbol, price_drop_percentage, current_price, historical_price,
                                     created_at_ms, updated_at_ms) 
                VALUES (%s, %s, %s, %s, %s, %s) 
                ON CONFLICT (symbol) DO UPDATE SET
                    is_active = TRUE,
                    price_drop_percentage = EXCLUDED.price_drop_percentage,
                    current_price = EXCLUDED.current_price,
                    historical_price = EXCLUDED.historical_price,
                    updated_at_ms = EXCLUDED.updated_at_ms
            """, (symbol, price_drop, current_price, historical_price,
                  current_time_ms, current_time_ms))

            cursor.close()

        except Exception as e:
            logger.error(f"Ошибка добавления в watchlist: {e}")

    async def update_watchlist_item(self, item_id: int, symbol: str, is_active: bool):
        """Обновить элемент watchlist"""
        try:
            cursor = self.connection.cursor()
            current_time_ms = int(datetime.utcnow().timestamp() * 1000)

            cursor.execute("""
                UPDATE watchlist 
                SET symbol = %s, is_active = %s, updated_at_ms = %s
                WHERE id = %s
            """, (symbol, is_active, current_time_ms, item_id))

            cursor.close()

        except Exception as e:
            logger.error(f"Ошибка обновления watchlist: {e}")

    async def remove_from_watchlist(self, symbol: str = None, item_id: int = None):
        """Удалить торговую пару из watchlist"""
        try:
            cursor = self.connection.cursor()

            if item_id:
                # Получаем символ для удаления из избранного
                cursor.execute("SELECT symbol FROM watchlist WHERE id = %s", (item_id,))
                result = cursor.fetchone()
                if result:
                    symbol_to_remove = result[0]
                    # Удаляем из избранного
                    await self.remove_from_favorites(symbol_to_remove)
                
                cursor.execute("DELETE FROM watchlist WHERE id = %s", (item_id,))
            elif symbol:
                # Удаляем из избранного
                await self.remove_from_favorites(symbol)
                cursor.execute("DELETE FROM watchlist WHERE symbol = %s", (symbol,))

            cursor.close()

        except Exception as e:
            logger.error(f"Ошибка удаления из watchlist: {e}")

    async def save_kline_data(self, symbol: str, kline_data: Dict, is_closed: bool = False):
        """Сохранение данных свечи в базу данных"""
        try:
            cursor = self.connection.cursor()

            # Получаем время из данных биржи
            open_time_ms = int(kline_data['start'])
            close_time_ms = int(kline_data['end'])

            # Определяем, является ли свеча LONG
            is_long = float(kline_data['close']) > float(kline_data['open'])

            # Рассчитываем объем в USDT
            volume_usdt = float(kline_data['volume']) * float(kline_data['close'])

            current_time_ms = int(datetime.utcnow().timestamp() * 1000)

            if is_closed:
                # Сохраняем в основную таблицу исторических данных
                cursor.execute("""
                    INSERT INTO kline_data 
                    (symbol, open_time_ms, close_time_ms, open_price, high_price, 
                     low_price, close_price, volume, volume_usdt, is_long, is_closed,
                     created_at_ms)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (symbol, open_time_ms) DO UPDATE SET
                        close_time_ms = EXCLUDED.close_time_ms,
                        open_price = EXCLUDED.open_price,
                        high_price = EXCLUDED.high_price,
                        low_price = EXCLUDED.low_price,
                        close_price = EXCLUDED.close_price,
                        volume = EXCLUDED.volume,
                        volume_usdt = EXCLUDED.volume_usdt,
                        is_long = EXCLUDED.is_long,
                        is_closed = EXCLUDED.is_closed
                """, (
                    symbol, open_time_ms, close_time_ms,
                    float(kline_data['open']), float(kline_data['high']),
                    float(kline_data['low']), float(kline_data['close']),
                    float(kline_data['volume']), volume_usdt, is_long, is_closed,
                    current_time_ms
                ))
            else:
                # Сохраняем в таблицу потоковых данных
                cursor.execute("""
                    INSERT INTO kline_stream 
                    (symbol, open_time_ms, close_time_ms, open_price, high_price, 
                     low_price, close_price, volume, volume_usdt, is_long, is_closed,
                     last_update_ms)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (symbol, open_time_ms) DO UPDATE SET
                        close_time_ms = EXCLUDED.close_time_ms,
                        high_price = GREATEST(kline_stream.high_price, EXCLUDED.high_price),
                        low_price = LEAST(kline_stream.low_price, EXCLUDED.low_price),
                        close_price = EXCLUDED.close_price,
                        volume = EXCLUDED.volume,
                        volume_usdt = EXCLUDED.volume_usdt,
                        is_long = EXCLUDED.is_long,
                        last_update_ms = EXCLUDED.last_update_ms
                """, (
                    symbol, open_time_ms, close_time_ms,
                    float(kline_data['open']), float(kline_data['high']),
                    float(kline_data['low']), float(kline_data['close']),
                    float(kline_data['volume']), volume_usdt, is_long, is_closed,
                    current_time_ms
                ))

            cursor.close()

        except Exception as e:
            logger.error(f"Ошибка сохранения данных свечи: {e}")

    async def save_alert(self, alert_data: Dict) -> int:
        """Сохранение алерта в базу данных"""
        try:
            cursor = self.connection.cursor()

            # Преобразуем datetime в миллисекунды
            alert_timestamp_ms = self._datetime_to_ms(alert_data['timestamp']) if isinstance(
                alert_data['timestamp'], datetime) else int(alert_data['timestamp'])
            close_timestamp_ms = None
            if alert_data.get('close_timestamp'):
                if isinstance(alert_data['close_timestamp'], datetime):
                    close_timestamp_ms = self._datetime_to_ms(alert_data['close_timestamp'])
                else:
                    close_timestamp_ms = int(alert_data['close_timestamp'])

            current_time_ms = int(datetime.utcnow().timestamp() * 1000)

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
                 created_at_ms, updated_at_ms,
                 candle_data, preliminary_alert, imbalance_data, order_book_snapshot)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                current_time_ms,
                current_time_ms,
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

            # Преобразуем datetime в миллисекунды
            close_timestamp_ms = None
            if alert_data.get('close_timestamp'):
                if isinstance(alert_data['close_timestamp'], datetime):
                    close_timestamp_ms = self._datetime_to_ms(alert_data['close_timestamp'])
                else:
                    close_timestamp_ms = int(alert_data['close_timestamp'])

            current_time_ms = int(datetime.utcnow().timestamp() * 1000)

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
                    close_timestamp_ms = %s, updated_at_ms = %s,
                    candle_data = %s, imbalance_data = %s
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
                current_time_ms,
                candle_data_json,
                imbalance_data_json,
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
                       is_closed, has_imbalance, message, telegram_sent, 
                       alert_timestamp_ms, close_timestamp_ms,
                       candle_data, preliminary_alert, imbalance_data, 
                       order_book_snapshot, created_at_ms, updated_at_ms
                FROM alerts 
                WHERE alert_type = %s
                ORDER BY COALESCE(close_timestamp_ms, alert_timestamp_ms) DESC
                LIMIT %s
            """, (alert_type, limit))

            result = cursor.fetchall()
            cursor.close()

            # Парсим JSON данные и преобразуем timestamp
            alerts = []
            for row in result:
                alert = dict(row)

                # Преобразуем timestamp в datetime для совместимости
                if alert['alert_timestamp_ms']:
                    alert['timestamp'] = self._ms_to_datetime(alert['alert_timestamp_ms']).isoformat()
                if alert['close_timestamp_ms']:
                    alert['close_timestamp'] = self._ms_to_datetime(alert['close_timestamp_ms']).isoformat()

                # Безопасный парсинг JSON
                for json_field in ['candle_data', 'preliminary_alert', 'imbalance_data', 'order_book_snapshot']:
                    if alert[json_field]:
                        try:
                            if isinstance(alert[json_field], str):
                                alert[json_field] = json.loads(alert[json_field])
                        except (json.JSONDecodeError, TypeError) as e:
                            logger.warning(f"Ошибка парсинга {json_field} для алерта {alert['id']}: {e}")
                            alert[json_field] = None

                alerts.append(alert)

            return alerts

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
                       is_closed, has_imbalance, message, telegram_sent,
                       alert_timestamp_ms, close_timestamp_ms,
                       candle_data, preliminary_alert, imbalance_data,
                       order_book_snapshot, created_at_ms, updated_at_ms
                FROM alerts 
                ORDER BY COALESCE(close_timestamp_ms, alert_timestamp_ms) DESC
                LIMIT %s
            """, (limit,))

            all_alerts_raw = cursor.fetchall()
            cursor.close()

            # Парсим JSON данные и преобразуем timestamp
            all_alerts = []
            for row in all_alerts_raw:
                alert = dict(row)

                # Преобразуем timestamp в datetime для совместимости
                if alert['alert_timestamp_ms']:
                    alert['timestamp'] = self._ms_to_datetime(alert['alert_timestamp_ms']).isoformat()
                if alert['close_timestamp_ms']:
                    alert['close_timestamp'] = self._ms_to_datetime(alert['close_timestamp_ms']).isoformat()

                # Безопасный парсинг JSON
                for json_field in ['candle_data', 'preliminary_alert', 'imbalance_data', 'order_book_snapshot']:
                    if alert[json_field]:
                        try:
                            if isinstance(alert[json_field], str):
                                alert[json_field] = json.loads(alert[json_field])
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
        """Получить объемы свечей за указанный период"""
        try:
            cursor = self.connection.cursor()

            # Рассчитываем временные границы
            current_time_ms = int(datetime.utcnow().timestamp() * 1000)
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
        """Получить данные для построения графика"""
        try:
            cursor = self.connection.cursor(cursor_factory=RealDictCursor)

            # Определяем временные границы
            if alert_time:
                try:
                    alert_dt = datetime.fromisoformat(alert_time.replace('Z', '+00:00'))
                    end_time_ms = self._datetime_to_ms(alert_dt)
                except:
                    end_time_ms = int(datetime.utcnow().timestamp() * 1000)
            else:
                end_time_ms = int(datetime.utcnow().timestamp() * 1000)

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
        """Получить недавние объемные алерты для символа"""
        try:
            cursor = self.connection.cursor(cursor_factory=RealDictCursor)

            cutoff_time_ms = int((datetime.utcnow() - timedelta(minutes=minutes_back)).timestamp() * 1000)

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
        """Очистка старых данных"""
        try:
            cursor = self.connection.cursor()

            # Удаляем старые данные свечей
            cutoff_time_ms = int((datetime.utcnow() - timedelta(hours=retention_hours)).timestamp() * 1000)

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
            alert_cutoff_ms = int((datetime.utcnow() - timedelta(hours=24)).timestamp() * 1000)
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