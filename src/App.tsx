import React, { useState, useEffect } from 'react';
import { 
  BarChart3, 
  Settings, 
  Wifi, 
  WifiOff, 
  Heart, 
  List, 
  TrendingUp, 
  TrendingDown, 
  Activity,
  ExternalLink,
  Star,
  MessageCircle,
  ThumbsUp,
  ThumbsDown,
  Minus
} from 'lucide-react';
import SettingsModal from './components/SettingsModal';
import WatchlistModal from './components/WatchlistModal';
import FavoritesModal from './components/FavoritesModal';
import ChartSelector from './components/ChartSelector';
import StreamDataModal from './components/StreamDataModal';
import TimeZoneToggle from './components/TimeZoneToggle';
import { useTimeZone } from './contexts/TimeZoneContext';
import { formatTime } from './utils/timeUtils';

interface Alert {
  id: number;
  symbol: string;
  alert_type: string;
  price: number;
  timestamp: number | string;
  close_timestamp?: number | string;
  volume_ratio?: number;
  consecutive_count?: number;
  current_volume_usdt?: number;
  average_volume_usdt?: number;
  preliminary_alert?: Alert;
  has_imbalance?: boolean;
  imbalance_data?: any;
  candle_data?: any;
  order_book_snapshot?: any;
  message?: string;
}

interface StreamData {
  symbol: string;
  price: number;
  volume: number;
  volume_usdt: number;
  is_long: boolean;
  timestamp: string;
  change_24h?: number;
}

interface WatchlistItem {
  id: number;
  symbol: string;
  is_active: boolean;
  is_favorite: boolean;
  price_drop_percentage?: number;
  current_price?: number;
  historical_price?: number;
  created_at: string;
  updated_at: string;
}

interface FavoriteItem {
  id: number;
  symbol: string;
  is_active: boolean;
  price_drop_percentage?: number;
  current_price?: number;
  historical_price?: number;
  notes?: string;
  color?: string;
  sort_order?: number;
  favorite_added_at?: string;
}

interface SocialRating {
  overall_score: number;
  mention_count: number;
  positive_mentions: number;
  negative_mentions: number;
  neutral_mentions: number;
  trending_score: number;
  volume_score: number;
  sentiment_trend: string;
  last_updated: string;
  rating_emoji: string;
  trend_emoji: string;
  top_mentions: Array<{
    platform: string;
    text: string;
    author: string;
    engagement: number;
    sentiment_score: number;
    timestamp: string;
  }>;
}

