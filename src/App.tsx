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
  Minus,
  DollarSign,
  Shield,
  Calculator,
  Brain,
  Zap
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
      <div className="flex items-center space-x-1 text-xs bg-gray-100 rounded-full px-2 py-1">
        <span className="text-sm">{rating.rating_emoji}</span>
        <span className={`font-medium ${
          rating.overall_score > 0 ? 'text-green-600' : 
          rating.overall_score < 0 ? 'text-red-600' : 'text-gray-600'
        }`}>
          {rating.overall_score > 0 ? '+' : ''}{rating.overall_score.toFixed(0)}
        </span>
        <span className="text-gray-500">({rating.mention_count})</span>
      </div>
    );
  };

  const renderAlertCard = (alert: Alert) => (
    <div 
      key={alert.id} 
      className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 hover:shadow-md transition-all duration-200 cursor-pointer group"
      onClick={() => setSelectedAlert(alert)}
    >
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center space-x-3">
          <div className="flex items-center space-x-2">
            <span className="font-bold text-xl text-gray-900">{alert.symbol}</span>
            <span className={`px-3 py-1 rounded-full text-xs font-medium ${
              alert.alert_type === 'volume_spike' ? 'bg-orange-100 text-orange-700' :
              alert.alert_type === 'consecutive_long' ? 'bg-green-100 text-green-700' :
              alert.alert_type === 'priority' ? 'bg-purple-100 text-purple-700' :
              'bg-gray-100 text-gray-700'
            }`}>
              {alert.alert_type === 'volume_spike' ? 'Объем' :
               alert.alert_type === 'consecutive_long' ? 'Последовательность' :
               alert.alert_type === 'priority' ? 'Приоритет' : alert.alert_type}
            </span>
          </div>
        </div>
        
        <div className="flex items-center space-x-2">
          {alert.has_imbalance && (
            <div className="flex items-center space-x-1 bg-purple-100 text-purple-700 px-2 py-1 rounded-full text-xs">
              <Brain className="w-3 h-3" />
              <span>Smart Money</span>
            </div>
          )}
          <button
            onClick={(e) => {
              e.stopPropagation();
              openTradingView(alert.symbol);
            }}
            className="text-blue-600 hover:text-blue-800 p-2 rounded-lg hover:bg-blue-50 transition-colors"
            title="Открыть в TradingView"
          >
            <ExternalLink className="w-4 h-4" />
          </button>
        </div>
      </div>
      
      <div className="grid grid-cols-2 gap-4 mb-4">
        <div className="bg-gray-50 rounded-lg p-3">
          <span className="text-sm text-gray-600 block mb-1">Цена</span>
          <div className="font-mono text-lg font-semibold text-gray-900">${alert.price.toFixed(8)}</div>
        </div>
        <div className="bg-gray-50 rounded-lg p-3">
          <span className="text-sm text-gray-600 block mb-1">Время</span>
          <div className="text-sm text-gray-900">
            {formatTime(alert.close_timestamp || alert.timestamp, timeZone)}
          </div>
        </div>
        
        {alert.volume_ratio && (
          <div className="bg-orange-50 rounded-lg p-3">
            <span className="text-sm text-orange-600 block mb-1">Превышение</span>
            <div className="font-semibold text-lg text-orange-700">{alert.volume_ratio}x</div>
          </div>
        )}
        
        {alert.consecutive_count && (
          <div className="bg-green-50 rounded-lg p-3">
            <span className="text-sm text-green-600 block mb-1">LONG свечей</span>
            <div className="font-semibold text-lg text-green-700">{alert.consecutive_count}</div>
          </div>
        )}
      </div>

      {/* Социальный рейтинг */}
      {socialRatings[alert.symbol] && (
        <div className="mt-4 p-4 bg-gradient-to-r from-blue-50 to-purple-50 rounded-lg border border-blue-100">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center space-x-2">
              <MessageCircle className="w-4 h-4 text-blue-600" />
              <span className="text-sm font-medium text-blue-900">Социальные настроения</span>
            </div>
            <div className="flex items-center space-x-2">
              <span className="text-lg">{socialRatings[alert.symbol].rating_emoji}</span>
              <span className={`text-sm font-bold ${
                socialRatings[alert.symbol].overall_score > 0 ? 'text-green-600' : 
                socialRatings[alert.symbol].overall_score < 0 ? 'text-red-600' : 'text-gray-600'
              }`}>
                {socialRatings[alert.symbol].overall_score > 0 ? '+' : ''}
                {socialRatings[alert.symbol].overall_score.toFixed(0)}/100
              </span>
            </div>
          </div>
          
          <div className="grid grid-cols-3 gap-3 text-xs">
            <div className="flex items-center space-x-1 bg-white rounded-lg p-2">
              <ThumbsUp className="w-3 h-3 text-green-500" />
              <span className="font-medium">{socialRatings[alert.symbol].positive_mentions}</span>
            </div>
            <div className="flex items-center space-x-1 bg-white rounded-lg p-2">
              <ThumbsDown className="w-3 h-3 text-red-500" />
              <span className="font-medium">{socialRatings[alert.symbol].negative_mentions}</span>
            </div>
            <div className="flex items-center space-x-1 bg-white rounded-lg p-2">
              <Minus className="w-3 h-3 text-gray-500" />
              <span className="font-medium">{socialRatings[alert.symbol].neutral_mentions}</span>
            </div>
          </div>
        </div>
      )}
      
      {alert.message && (
        <div className="mt-4 text-sm text-blue-700 bg-blue-50 p-3 rounded-lg border border-blue-200">
          {alert.message}
        </div>
      )}
    </div>
  );

  const renderFavoriteCard = (favorite: FavoriteItem) => (
    <div 
      key={favorite.id}
      className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 hover:shadow-md transition-all duration-200 cursor-pointer group"
      onClick={() => setSelectedAlert({
        id: favorite.id,
        symbol: favorite.symbol,
        alert_type: 'favorite',
        price: favorite.current_price || 0,
        timestamp: favorite.favorite_added_at || new Date().toISOString()
      } as Alert)}
    >
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center space-x-3">
          <div className="flex items-center space-x-2">
            <Heart className="w-5 h-5 text-yellow-500 fill-yellow-500" />
            <span className="font-bold text-xl text-gray-900">{favorite.symbol}</span>
            <div className={`w-3 h-3 rounded-full ${favorite.is_active ? 'bg-green-500' : 'bg-red-500'}`}></div>
          </div>
        </div>
        
        <button
          onClick={(e) => {
            e.stopPropagation();
            openTradingView(favorite.symbol);
          }}
          className="text-blue-600 hover:text-blue-800 p-2 rounded-lg hover:bg-blue-50 transition-colors"
          title="Открыть в TradingView"
        >
          <ExternalLink className="w-4 h-4" />
        </button>
      </div>
      
      <div className="grid grid-cols-2 gap-4 mb-4">
        {favorite.current_price && (
          <div className="bg-gray-50 rounded-lg p-3">
            <span className="text-sm text-gray-600 block mb-1">Текущая цена</span>
            <div className="font-mono text-lg font-semibold text-gray-900">${favorite.current_price.toFixed(8)}</div>
          </div>
        )}
        
        {favorite.price_drop_percentage && (
          <div className="bg-red-50 rounded-lg p-3">
            <span className="text-sm text-red-600 block mb-1">Падение цены</span>
            <div className="font-semibold text-lg text-red-700">{favorite.price_drop_percentage.toFixed(2)}%</div>
          </div>
        )}
      </div>

      {/* Социальный рейтинг для избранных */}
      {socialRatings[favorite.symbol] && (
        <div className="mt-4 p-4 bg-gradient-to-r from-yellow-50 to-orange-50 rounded-lg border border-yellow-200">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center space-x-2">
              <MessageCircle className="w-4 h-4 text-yellow-600" />
              <span className="text-sm font-medium text-yellow-900">Социальные настроения</span>
            </div>
            <div className="flex items-center space-x-2">
              <span className="text-lg">{socialRatings[favorite.symbol].rating_emoji}</span>
              <span className={`text-sm font-bold ${
                socialRatings[favorite.symbol].overall_score > 0 ? 'text-green-600' : 
                socialRatings[favorite.symbol].overall_score < 0 ? 'text-red-600' : 'text-gray-600'
              }`}>
                {socialRatings[favorite.symbol].overall_score > 0 ? '+' : ''}
                {socialRatings[favorite.symbol].overall_score.toFixed(0)}/100
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
        <div className="mt-4 text-sm text-gray-700 bg-gray-50 p-3 rounded-lg border border-gray-200">
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
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100">
      {/* Header */}
      <header className="bg-white/80 backdrop-blur-md shadow-sm border-b border-gray-200 sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center space-x-4">
              <div className="flex items-center space-x-3">
                <div className="p-2 bg-gradient-to-r from-blue-600 to-purple-600 rounded-lg">
                  <BarChart3 className="w-6 h-6 text-white" />
                </div>
                <div>
                  <h1 className="text-xl font-bold text-gray-900">Анализатор Объемов</h1>
                  <p className="text-xs text-gray-500">Профессиональная торговая система</p>
                </div>
              </div>
              
              <div className="flex items-center space-x-2 bg-gray-100 rounded-full px-3 py-1">
                {connectionStatus === 'connected' ? (
                  <Wifi className="w-4 h-4 text-green-500" />
                ) : (
                  <WifiOff className="w-4 h-4 text-red-500" />
                )}
                <span className="text-sm text-gray-600">
                  {connectionStatus === 'connected' ? 'Подключено' : 
                   connectionStatus === 'connecting' ? 'Подключение...' : 'Отключено'}
                </span>
              </div>
            </div>
            
            <div className="flex items-center space-x-2">
              <TimeZoneToggle />
              
              <button
                onClick={() => setShowStreamData(true)}
                className="flex items-center space-x-2 text-gray-600 hover:text-gray-900 px-3 py-2 rounded-lg hover:bg-gray-100 transition-colors"
              >
                <Activity className="w-4 h-4" />
                <span className="hidden sm:inline">Поток</span>
              </button>
              
              <button
                onClick={() => setShowFavorites(true)}
                className="flex items-center space-x-2 text-gray-600 hover:text-gray-900 px-3 py-2 rounded-lg hover:bg-gray-100 transition-colors"
              >
                <Heart className="w-4 h-4" />
                <span className="hidden sm:inline">Избранное</span>
                <span className="bg-yellow-100 text-yellow-800 px-2 py-1 rounded-full text-xs">
                  {favorites.length}
                </span>
              </button>
              
              <button
                onClick={() => setShowWatchlist(true)}
                className="flex items-center space-x-2 text-gray-600 hover:text-gray-900 px-3 py-2 rounded-lg hover:bg-gray-100 transition-colors"
              >
                <List className="w-4 h-4" />
                <span className="hidden sm:inline">Пары</span>
                <span className="bg-blue-100 text-blue-800 px-2 py-1 rounded-full text-xs">
                  {watchlist.length}
                </span>
              </button>
              
              <button
                onClick={() => setShowSettings(true)}
                className="flex items-center space-x-2 text-gray-600 hover:text-gray-900 px-3 py-2 rounded-lg hover:bg-gray-100 transition-colors"
              >
                <Settings className="w-4 h-4" />
                <span className="hidden sm:inline">Настройки</span>
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Stats */}
      {stats && (
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <div className="bg-white/70 backdrop-blur-sm rounded-xl shadow-sm border border-gray-200 p-6">
              <div className="flex items-center">
                <div className="flex-shrink-0">
                  <div className="p-3 bg-blue-100 rounded-lg">
                    <List className="w-6 h-6 text-blue-600" />
                  </div>
                </div>
                <div className="ml-4">
                  <p className="text-sm font-medium text-gray-600">Торговых пар</p>
                  <p className="text-2xl font-bold text-gray-900">{stats.pairs_count}</p>
                </div>
              </div>
            </div>
            
            <div className="bg-white/70 backdrop-blur-sm rounded-xl shadow-sm border border-gray-200 p-6">
              <div className="flex items-center">
                <div className="flex-shrink-0">
                  <div className="p-3 bg-green-100 rounded-lg">
                    <Zap className="w-6 h-6 text-green-600" />
                  </div>
                </div>
                <div className="ml-4">
                  <p className="text-sm font-medium text-gray-600">Всего алертов</p>
                  <p className="text-2xl font-bold text-gray-900">{stats.alerts_count}</p>
                </div>
              </div>
            </div>
            
            <div className="bg-white/70 backdrop-blur-sm rounded-xl shadow-sm border border-gray-200 p-6">
              <div className="flex items-center">
                <div className="flex-shrink-0">
                  <div className="p-3 bg-yellow-100 rounded-lg">
                    <Heart className="w-6 h-6 text-yellow-600" />
                  </div>
                </div>
                <div className="ml-4">
                  <p className="text-sm font-medium text-gray-600">Избранных</p>
                  <p className="text-2xl font-bold text-gray-900">{stats.favorites_count}</p>
                </div>
              </div>
            </div>
            
            <div className="bg-white/70 backdrop-blur-sm rounded-xl shadow-sm border border-gray-200 p-6">
              <div className="flex items-center">
                <div className="flex-shrink-0">
                  <div className="p-3 bg-purple-100 rounded-lg">
                    <MessageCircle className="w-6 h-6 text-purple-600" />
                  </div>
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
        <div className="bg-white/70 backdrop-blur-sm rounded-xl shadow-sm border border-gray-200 p-2">
          <nav className="flex space-x-2">
            {[
              { id: 'volume', label: 'Объем', count: alerts.volume_alerts.length, icon: TrendingUp, color: 'orange' },
              { id: 'consecutive', label: 'Последовательность', count: alerts.consecutive_alerts.length, icon: BarChart3, color: 'green' },
              { id: 'priority', label: 'Приоритет', count: alerts.priority_alerts.length, icon: Star, color: 'purple' },
              { id: 'favorites', label: 'Избранное', count: favorites.length, icon: Heart, color: 'yellow' }
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={`flex items-center space-x-2 py-3 px-4 rounded-lg font-medium text-sm transition-all ${
                  activeTab === tab.id
                    ? tab.color === 'orange' ? 'bg-orange-100 text-orange-700 shadow-sm' :
                      tab.color === 'green' ? 'bg-green-100 text-green-700 shadow-sm' :
                      tab.color === 'purple' ? 'bg-purple-100 text-purple-700 shadow-sm' :
                      'bg-yellow-100 text-yellow-700 shadow-sm'
                    : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
                }`}
              >
                <tab.icon className="w-4 h-4" />
                <span>{tab.label}</span>
                <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                  activeTab === tab.id 
                    ? tab.color === 'orange' ? 'bg-orange-200 text-orange-800' :
                      tab.color === 'green' ? 'bg-green-200 text-green-800' :
                      tab.color === 'purple' ? 'bg-purple-200 text-purple-800' :
                      'bg-yellow-200 text-yellow-800'
                    : 'bg-gray-200 text-gray-600'
                }`}>
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
              <div>
                <h2 className="text-2xl font-bold text-gray-900">Алерты по объему</h2>
                <p className="text-gray-600">Сигналы о превышении торгового объема</p>
              </div>
              <button
                onClick={() => clearAlerts('volume_spike')}
                className="text-red-600 hover:text-red-800 text-sm bg-red-50 hover:bg-red-100 px-3 py-2 rounded-lg transition-colors"
              >
                Очистить все
              </button>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {alerts.volume_alerts.map(renderAlertCard)}
            </div>
            
            {alerts.volume_alerts.length === 0 && (
              <div className="text-center py-16">
                <div className="p-4 bg-orange-100 rounded-full w-16 h-16 mx-auto mb-4 flex items-center justify-center">
                  <TrendingUp className="w-8 h-8 text-orange-600" />
                </div>
                <h3 className="text-lg font-medium text-gray-900 mb-2">Нет алертов по объему</h3>
                <p className="text-gray-500">Алерты появятся при превышении объема торгов</p>
              </div>
            )}
          </div>
        )}

        {activeTab === 'consecutive' && (
          <div>
            <div className="flex items-center justify-between mb-6">
              <div>
                <h2 className="text-2xl font-bold text-gray-900">Алерты по последовательности</h2>
                <p className="text-gray-600">Сигналы о подряд идущих LONG свечах</p>
              </div>
              <button
                onClick={() => clearAlerts('consecutive_long')}
                className="text-red-600 hover:text-red-800 text-sm bg-red-50 hover:bg-red-100 px-3 py-2 rounded-lg transition-colors"
              >
                Очистить все
              </button>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {alerts.consecutive_alerts.map(renderAlertCard)}
            </div>
            
            {alerts.consecutive_alerts.length === 0 && (
              <div className="text-center py-16">
                <div className="p-4 bg-green-100 rounded-full w-16 h-16 mx-auto mb-4 flex items-center justify-center">
                  <BarChart3 className="w-8 h-8 text-green-600" />
                </div>
                <h3 className="text-lg font-medium text-gray-900 mb-2">Нет алертов по последовательности</h3>
                <p className="text-gray-500">Алерты появятся при формировании последовательных LONG свечей</p>
              </div>
            )}
          </div>
        )}

        {activeTab === 'priority' && (
          <div>
            <div className="flex items-center justify-between mb-6">
              <div>
                <h2 className="text-2xl font-bold text-gray-900">Приоритетные алерты</h2>
                <p className="text-gray-600">Комбинированные сигналы высокого приоритета</p>
              </div>
              <button
                onClick={() => clearAlerts('priority')}
                className="text-red-600 hover:text-red-800 text-sm bg-red-50 hover:bg-red-100 px-3 py-2 rounded-lg transition-colors"
              >
                Очистить все
              </button>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {alerts.priority_alerts.map(renderAlertCard)}
            </div>
            
            {alerts.priority_alerts.length === 0 && (
              <div className="text-center py-16">
                <div className="p-4 bg-purple-100 rounded-full w-16 h-16 mx-auto mb-4 flex items-center justify-center">
                  <Star className="w-8 h-8 text-purple-600" />
                </div>
                <h3 className="text-lg font-medium text-gray-900 mb-2">Нет приоритетных алертов</h3>
                <p className="text-gray-500">Приоритетные сигналы формируются при совпадении нескольких условий</p>
              </div>
            )}
          </div>
        )}

        {activeTab === 'favorites' && (
          <div>
            <div className="flex items-center justify-between mb-6">
              <div>
                <h2 className="text-2xl font-bold text-gray-900">Избранные торговые пары</h2>
                <p className="text-gray-600">Ваши отслеживаемые торговые инструменты</p>
              </div>
              <button
                onClick={() => setShowFavorites(true)}
                className="text-blue-600 hover:text-blue-800 text-sm bg-blue-50 hover:bg-blue-100 px-3 py-2 rounded-lg transition-colors"
              >
                Управление избранным
              </button>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {favorites.map(renderFavoriteCard)}
            </div>
            
            {favorites.length === 0 && (
              <div className="text-center py-16">
                <div className="p-4 bg-yellow-100 rounded-full w-16 h-16 mx-auto mb-4 flex items-center justify-center">
                  <Heart className="w-8 h-8 text-yellow-600" />
                </div>
                <h3 className="text-lg font-medium text-gray-900 mb-2">Нет избранных торговых пар</h3>
                <p className="text-gray-500 mb-4">Добавьте интересующие вас торговые пары в избранное</p>
                <button
                  onClick={() => setShowWatchlist(true)}
                  className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg transition-colors"
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