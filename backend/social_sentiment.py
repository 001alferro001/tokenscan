import asyncio
import logging
import aiohttp
import json
import re
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass
from enum import Enum
import hashlib
import time

logger = logging.getLogger(__name__)

class SentimentScore(Enum):
    VERY_NEGATIVE = -2
    NEGATIVE = -1
    NEUTRAL = 0
    POSITIVE = 1
    VERY_POSITIVE = 2

@dataclass
class SocialMention:
    platform: str
    text: str
    author: str
    timestamp: datetime
    url: Optional[str]
    engagement: int  # likes, retweets, views etc
    sentiment_score: float
    confidence: float

@dataclass
class SocialRating:
    symbol: str
    overall_score: float  # -100 to 100
    mention_count: int
    positive_mentions: int
    negative_mentions: int
    neutral_mentions: int
    trending_score: float  # 0 to 100
    volume_score: float  # 0 to 100
    sentiment_trend: str  # 'rising', 'falling', 'stable'
    last_updated: datetime
    top_mentions: List[SocialMention]

class SocialSentimentAnalyzer:
    """Анализатор социальных настроений для торговых пар"""
    
    def __init__(self, db_manager):
        self.db_manager = db_manager
        self.session = None
        
        # Ключевые слова для поиска
        self.crypto_keywords = {
            'positive': [
                'moon', 'bullish', 'pump', 'rocket', 'gem', 'buy', 'long',
                'breakout', 'rally', 'surge', 'explosion', 'massive', 'huge',
                'profit', 'gains', 'winner', 'golden', 'diamond', 'fire'
            ],
            'negative': [
                'dump', 'crash', 'bearish', 'sell', 'short', 'scam', 'rug',
                'dead', 'rip', 'loss', 'down', 'fall', 'drop', 'disaster',
                'avoid', 'warning', 'danger', 'exit', 'liquidated'
            ],
            'neutral': [
                'analysis', 'chart', 'technical', 'support', 'resistance',
                'volume', 'price', 'market', 'trading', 'hodl', 'dyor'
            ]
        }
        
        # Настройки анализа
        self.analysis_period_hours = 72  # 3 дня
        self.min_mentions_for_rating = 5
        self.cache_duration_minutes = 30
        
        # Кэш для избежания повторных запросов
        self.ratings_cache = {}
        self.last_cache_update = {}

    async def start(self):
        """Запуск анализатора"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
        )
        logger.info("Social sentiment analyzer started")

    async def stop(self):
        """Остановка анализатора"""
        if self.session:
            await self.session.close()
        logger.info("Social sentiment analyzer stopped")

    async def get_symbol_rating(self, symbol: str) -> Optional[SocialRating]:
        """Получить рейтинг для торговой пары"""
        try:
            # Проверяем кэш
            cache_key = symbol
            if (cache_key in self.ratings_cache and 
                cache_key in self.last_cache_update and
                (datetime.now(timezone.utc) - self.last_cache_update[cache_key]).total_seconds() < self.cache_duration_minutes * 60):
                return self.ratings_cache[cache_key]

            # Получаем упоминания из разных источников
            mentions = []
            
            # Twitter/X (через публичные API или скрапинг)
            twitter_mentions = await self._get_twitter_mentions(symbol)
            mentions.extend(twitter_mentions)
            
            # Telegram (через публичные каналы)
            telegram_mentions = await self._get_telegram_mentions(symbol)
            mentions.extend(telegram_mentions)
            
            # Reddit
            reddit_mentions = await self._get_reddit_mentions(symbol)
            mentions.extend(reddit_mentions)
            
            # CoinGecko trending
            coingecko_data = await self._get_coingecko_trending(symbol)
            
            if len(mentions) < self.min_mentions_for_rating:
                logger.debug(f"Недостаточно упоминаний для {symbol}: {len(mentions)}")
                return None

            # Анализируем настроения
            rating = await self._calculate_rating(symbol, mentions, coingecko_data)
            
            # Сохраняем в кэш
            self.ratings_cache[cache_key] = rating
            self.last_cache_update[cache_key] = datetime.now(timezone.utc)
            
            # Сохраняем в базу данных
            await self._save_rating_to_db(rating)
            
            return rating

        except Exception as e:
            logger.error(f"Ошибка получения рейтинга для {symbol}: {e}")
            return None

    async def _get_twitter_mentions(self, symbol: str) -> List[SocialMention]:
        """Получение упоминаний из Twitter/X"""
        mentions = []
        try:
            # Используем публичные источники или API
            # Здесь можно интегрировать с Twitter API v2 или альтернативными сервисами
            
            # Пример поиска через альтернативные источники
            search_terms = [
                symbol,
                symbol.replace('USDT', ''),
                f"${symbol.replace('USDT', '')}",
                f"#{symbol.replace('USDT', '')}"
            ]
            
            for term in search_terms:
                # Имитация получения данных (в реальности здесь будет API запрос)
                mock_mentions = await self._mock_twitter_data(symbol, term)
                mentions.extend(mock_mentions)
                
                # Задержка между запросами
                await asyncio.sleep(0.5)

        except Exception as e:
            logger.error(f"Ошибка получения Twitter упоминаний для {symbol}: {e}")
        
        return mentions

    async def _get_telegram_mentions(self, symbol: str) -> List[SocialMention]:
        """Получение упоминаний из Telegram"""
        mentions = []
        try:
            # Список популярных крипто каналов (публичные)
            channels = [
                '@cryptonews',
                '@binance',
                '@bybit_official',
                '@coindesk',
                '@cointelegraph'
            ]
            
            # В реальности здесь будет интеграция с Telegram API
            # Пока используем моковые данные
            for channel in channels:
                mock_mentions = await self._mock_telegram_data(symbol, channel)
                mentions.extend(mock_mentions)
                await asyncio.sleep(0.3)

        except Exception as e:
            logger.error(f"Ошибка получения Telegram упоминаний для {symbol}: {e}")
        
        return mentions

    async def _get_reddit_mentions(self, symbol: str) -> List[SocialMention]:
        """Получение упоминаний из Reddit"""
        mentions = []
        try:
            # Поиск в популярных крипто сабреддитах
            subreddits = ['cryptocurrency', 'CryptoMoonShots', 'altcoin', 'Bitcoin']
            
            for subreddit in subreddits:
                # В реальности здесь будет Reddit API
                mock_mentions = await self._mock_reddit_data(symbol, subreddit)
                mentions.extend(mock_mentions)
                await asyncio.sleep(0.4)

        except Exception as e:
            logger.error(f"Ошибка получения Reddit упоминаний для {symbol}: {e}")
        
        return mentions

    async def _get_coingecko_trending(self, symbol: str) -> Dict:
        """Получение данных о трендах с CoinGecko"""
        try:
            if not self.session:
                return {}
                
            # Получаем trending данные
            url = "https://api.coingecko.com/api/v3/search/trending"
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Ищем наш символ в трендах
                    clean_symbol = symbol.replace('USDT', '').lower()
                    for coin in data.get('coins', []):
                        if coin.get('item', {}).get('symbol', '').lower() == clean_symbol:
                            return {
                                'trending_rank': coin.get('item', {}).get('market_cap_rank', 0),
                                'score': coin.get('item', {}).get('score', 0)
                            }
            
            return {}

        except Exception as e:
            logger.error(f"Ошибка получения CoinGecko данных для {symbol}: {e}")
            return {}

    async def _mock_twitter_data(self, symbol: str, term: str) -> List[SocialMention]:
        """Моковые данные Twitter (заменить на реальный API)"""
        mentions = []
        
        # Генерируем случайные упоминания для демонстрации
        import random
        
        for i in range(random.randint(2, 8)):
            sentiment_words = random.choice([
                self.crypto_keywords['positive'],
                self.crypto_keywords['negative'],
                self.crypto_keywords['neutral']
            ])
            
            word = random.choice(sentiment_words)
            text = f"{term} is looking {word} today! #crypto #trading"
            
            mention = SocialMention(
                platform='twitter',
                text=text,
                author=f"user_{random.randint(1000, 9999)}",
                timestamp=datetime.now(timezone.utc) - timedelta(hours=random.randint(1, 72)),
                url=f"https://twitter.com/user/status/{random.randint(1000000, 9999999)}",
                engagement=random.randint(1, 100),
                sentiment_score=self._analyze_text_sentiment(text),
                confidence=random.uniform(0.6, 0.9)
            )
            mentions.append(mention)
        
        return mentions

    async def _mock_telegram_data(self, symbol: str, channel: str) -> List[SocialMention]:
        """Моковые данные Telegram"""
        mentions = []
        import random
        
        for i in range(random.randint(1, 5)):
            sentiment_words = random.choice([
                self.crypto_keywords['positive'],
                self.crypto_keywords['negative'],
                self.crypto_keywords['neutral']
            ])
            
            word = random.choice(sentiment_words)
            text = f"Analysis: {symbol} shows {word} signals"
            
            mention = SocialMention(
                platform='telegram',
                text=text,
                author=channel,
                timestamp=datetime.now(timezone.utc) - timedelta(hours=random.randint(1, 72)),
                url=f"https://t.me/{channel.replace('@', '')}/{random.randint(100, 999)}",
                engagement=random.randint(10, 500),
                sentiment_score=self._analyze_text_sentiment(text),
                confidence=random.uniform(0.7, 0.95)
            )
            mentions.append(mention)
        
        return mentions

    async def _mock_reddit_data(self, symbol: str, subreddit: str) -> List[SocialMention]:
        """Моковые данные Reddit"""
        mentions = []
        import random
        
        for i in range(random.randint(1, 4)):
            sentiment_words = random.choice([
                self.crypto_keywords['positive'],
                self.crypto_keywords['negative'],
                self.crypto_keywords['neutral']
            ])
            
            word = random.choice(sentiment_words)
            text = f"Discussion about {symbol}: {word} potential"
            
            mention = SocialMention(
                platform='reddit',
                text=text,
                author=f"reddit_user_{random.randint(100, 999)}",
                timestamp=datetime.now(timezone.utc) - timedelta(hours=random.randint(1, 72)),
                url=f"https://reddit.com/r/{subreddit}/comments/{random.randint(100000, 999999)}",
                engagement=random.randint(5, 200),
                sentiment_score=self._analyze_text_sentiment(text),
                confidence=random.uniform(0.5, 0.8)
            )
            mentions.append(mention)
        
        return mentions

    def _analyze_text_sentiment(self, text: str) -> float:
        """Анализ настроений текста"""
        text_lower = text.lower()
        
        positive_score = 0
        negative_score = 0
        
        # Подсчитываем позитивные слова
        for word in self.crypto_keywords['positive']:
            if word in text_lower:
                positive_score += 1
        
        # Подсчитываем негативные слова
        for word in self.crypto_keywords['negative']:
            if word in text_lower:
                negative_score += 1
        
        # Рассчитываем итоговый счет (-1 до 1)
        total_words = positive_score + negative_score
        if total_words == 0:
            return 0.0
        
        return (positive_score - negative_score) / total_words

    async def _calculate_rating(self, symbol: str, mentions: List[SocialMention], coingecko_data: Dict) -> SocialRating:
        """Расчет итогового рейтинга"""
        if not mentions:
            return SocialRating(
                symbol=symbol,
                overall_score=0,
                mention_count=0,
                positive_mentions=0,
                negative_mentions=0,
                neutral_mentions=0,
                trending_score=0,
                volume_score=0,
                sentiment_trend='stable',
                last_updated=datetime.now(timezone.utc),
                top_mentions=[]
            )

        # Подсчитываем типы упоминаний
        positive_count = len([m for m in mentions if m.sentiment_score > 0.2])
        negative_count = len([m for m in mentions if m.sentiment_score < -0.2])
        neutral_count = len(mentions) - positive_count - negative_count

        # Рассчитываем общий счет настроений
        total_sentiment = sum(m.sentiment_score * m.confidence for m in mentions)
        avg_sentiment = total_sentiment / len(mentions) if mentions else 0
        overall_score = max(-100, min(100, avg_sentiment * 100))

        # Рассчитываем trending score
        trending_score = 0
        if coingecko_data.get('trending_rank'):
            # Чем выше ранг, тем больше trending score
            trending_score = max(0, 100 - coingecko_data['trending_rank'])

        # Рассчитываем volume score на основе количества упоминаний
        volume_score = min(100, (len(mentions) / 50) * 100)

        # Определяем тренд настроений
        recent_mentions = [m for m in mentions if 
                          (datetime.now(timezone.utc) - m.timestamp).total_seconds() < 24 * 3600]
        older_mentions = [m for m in mentions if 
                         (datetime.now(timezone.utc) - m.timestamp).total_seconds() >= 24 * 3600]

        sentiment_trend = 'stable'
        if recent_mentions and older_mentions:
            recent_sentiment = sum(m.sentiment_score for m in recent_mentions) / len(recent_mentions)
            older_sentiment = sum(m.sentiment_score for m in older_mentions) / len(older_mentions)
            
            if recent_sentiment > older_sentiment + 0.1:
                sentiment_trend = 'rising'
            elif recent_sentiment < older_sentiment - 0.1:
                sentiment_trend = 'falling'

        # Топ упоминания (по engagement)
        top_mentions = sorted(mentions, key=lambda x: x.engagement, reverse=True)[:5]

        return SocialRating(
            symbol=symbol,
            overall_score=round(overall_score, 1),
            mention_count=len(mentions),
            positive_mentions=positive_count,
            negative_mentions=negative_count,
            neutral_mentions=neutral_count,
            trending_score=round(trending_score, 1),
            volume_score=round(volume_score, 1),
            sentiment_trend=sentiment_trend,
            last_updated=datetime.now(timezone.utc),
            top_mentions=top_mentions
        )

    async def _save_rating_to_db(self, rating: SocialRating):
        """Сохранение рейтинга в базу данных"""
        try:
            cursor = self.db_manager.connection.cursor()
            
            # Создаем таблицу если не существует
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS social_ratings (
                    id SERIAL PRIMARY KEY,
                    symbol VARCHAR(20) NOT NULL,
                    overall_score FLOAT NOT NULL,
                    mention_count INTEGER NOT NULL,
                    positive_mentions INTEGER NOT NULL,
                    negative_mentions INTEGER NOT NULL,
                    neutral_mentions INTEGER NOT NULL,
                    trending_score FLOAT NOT NULL,
                    volume_score FLOAT NOT NULL,
                    sentiment_trend VARCHAR(20) NOT NULL,
                    last_updated TIMESTAMPTZ NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            
            # Удаляем старые записи для символа
            cursor.execute("""
                DELETE FROM social_ratings 
                WHERE symbol = %s AND created_at < NOW() - INTERVAL '1 day'
            """, (rating.symbol,))
            
            # Вставляем новую запись
            cursor.execute("""
                INSERT INTO social_ratings (
                    symbol, overall_score, mention_count, positive_mentions,
                    negative_mentions, neutral_mentions, trending_score,
                    volume_score, sentiment_trend, last_updated
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                rating.symbol, rating.overall_score, rating.mention_count,
                rating.positive_mentions, rating.negative_mentions, rating.neutral_mentions,
                rating.trending_score, rating.volume_score, rating.sentiment_trend,
                rating.last_updated
            ))
            
            self.db_manager.connection.commit()
            cursor.close()
            
        except Exception as e:
            logger.error(f"Ошибка сохранения рейтинга в БД: {e}")
            if cursor:
                cursor.close()

    async def get_ratings_for_symbols(self, symbols: List[str]) -> Dict[str, SocialRating]:
        """Получить рейтинги для списка символов"""
        ratings = {}
        
        # Ограничиваем количество одновременных запросов
        semaphore = asyncio.Semaphore(5)
        
        async def get_rating_with_semaphore(symbol):
            async with semaphore:
                rating = await self.get_symbol_rating(symbol)
                if rating:
                    ratings[symbol] = rating
                await asyncio.sleep(0.2)  # Задержка между запросами
        
        # Запускаем задачи параллельно
        tasks = [get_rating_with_semaphore(symbol) for symbol in symbols]
        await asyncio.gather(*tasks, return_exceptions=True)
        
        return ratings

    def get_rating_emoji(self, score: float) -> str:
        """Получить эмодзи для рейтинга"""
        if score >= 70:
            return "🚀"  # Очень позитивно
        elif score >= 40:
            return "📈"  # Позитивно
        elif score >= 10:
            return "🟢"  # Слабо позитивно
        elif score >= -10:
            return "⚪"  # Нейтрально
        elif score >= -40:
            return "🟡"  # Слабо негативно
        elif score >= -70:
            return "📉"  # Негативно
        else:
            return "🔴"  # Очень негативно

    def get_trend_emoji(self, trend: str) -> str:
        """Получить эмодзи для тренда"""
        if trend == 'rising':
            return "⬆️"
        elif trend == 'falling':
            return "⬇️"
        else:
            return "➡️"