function App() {
  const [alerts, setAlerts] = useState<{
    volume_alerts: Alert[];
    consecutive_alerts: Alert[];
    priority_alerts: Alert[];
  }>({
    volume_alerts: [],
    consecutive_alerts: [],
    priority_alerts: []
  });
  
  const [stats, setStats] = useState<any>(null);
  const [settings, setSettings] = useState<any>(null);
  const [showSettings, setShowSettings] = useState(false);
  const [showWatchlist, setShowWatchlist] = useState(false);
  const [showFavorites, setShowFavorites] = useState(false);
  const [showStreamData, setShowStreamData] = useState(false);
  const [selectedAlert, setSelectedAlert] = useState<Alert | null>(null);
  const [connectionStatus, setConnectionStatus] = useState<'connecting' | 'connected' | 'disconnected'>('connecting');
  const [streamData, setStreamData] = useState<StreamData[]>([]);
  const [watchlist, setWatchlist] = useState<WatchlistItem[]>([]);
  const [favorites, setFavorites] = useState<FavoriteItem[]>([]);
  const [activeTab, setActiveTab] = useState<'volume' | 'consecutive' | 'priority' | 'favorites'>('volume');
  const [socialRatings, setSocialRatings] = useState<{[symbol: string]: SocialRating}>({});
  
  const { timeZone } = useTimeZone();

  useEffect(() => {
    loadInitialData();
    connectWebSocket();
    
    const interval = setInterval(loadStats, 30000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    loadSocialRatings();
    const interval = setInterval(loadSocialRatings, 300000); // Каждые 5 минут
    return () => clearInterval(interval);
  }, [watchlist, favorites]);

  const loadInitialData = async () => {
    await Promise.all([
      loadStats(),
      loadSettings(),
      loadAlerts(),
      loadWatchlist(),
      loadFavorites()
    ]);
  };

  const loadStats = async () => {
    try {
      const response = await fetch('/api/stats');
      if (response.ok) {
        const data = await response.json();
        setStats(data);
      }
    } catch (error) {
      console.error('Ошибка загрузки статистики:', error);
    }
  };

  const loadSettings = async () => {
    try {
      const response = await fetch('/api/settings');
      if (response.ok) {
        const data = await response.json();
        setSettings(data);
      }
    } catch (error) {
      console.error('Ошибка загрузки настроек:', error);
    }
  };

  const loadAlerts = async () => {
    try {
      const response = await fetch('/api/alerts/all');
      if (response.ok) {
        const data = await response.json();
        setAlerts(data);
      }
    } catch (error) {
      console.error('Ошибка загрузки алертов:', error);
    }
  };

  const loadWatchlist = async () => {
    try {
      const response = await fetch('/api/watchlist');
      if (response.ok) {
        const data = await response.json();
        setWatchlist(data.pairs || []);
      }
    } catch (error) {
      console.error('Ошибка загрузки watchlist:', error);
    }
  };

  const loadFavorites = async () => {
    try {
      const response = await fetch('/api/favorites');
      if (response.ok) {
        const data = await response.json();
        setFavorites(data.favorites || []);
      }
    } catch (error) {
      console.error('Ошибка загрузки избранного:', error);
    }
  };

  const loadSocialRatings = async () => {
    try {
      // Получаем рейтинги для всех активных пар
      const allSymbols = [...new Set([
        ...watchlist.filter(w => w.is_active).map(w => w.symbol),
        ...favorites.map(f => f.symbol)
      ])];
      
      if (allSymbols.length === 0) return;
      
      const response = await fetch(`/api/social-ratings?symbols=${allSymbols.join(',')}`);
      if (response.ok) {
        const data = await response.json();
        setSocialRatings(data.ratings || {});
      }
    } catch (error) {
      console.error('Ошибка загрузки социальных рейтингов:', error);
    }
  };

  const connectWebSocket = () => {
    const ws = new WebSocket(`ws://${window.location.host}/ws`);
    
    ws.onopen = () => {
      setConnectionStatus('connected');
      console.log('WebSocket подключен');
    };
    
    ws.onclose = () => {
      setConnectionStatus('disconnected');
      console.log('WebSocket отключен');
      setTimeout(connectWebSocket, 5000);
    };
    
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        
        if (data.type === 'new_alert') {
          loadAlerts();
          
          if (Notification.permission === 'granted') {
            new Notification(`Новый алерт: ${data.alert.symbol}`, {
              body: data.alert.message || 'Превышение объема',
              icon: '/favicon.ico'
            });
          }
        } else if (data.type === 'kline_update') {
          setStreamData(prev => {
            const newData = {
              symbol: data.symbol,
              price: parseFloat(data.data.close),
              volume: parseFloat(data.data.volume),
              volume_usdt: parseFloat(data.data.close) * parseFloat(data.data.volume),
              is_long: parseFloat(data.data.close) > parseFloat(data.data.open),
              timestamp: data.timestamp
            };
            
            const filtered = prev.filter(item => item.symbol !== data.symbol);
            return [newData, ...filtered].slice(0, 50);
          });
        }
      } catch (error) {
        console.error('Ошибка обработки WebSocket сообщения:', error);
      }
    };
    
    const pingInterval = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'ping' }));
      }
    }, 30000);
    
    ws.onclose = () => {
      clearInterval(pingInterval);
    };
  };

  const handleSaveSettings = async (newSettings: any) => {
    try {
      const response = await fetch('/api/settings', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(newSettings),
      });
      
      if (response.ok) {
        setSettings(newSettings);
        alert('Настройки сохранены');
      } else {
        alert('Ошибка сохранения настроек');
      }
    } catch (error) {
      console.error('Ошибка сохранения настроек:', error);
      alert('Ошибка сохранения настроек');
    }
  };

  const handleToggleFavorite = async (symbol: string, isFavorite: boolean) => {
    try {
      if (isFavorite) {
        // Удаляем из избранного
        const response = await fetch(`/api/favorites/${symbol}`, {
          method: 'DELETE'
        });
        if (response.ok) {
          loadFavorites();
          loadWatchlist();
        }
      } else {
        // Добавляем в избранное
        const response = await fetch('/api/favorites', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ symbol }),
        });
        if (response.ok) {
          loadFavorites();
          loadWatchlist();
        }
      }
    } catch (error) {
      console.error('Ошибка переключения избранного:', error);
    }
  };

  const clearAlerts = async (alertType: string) => {
    if (!confirm(`Очистить все алерты типа "${alertType}"?`)) return;
    
    try {
      const response = await fetch(`/api/alerts/clear/${alertType}`, {
        method: 'DELETE'
      });
      
      if (response.ok) {
        loadAlerts();
      } else {
        alert('Ошибка очистки алертов');
      }
    } catch (error) {
      console.error('Ошибка очистки алертов:', error);
      alert('Ошибка очистки алертов');
    }
  };

  const openTradingView = (symbol: string) => {
    const cleanSymbol = symbol.replace('USDT', '');
    const url = `https://www.tradingview.com/chart/?symbol=BYBIT:${cleanSymbol}USDT.P&interval=1`;
    window.open(url, '_blank');
  };

  const getSocialRatingBadge = (symbol: string) => {
    const rating = socialRatings[symbol];
    if (!rating) return null;

    return (
      <div className="flex items-center space-x-1 text-xs">
        <span className="text-lg">{rating.rating_emoji}</span>
        <span className={`font-medium ${
          rating.overall_score > 0 ? 'text-green-600' : 
          rating.overall_score < 0 ? 'text-red-600' : 'text-gray-600'
        }`}>
          {rating.overall_score > 0 ? '+' : ''}{rating.overall_score.toFixed(0)}
        </span>
        <span className="text-gray-500">({rating.mention_count})</span>
        <span className="text-sm">{rating.trend_emoji}</span>
      </div>
    );
  };

  const renderAlertCard = (alert: Alert) => (
    <div 
      key={alert.id} 
      className="bg-white rounded-lg shadow-md border-l-4 border-blue-500 p-4 hover:shadow-lg transition-shadow cursor-pointer"
      onClick={() => setSelectedAlert(alert)}
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center space-x-3">
          <div className="flex items-center space-x-2">
            <span className="font-bold text-lg text-gray-900">{alert.symbol}</span>
            {getSocialRatingBadge(alert.symbol)}
          </div>
          <span className={`px-2 py-1 rounded-full text-xs font-medium ${
            alert.alert_type === 'volume_spike' ? 'bg-orange-100 text-orange-800' :
            alert.alert_type === 'consecutive_long' ? 'bg-green-100 text-green-800' :
            alert.alert_type === 'priority' ? 'bg-purple-100 text-purple-800' :
            'bg-gray-100 text-gray-800'
          }`}>
            {alert.alert_type === 'volume_spike' ? 'Объем' :
             alert.alert_type === 'consecutive_long' ? 'Последовательность' :
             alert.alert_type === 'priority' ? 'Приоритет' : alert.alert_type}
          </span>
          {alert.has_imbalance && (
            <span className="px-2 py-1 rounded-full text-xs font-medium bg-purple-100 text-purple-800">
              🧠 Smart Money
            </span>
          )}
        </div>
        
        <div className="flex items-center space-x-2">
          <button
            onClick={(e) => {
              e.stopPropagation();
              openTradingView(alert.symbol);
            }}
            className="text-blue-600 hover:text-blue-800 p-1"
            title="Открыть в TradingView"
          >
            <ExternalLink className="w-4 h-4" />
          </button>
        </div>
      </div>
      
      <div className="grid grid-cols-2 gap-4 text-sm mb-3">
        <div>
          <span className="text-gray-600">Цена:</span>
          <div className="font-mono text-gray-900">${alert.price.toFixed(8)}</div>
        </div>
        <div>
          <span className="text-gray-600">Время:</span>
          <div className="text-gray-900">
            {formatTime(alert.close_timestamp || alert.timestamp, timeZone)}
          </div>
        </div>
        
        {alert.volume_ratio && (
          <div>
            <span className="text-gray-600">Превышение:</span>
            <div className="font-semibold text-orange-600">{alert.volume_ratio}x</div>
          </div>
        )}
        
        {alert.consecutive_count && (
          <div>
            <span className="text-gray-600">LONG свечей:</span>
            <div className="font-semibold text-green-600">{alert.consecutive_count}</div>
          </div>
        )}
        
        {alert.current_volume_usdt && (
          <div>
            <span className="text-gray-600">Объем:</span>
            <div className="text-gray-900">${alert.current_volume_usdt.toLocaleString()}</div>
          </div>
        )}
      </div>

      {/* Социальный рейтинг */}
      {socialRatings[alert.symbol] && (
        <div className="mt-3 p-3 bg-gray-50 rounded-lg">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-gray-700">Социальные настроения</span>
            <div className="flex items-center space-x-2">
              <span className="text-lg">{socialRatings[alert.symbol].rating_emoji}</span>
              <span className={`text-sm font-medium ${
                socialRatings[alert.symbol].overall_score > 0 ? 'text-green-600' : 
                socialRatings[alert.symbol].overall_score < 0 ? 'text-red-600' : 'text-gray-600'
              }`}>
                {socialRatings[alert.symbol].overall_score > 0 ? '+' : ''}
                {socialRatings[alert.symbol].overall_score.toFixed(0)}/100
              </span>
            </div>
          </div>
          
          <div className="grid grid-cols-3 gap-2 text-xs">
            <div className="flex items-center space-x-1">
              <ThumbsUp className="w-3 h-3 text-green-500" />
              <span>{socialRatings[alert.symbol].positive_mentions}</span>
            </div>
            <div className="flex items-center space-x-1">
              <ThumbsDown className="w-3 h-3 text-red-500" />
              <span>{socialRatings[alert.symbol].negative_mentions}</span>
            </div>
            <div className="flex items-center space-x-1">
              <Minus className="w-3 h-3 text-gray-500" />
              <span>{socialRatings[alert.symbol].neutral_mentions}</span>
            </div>
          </div>
          
          {socialRatings[alert.symbol].top_mentions.length > 0 && (
            <div className="mt-2">
              <div className="text-xs text-gray-600 mb-1">Последние упоминания:</div>
              {socialRatings[alert.symbol].top_mentions.slice(0, 2).map((mention, idx) => (
                <div key={idx} className="text-xs text-gray-700 bg-white p-2 rounded mb-1">
                  <div className="flex items-center space-x-2 mb-1">
                    <span className="font-medium">{mention.platform}</span>
                    <span className="text-gray-500">@{mention.author}</span>
                    <div className="flex items-center space-x-1">
                      <MessageCircle className="w-3 h-3" />
                      <span>{mention.engagement}</span>
                    </div>
                  </div>
                  <div className="text-gray-800">{mention.text}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
      
      {alert.message && (
        <div className="mt-3 text-sm text-gray-700 bg-blue-50 p-2 rounded">
          {alert.message}
        </div>
      )}
    </div>
  );

  const renderFavoriteCard = (favorite: FavoriteItem) => (
    <div 
      key={favorite.id}
      className="bg-white rounded-lg shadow-md border-l-4 p-4 hover:shadow-lg transition-shadow cursor-pointer"
      style={{ borderLeftColor: favorite.color || '#FFD700' }}
      onClick={() => setSelectedAlert({
        id: favorite.id,
        symbol: favorite.symbol,
        alert_type: 'favorite',
        price: favorite.current_price || 0,
        timestamp: favorite.favorite_added_at || new Date().toISOString()
      } as Alert)}
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center space-x-3">
          <div className="flex items-center space-x-2">
            <Heart className="w-4 h-4 text-yellow-500 fill-yellow-500" />
            <span className="font-bold text-lg text-gray-900">{favorite.symbol}</span>
            {getSocialRatingBadge(favorite.symbol)}
          </div>
          <div className={`w-3 h-3 rounded-full ${favorite.is_active ? 'bg-green-500' : 'bg-red-500'}`}></div>
        </div>
        
        <button
          onClick={(e) => {
            e.stopPropagation();
            openTradingView(favorite.symbol);
          }}
          className="text-blue-600 hover:text-blue-800 p-1"
          title="Открыть в TradingView"
        >
          <ExternalLink className="w-4 h-4" />
        </button>
      </div>
      
      <div className="grid grid-cols-2 gap-4 text-sm mb-3">
        {favorite.current_price && (
          <div>
            <span className="text-gray-600">Текущая цена:</span>
            <div className="font-mono text-gray-900">${favorite.current_price.toFixed(8)}</div>
          </div>
        )}
        
        {favorite.price_drop_percentage && (
          <div>
            <span className="text-gray-600">Падение цены:</span>
            <div className="font-semibold text-red-600">{favorite.price_drop_percentage.toFixed(2)}%</div>
          </div>
        )}
      </div>

      {/* Социальный рейтинг для избранных */}
      {socialRatings[favorite.symbol] && (
        <div className="mt-3 p-3 bg-gray-50 rounded-lg">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-gray-700">Социальные настроения</span>
            <div className="flex items-center space-x-2">
              <span className="text-lg">{socialRatings[favorite.symbol].rating_emoji}</span>
              <span className={`text-sm font-medium ${
                socialRatings[favorite.symbol].overall_score > 0 ? 'text-green-600' : 
                socialRatings[favorite.symbol].overall_score < 0 ? 'text-red-600' : 'text-gray-600'
              }`}>
                {socialRatings[favorite.symbol].overall_score > 0 ? '+' : ''}
                {socialRatings[favorite.symbol].overall_score.toFixed(0)}/100
              </span>
              <span className="text-xs text-gray-500">
                ({socialRatings[favorite.symbol].mention_count} упоминаний)
              </span>
            </div>
          </div>
          
          <div className="flex items-center justify-between text-xs">
            <div className="flex items-center space-x-3">
              <div className="flex items-center space-x-1">
                <ThumbsUp className="w-3 h-3 text-green-500" />
                <span>{socialRatings[favorite.symbol].positive_mentions}</span>
              </div>
              <div className="flex items-center space-x-1">
                <ThumbsDown className="w-3 h-3 text-red-500" />
                <span>{socialRatings[favorite.symbol].negative_mentions}</span>
              </div>
              <div className="flex items-center space-x-1">
                <Minus className="w-3 h-3 text-gray-500" />
                <span>{socialRatings[favorite.symbol].neutral_mentions}</span>
              </div>
            </div>
            <div className="flex items-center space-x-1">
              <span>Тренд:</span>
              <span className="text-sm">{socialRatings[favorite.symbol].trend_emoji}</span>
            </div>
          </div>
        </div>
      )}
      
      {favorite.notes && (
        <div className="mt-3 text-sm text-gray-700 bg-blue-50 p-2 rounded">
          {favorite.notes}
        </div>
      )}
    </div>
  );

  // Запрашиваем разрешение на уведомления
  useEffect(() => {
    if (Notification.permission === 'default') {
      Notification.requestPermission();
    }
  }, []);

  return (
    <div className="min-h-screen bg-gray-100">
      {/* Header */}
      <header className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center space-x-4">
              <BarChart3 className="w-8 h-8 text-blue-600" />
              <h1 className="text-xl font-bold text-gray-900">Анализатор Объемов</h1>
              
              <div className="flex items-center space-x-2">
                {connectionStatus === 'connected' ? (
                  <Wifi className="w-5 h-5 text-green-500" />
                ) : (
                  <WifiOff className="w-5 h-5 text-red-500" />
                )}
                <span className="text-sm text-gray-600">
                  {connectionStatus === 'connected' ? 'Подключено' : 
                   connectionStatus === 'connecting' ? 'Подключение...' : 'Отключено'}
                </span>
              </div>
            </div>
            
            <div className="flex items-center space-x-4">
              <TimeZoneToggle />
              
              <button
                onClick={() => setShowStreamData(true)}
                className="flex items-center space-x-2 text-gray-600 hover:text-gray-900"
              >
                <Activity className="w-5 h-5" />
                <span>Поток данных</span>
              </button>
              
              <button
                onClick={() => setShowFavorites(true)}
                className="flex items-center space-x-2 text-gray-600 hover:text-gray-900"
              >
                <Heart className="w-5 h-5" />
                <span>Избранное ({favorites.length})</span>
              </button>
              
              <button
                onClick={() => setShowWatchlist(true)}
                className="flex items-center space-x-2 text-gray-600 hover:text-gray-900"
              >
                <List className="w-5 h-5" />
                <span>Пары ({watchlist.length})</span>
              </button>
              
              <button
                onClick={() => setShowSettings(true)}
                className="flex items-center space-x-2 text-gray-600 hover:text-gray-900"
              >
                <Settings className="w-5 h-5" />
                <span>Настройки</span>
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Stats */}
      {stats && (
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center">
                <div className="flex-shrink-0">
                  <List className="w-8 h-8 text-blue-600" />
                </div>
                <div className="ml-4">
                  <p className="text-sm font-medium text-gray-600">Торговых пар</p>
                  <p className="text-2xl font-bold text-gray-900">{stats.pairs_count}</p>
                </div>
              </div>
            </div>
            
            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center">
                <div className="flex-shrink-0">
                  <TrendingUp className="w-8 h-8 text-green-600" />
                </div>
                <div className="ml-4">
                  <p className="text-sm font-medium text-gray-600">Всего алертов</p>
                  <p className="text-2xl font-bold text-gray-900">{stats.alerts_count}</p>
                </div>
              </div>
            </div>
            
            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center">
                <div className="flex-shrink-0">
                  <Heart className="w-8 h-8 text-yellow-600" />
                </div>
                <div className="ml-4">
                  <p className="text-sm font-medium text-gray-600">Избранных</p>
                  <p className="text-2xl font-bold text-gray-900">{stats.favorites_count}</p>
                </div>
              </div>
            </div>
            
            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center">
                <div className="flex-shrink-0">
                  <MessageCircle className="w-8 h-8 text-purple-600" />
                </div>
                <div className="ml-4">
                  <p className="text-sm font-medium text-gray-600">Социальных упоминаний</p>
                  <p className="text-2xl font-bold text-gray-900">
                    {Object.values(socialRatings).reduce((sum, rating) => sum + rating.mention_count, 0)}
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="border-b border-gray-200">
          <nav className="flex space-x-8">
            {[
              { id: 'volume', label: 'Объем', count: alerts.volume_alerts.length, icon: TrendingUp },
              { id: 'consecutive', label: 'Последовательность', count: alerts.consecutive_alerts.length, icon: BarChart3 },
              { id: 'priority', label: 'Приоритет', count: alerts.priority_alerts.length, icon: Star },
              { id: 'favorites', label: 'Избранное', count: favorites.length, icon: Heart }
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={`flex items-center space-x-2 py-4 px-1 border-b-2 font-medium text-sm transition-colors ${
                  activeTab === tab.id
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                <tab.icon className="w-4 h-4" />
                <span>{tab.label}</span>
                <span className="bg-gray-100 text-gray-600 px-2 py-1 rounded-full text-xs">
                  {tab.count}
                </span>
              </button>
            ))}
          </nav>
        </div>
      </div>

      {/* Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {activeTab === 'volume' && (
          <div>
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-2xl font-bold text-gray-900">Алерты по объему</h2>
              <button
                onClick={() => clearAlerts('volume_spike')}
                className="text-red-600 hover:text-red-800 text-sm"
              >
                Очистить все
              </button>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {alerts.volume_alerts.map(renderAlertCard)}
            </div>
            
            {alerts.volume_alerts.length === 0 && (
              <div className="text-center py-12 text-gray-500">
                <TrendingUp className="w-12 h-12 mx-auto mb-4 text-gray-300" />
                <p>Нет алертов по объему</p>
              </div>
            )}
          </div>
        )}

        {activeTab === 'consecutive' && (
          <div>
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-2xl font-bold text-gray-900">Алерты по последовательности</h2>
              <button
                onClick={() => clearAlerts('consecutive_long')}
                className="text-red-600 hover:text-red-800 text-sm"
              >
                Очистить все
              </button>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {alerts.consecutive_alerts.map(renderAlertCard)}
            </div>
            
            {alerts.consecutive_alerts.length === 0 && (
              <div className="text-center py-12 text-gray-500">
                <BarChart3 className="w-12 h-12 mx-auto mb-4 text-gray-300" />
                <p>Нет алертов по последовательности</p>
              </div>
            )}
          </div>
        )}

        {activeTab === 'priority' && (
          <div>
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-2xl font-bold text-gray-900">Приоритетные алерты</h2>
              <button
                onClick={() => clearAlerts('priority')}
                className="text-red-600 hover:text-red-800 text-sm"
              >
                Очистить все
              </button>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {alerts.priority_alerts.map(renderAlertCard)}
            </div>
            
            {alerts.priority_alerts.length === 0 && (
              <div className="text-center py-12 text-gray-500">
                <Star className="w-12 h-12 mx-auto mb-4 text-gray-300" />
                <p>Нет приоритетных алертов</p>
              </div>
            )}
          </div>
        )}

        {activeTab === 'favorites' && (
          <div>
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-2xl font-bold text-gray-900">Избранные торговые пары</h2>
              <button
                onClick={() => setShowFavorites(true)}
                className="text-blue-600 hover:text-blue-800 text-sm"
              >
                Управление избранным
              </button>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {favorites.map(renderFavoriteCard)}
            </div>
            
            {favorites.length === 0 && (
              <div className="text-center py-12 text-gray-500">
                <Heart className="w-12 h-12 mx-auto mb-4 text-gray-300" />
                <p>Нет избранных торговых пар</p>
                <button
                  onClick={() => setShowWatchlist(true)}
                  className="mt-4 text-blue-600 hover:text-blue-800"
                >
                  Добавить из списка торговых пар
                </button>
              </div>
            )}
          </div>
        )}
      </main>

      {/* Modals */}
      {showSettings && (
        <SettingsModal
          settings={settings}
          onClose={() => setShowSettings(false)}
          onSave={handleSaveSettings}
        />
      )}

      {showWatchlist && (
        <WatchlistModal
          watchlist={watchlist}
          onClose={() => setShowWatchlist(false)}
          onUpdate={() => {
            loadWatchlist();
            loadFavorites();
          }}
          onToggleFavorite={handleToggleFavorite}
        />
      )}

      {showFavorites && (
        <FavoritesModal
          favorites={favorites}
          onClose={() => setShowFavorites(false)}
          onUpdate={() => {
            loadFavorites();
            loadWatchlist();
          }}
        />
      )}

      {selectedAlert && (
        <ChartSelector
          alert={selectedAlert}
          onClose={() => setSelectedAlert(null)}
        />
      )}

      {showStreamData && (
        <StreamDataModal
          streamData={streamData}
          connectionStatus={connectionStatus}
          onClose={() => setShowStreamData(false)}
        />
      )}
    </div>
  );
}

export default App;