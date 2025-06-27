import React, { useState, useEffect } from 'react';
import { 
  TrendingUp, 
  BarChart3, 
  Star, 
  List, 
  Wifi, 
  Settings, 
  ExternalLink,
  Brain,
  RefreshCw,
  Clock
} from 'lucide-react';
import ChartModal from './components/ChartModal';
import SmartMoneyChartModal from './components/SmartMoneyChartModal';
import WatchlistModal from './components/WatchlistModal';
import StreamDataModal from './components/StreamDataModal';
import SettingsModal from './components/SettingsModal';

interface Alert {
  id: number;
  symbol: string;
  alert_type: string;
  price: number;
  volume_ratio?: number;
  consecutive_count?: number;
  current_volume_usdt?: number;
  average_volume_usdt?: number;
  is_true_signal?: boolean;
  is_closed: boolean;
  has_imbalance?: boolean;
  imbalance_data?: any;
  message: string;
  timestamp: string;
  close_timestamp?: string;
  candle_data?: any;
  preliminary_alert?: Alert;
  order_book_snapshot?: any;
}

interface WatchlistItem {
  id: number;
  symbol: string;
  is_active: boolean;
  price_drop_percentage?: number;
  current_price?: number;
  historical_price?: number;
  created_at: string;
  updated_at: string;
}

interface StreamData {
  symbol: string;
  price: number;
  volume: number;
  volume_usdt: number;
  is_long: boolean;
  timestamp: string;
}

interface SmartMoneyAlert {
  id: number;
  symbol: string;
  type: 'fair_value_gap' | 'order_block' | 'breaker_block';
  direction: 'bullish' | 'bearish';
  strength: number;
  price: number;
  timestamp: string;
  top?: number;
  bottom?: number;
  related_alert_id?: number;
}

interface TimeSync {
  is_synced: boolean;
  last_sync?: string;
  time_offset_ms: number;
  exchange_time: string;
  local_time: string;
  sync_age_seconds?: number;
}

interface Settings {
  volume_analyzer: {
    analysis_hours: number;
    volume_multiplier: number;
    min_volume_usdt: number;
    consecutive_long_count: number;
    alert_grouping_minutes: number;
    data_retention_hours: number;
    update_interval_seconds: number;
    notification_enabled: boolean;
  };
  alerts: {
    volume_alerts_enabled: boolean;
    consecutive_alerts_enabled: boolean;
    priority_alerts_enabled: boolean;
  };
  imbalance: {
    fair_value_gap_enabled: boolean;
    order_block_enabled: boolean;
    breaker_block_enabled: boolean;
    min_gap_percentage: number;
    min_strength: number;
  };
  orderbook: {
    enabled: boolean;
    snapshot_on_alert: boolean;
  };
  telegram: {
    enabled: boolean;
  };
  time_sync?: TimeSync;
}

const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'volume' | 'consecutive' | 'priority' | 'watchlist' | 'stream' | 'smart_money'>('volume');
  const [volumeAlerts, setVolumeAlerts] = useState<Alert[]>([]);
  const [consecutiveAlerts, setConsecutiveAlerts] = useState<Alert[]>([]);
  const [priorityAlerts, setPriorityAlerts] = useState<Alert[]>([]);
  const [smartMoneyAlerts, setSmartMoneyAlerts] = useState<SmartMoneyAlert[]>([]);
  const [watchlist, setWatchlist] = useState<WatchlistItem[]>([]);
  const [streamData, setStreamData] = useState<StreamData[]>([]);
  const [selectedAlert, setSelectedAlert] = useState<Alert | null>(null);
  const [selectedSmartMoneyAlert, setSelectedSmartMoneyAlert] = useState<SmartMoneyAlert | null>(null);
  const [showWatchlistModal, setShowWatchlistModal] = useState(false);
  const [showStreamModal, setShowStreamModal] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<'connecting' | 'connected' | 'disconnected'>('connecting');
  const [settings, setSettings] = useState<Settings | null>(null);
  const [loading, setLoading] = useState(true);
  const [currentTime, setCurrentTime] = useState<Date>(new Date());
  const [timeSync, setTimeSync] = useState<TimeSync | null>(null);

  useEffect(() => {
    loadInitialData();
    connectWebSocket();
    requestNotificationPermission();
    
    // Обновляем время каждую секунду
    const timeInterval = setInterval(() => {
      setCurrentTime(new Date());
    }, 1000);
    
    // Загружаем информацию о синхронизации времени каждые 30 секунд
    const syncInterval = setInterval(loadTimeSync, 30000);
    loadTimeSync(); // Первоначальная загрузка
    
    return () => {
      clearInterval(timeInterval);
      clearInterval(syncInterval);
    };
  }, []);

  const loadTimeSync = async () => {
    try {
      const response = await fetch('/api/time');
      if (response.ok) {
        const timeSyncData = await response.json();
        setTimeSync(timeSyncData);
      }
    } catch (error) {
      console.error('Ошибка загрузки информации о времени:', error);
    }
  };

  const requestNotificationPermission = async () => {
    if ('Notification' in window && Notification.permission === 'default') {
      await Notification.requestPermission();
    }
  };

  const showNotification = (alert: Alert) => {
    if (!settings?.volume_analyzer?.notification_enabled) return;
    if ('Notification' in window && Notification.permission === 'granted') {
      const title = `Алерт: ${alert.symbol}`;
      const body = alert.message;
      const notification = new Notification(title, {
        body,
        icon: '/favicon.ico',
        tag: `alert-${alert.id}`
      });
      
      notification.onclick = () => {
        window.focus();
        setSelectedAlert(alert);
        notification.close();
      };
      
      setTimeout(() => notification.close(), 10000);
    }
  };

  const loadInitialData = async () => {
    try {
      setLoading(true);
      
      // Загружаем алерты
      const alertsResponse = await fetch('/api/alerts/all');
      if (alertsResponse.ok) {
        const alertsData = await alertsResponse.json();
        // Сортируем по времени закрытия (новые сверху)
        setVolumeAlerts((alertsData.volume_alerts || []).sort((a: Alert, b: Alert) => 
          new Date(b.close_timestamp || b.timestamp).getTime() - new Date(a.close_timestamp || a.timestamp).getTime()
        ));
        setConsecutiveAlerts((alertsData.consecutive_alerts || []).sort((a: Alert, b: Alert) => 
          new Date(b.close_timestamp || b.timestamp).getTime() - new Date(a.close_timestamp || a.timestamp).getTime()
        ));
        setPriorityAlerts((alertsData.priority_alerts || []).sort((a: Alert, b: Alert) => 
          new Date(b.close_timestamp || b.timestamp).getTime() - new Date(a.close_timestamp || a.timestamp).getTime()
        ));
      }

      // Загружаем watchlist
      const watchlistResponse = await fetch('/api/watchlist');
      if (watchlistResponse.ok) {
        const watchlistData = await watchlistResponse.json();
        // Сортируем по проценту падения (больше сверху) и по алфавиту
        const sortedWatchlist = (watchlistData.pairs || []).sort((a: WatchlistItem, b: WatchlistItem) => {
          if (a.price_drop_percentage && b.price_drop_percentage) {
            if (a.price_drop_percentage !== b.price_drop_percentage) {
              return b.price_drop_percentage - a.price_drop_percentage;
            }
          }
          return a.symbol.localeCompare(b.symbol);
        });
        setWatchlist(sortedWatchlist);
      }

      // Загружаем настройки
      const settingsResponse = await fetch('/api/settings');
      if (settingsResponse.ok) {
        const settingsData = await settingsResponse.json();
        setSettings(settingsData);
        if (settingsData.time_sync) {
          setTimeSync(settingsData.time_sync);
        }
      }

    } catch (error) {
      console.error('Ошибка загрузки данных:', error);
    } finally {
      setLoading(false);
    }
  };

  const connectWebSocket = () => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;
    
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      setConnectionStatus('connected');
      console.log('WebSocket подключен');
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        handleWebSocketMessage(data);
      } catch (error) {
        console.error('Ошибка парсинга WebSocket сообщения:', error);
      }
    };

    ws.onclose = () => {
      setConnectionStatus('disconnected');
      console.log('WebSocket отключен, переподключение через 5 секунд...');
      setTimeout(connectWebSocket, 5000);
    };

    ws.onerror = (error) => {
      console.error('WebSocket ошибка:', error);
      setConnectionStatus('disconnected');
    };
  };

  const handleWebSocketMessage = (data: any) => {
    switch (data.type) {
      case 'new_alert':
        const alert = data.alert;
        
        // Показываем уведомление
        showNotification(alert);
        
        // Обновляем алерты без дублирования
        if (alert.alert_type === 'volume_spike') {
          setVolumeAlerts(prev => {
            const existing = prev.find(a => a.id === alert.id);
            if (existing) {
              // Обновляем существующий алерт
              const updated = prev.map(a => a.id === alert.id ? alert : a);
              return updated.sort((a, b) => 
                new Date(b.close_timestamp || b.timestamp).getTime() - new Date(a.close_timestamp || a.timestamp).getTime()
              );
            }
            // Добавляем новый алерт
            const newList = [alert, ...prev].slice(0, 100);
            return newList.sort((a, b) => 
              new Date(b.close_timestamp || b.timestamp).getTime() - new Date(a.close_timestamp || a.timestamp).getTime()
            );
          });
        } else if (alert.alert_type === 'consecutive_long') {
          setConsecutiveAlerts(prev => {
            const newList = [alert, ...prev].slice(0, 100);
            return newList.sort((a, b) => 
              new Date(b.close_timestamp || b.timestamp).getTime() - new Date(a.close_timestamp || a.timestamp).getTime()
            );
          });
        } else if (alert.alert_type === 'priority') {
          setPriorityAlerts(prev => {
            const newList = [alert, ...prev].slice(0, 100);
            return newList.sort((a, b) => 
              new Date(b.close_timestamp || b.timestamp).getTime() - new Date(a.close_timestamp || a.timestamp).getTime()
            );
          });
        }

        // Если есть имбаланс, добавляем в Smart Money алерты
        if (alert.has_imbalance && alert.imbalance_data) {
          const smartMoneyAlert: SmartMoneyAlert = {
            id: Date.now(),
            symbol: alert.symbol,
            type: alert.imbalance_data.type,
            direction: alert.imbalance_data.direction,
            strength: alert.imbalance_data.strength,
            price: alert.price,
            timestamp: alert.timestamp,
            top: alert.imbalance_data.top,
            bottom: alert.imbalance_data.bottom,
            related_alert_id: alert.id
          };
          setSmartMoneyAlerts(prev => [smartMoneyAlert, ...prev].slice(0, 50));
        }
        break;

      case 'kline_update':
        // Обновляем потоковые данные
        const streamItem: StreamData = {
          symbol: data.symbol,
          price: parseFloat(data.data.close),
          volume: parseFloat(data.data.volume),
          volume_usdt: parseFloat(data.data.volume) * parseFloat(data.data.close),
          is_long: parseFloat(data.data.close) > parseFloat(data.data.open),
          timestamp: data.timestamp
        };
        
        setStreamData(prev => {
          const filtered = prev.filter(item => item.symbol !== data.symbol);
          return [streamItem, ...filtered].slice(0, 100);
        });
        break;

      case 'connection_status':
        setConnectionStatus(data.status === 'connected' ? 'connected' : 'disconnected');
        break;

      case 'watchlist_updated':
        loadWatchlist();
        break;
    }
  };

  const loadWatchlist = async () => {
    try {
      const response = await fetch('/api/watchlist');
      if (response.ok) {
        const data = await response.json();
        // Сортируем по проценту падения и алфавиту
        const sortedWatchlist = (data.pairs || []).sort((a: WatchlistItem, b: WatchlistItem) => {
          if (a.price_drop_percentage && b.price_drop_percentage) {
            if (a.price_drop_percentage !== b.price_drop_percentage) {
              return b.price_drop_percentage - a.price_drop_percentage;
            }
          }
          return a.symbol.localeCompare(b.symbol);
        });
        setWatchlist(sortedWatchlist);
      }
    } catch (error) {
      console.error('Ошибка загрузки watchlist:', error);
    }
  };

  const clearAlerts = async (alertType: string) => {
    try {
      const response = await fetch(`/api/alerts/clear/${alertType}`, {
        method: 'DELETE'
      });
      
      if (response.ok) {
        if (alertType === 'volume_spike') {
          setVolumeAlerts([]);
        } else if (alertType === 'consecutive_long') {
          setConsecutiveAlerts([]);
        } else if (alertType === 'priority') {
          setPriorityAlerts([]);
        }
      }
    } catch (error) {
      console.error('Ошибка очистки алертов:', error);
    }
  };

  const openTradingView = (symbol: string) => {
    const cleanSymbol = symbol.replace('USDT', '');
    const url = `https://www.tradingview.com/chart/?symbol=BYBIT:${cleanSymbol}USDT.P&interval=1`;
    window.open(url, '_blank');
  };

  const handleSettingsSave = (newSettings: Settings) => {
    setSettings(newSettings);
  };

  const formatTime = (timestamp: string) => {
    return new Date(timestamp).toLocaleString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    });
  };

  const formatVolume = (volume: number) => {
    if (volume >= 1000000) {
      return `$${(volume / 1000000).toFixed(1)}M`;
    } else if (volume >= 1000) {
      return `$${(volume / 1000).toFixed(1)}K`;
    }
    return `$${volume.toFixed(0)}`;
  };

  const getAlertStatusBadge = (alert: Alert) => {
    if (!alert.is_closed) {
      return <span className="px-2 py-1 bg-yellow-100 text-yellow-800 text-xs rounded-full">В процессе</span>;
    }
    
    if (alert.is_true_signal === true) {
      return <span className="px-2 py-1 bg-green-100 text-green-800 text-xs rounded-full">Истинный</span>;
    } else if (alert.is_true_signal === false) {
      return <span className="px-2 py-1 bg-red-100 text-red-800 text-xs rounded-full">Ложный</span>;
    }
    
    return <span className="px-2 py-1 bg-gray-100 text-gray-800 text-xs rounded-full">Неизвестно</span>;
  };

  const getTimeSyncStatus = () => {
    if (!timeSync) return { color: 'text-gray-500', text: 'Нет данных' };
    
    if (!timeSync.is_synced) {
      return { color: 'text-red-500', text: 'Не синхронизировано' };
    }
    
    if (timeSync.sync_age_seconds && timeSync.sync_age_seconds > 600) { // 10 минут
      return { color: 'text-yellow-500', text: 'Устаревшая синхронизация' };
    }
    
    return { color: 'text-green-500', text: 'Синхронизировано' };
  };

  const renderAlertCard = (alert: Alert) => (
    <div 
      key={alert.id} 
      className="bg-white rounded-lg shadow-md border border-gray-200 p-4 hover:shadow-lg transition-shadow cursor-pointer w-full"
      onClick={() => setSelectedAlert(alert)}
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center space-x-3">
          <span className="font-bold text-lg text-gray-900">{alert.symbol}</span>
          {alert.has_imbalance && (
            <span className="text-orange-500 text-sm">⚠️ Имбаланс</span>
          )}
          {getAlertStatusBadge(alert)}
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

      <div className="grid grid-cols-2 gap-4 text-sm">
        <div>
          <span className="text-gray-600">Цена:</span>
          <div className="font-mono text-gray-900">${alert.price.toFixed(8)}</div>
        </div>
        
        {alert.volume_ratio && (
          <div>
            <span className="text-gray-600">Превышение:</span>
            <div className="font-semibold text-orange-600">{alert.volume_ratio}x</div>
          </div>
        )}
        
        {alert.current_volume_usdt && (
          <div>
            <span className="text-gray-600">Объем:</span>
            <div className="text-gray-900">{formatVolume(alert.current_volume_usdt)}</div>
          </div>
        )}
        
        {alert.consecutive_count && (
          <div>
            <span className="text-gray-600">LONG свечей:</span>
            <div className="font-semibold text-green-600">{alert.consecutive_count}</div>
          </div>
        )}
      </div>

      <div className="mt-3 pt-3 border-t border-gray-200">
        <div className="text-xs text-gray-500">
          <div>Время закрытия: {formatTime(alert.close_timestamp || alert.timestamp)}</div>
          {alert.preliminary_alert && (
            <div>Предварительный: {formatTime(alert.preliminary_alert.timestamp)}</div>
          )}
        </div>
      </div>
    </div>
  );

  const renderSmartMoneyCard = (alert: SmartMoneyAlert) => (
    <div 
      key={alert.id} 
      className="bg-white rounded-lg shadow-md border border-gray-200 p-4 hover:shadow-lg transition-shadow cursor-pointer w-full"
      onClick={() => setSelectedSmartMoneyAlert(alert)}
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center space-x-3">
          <span className="font-bold text-lg text-gray-900">{alert.symbol}</span>
          <span className={`px-2 py-1 text-xs rounded-full ${
            alert.direction === 'bullish' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
          }`}>
            {alert.direction === 'bullish' ? 'Бычий' : 'Медвежий'}
          </span>
        </div>
        
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

      <div className="grid grid-cols-2 gap-4 text-sm">
        <div>
          <span className="text-gray-600">Тип:</span>
          <div className="font-semibold text-gray-900">
            {alert.type === 'fair_value_gap' && 'Fair Value Gap'}
            {alert.type === 'order_block' && 'Order Block'}
            {alert.type === 'breaker_block' && 'Breaker Block'}
          </div>
        </div>
        
        <div>
          <span className="text-gray-600">Сила:</span>
          <div className="font-semibold text-purple-600">{alert.strength.toFixed(2)}%</div>
        </div>
        
        <div>
          <span className="text-gray-600">Цена:</span>
          <div className="font-mono text-gray-900">${alert.price.toFixed(8)}</div>
        </div>
        
        <div>
          <span className="text-gray-600">Время:</span>
          <div className="text-gray-900">{formatTime(alert.timestamp)}</div>
        </div>
      </div>

      {alert.top && alert.bottom && (
        <div className="mt-3 pt-3 border-t border-gray-200">
          <div className="grid grid-cols-2 gap-4 text-xs text-gray-500">
            <div>Верх: ${alert.top.toFixed(6)}</div>
            <div>Низ: ${alert.bottom.toFixed(6)}</div>
          </div>
        </div>
      )}
    </div>
  );

  const renderWatchlistCard = (item: WatchlistItem) => (
    <div key={item.id} className="bg-white rounded-lg shadow-md border border-gray-200 p-4 hover:shadow-lg transition-shadow w-full">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center space-x-3">
          <div className={`w-3 h-3 rounded-full ${item.is_active ? 'bg-green-500' : 'bg-red-500'}`}></div>
          <span className="font-bold text-lg text-gray-900">{item.symbol}</span>
        </div>
        
        <button
          onClick={() => openTradingView(item.symbol)}
          className="text-blue-600 hover:text-blue-800 p-1"
          title="Открыть в TradingView"
        >
          <ExternalLink className="w-4 h-4" />
        </button>
      </div>

      {item.price_drop_percentage && (
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <span className="text-gray-600">Падение цены:</span>
            <div className="font-semibold text-red-600">{item.price_drop_percentage.toFixed(2)}%</div>
          </div>
          
          {item.current_price && (
            <div>
              <span className="text-gray-600">Текущая цена:</span>
              <div className="font-mono text-gray-900">${item.current_price.toFixed(8)}</div>
            </div>
          )}
        </div>
      )}

      <div className="mt-3 pt-3 border-t border-gray-200 text-xs text-gray-500">
        Обновлено: {formatTime(item.updated_at)}
      </div>
    </div>
  );

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <RefreshCw className="w-8 h-8 animate-spin text-blue-600 mx-auto mb-4" />
          <p className="text-gray-600">Загрузка данных...</p>
        </div>
      </div>
    );
  }

  const timeSyncStatus = getTimeSyncStatus();

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center space-x-4">
              <h1 className="text-xl font-bold text-gray-900">Анализатор Объемов</h1>
              <div className="flex items-center space-x-2">
                <div className={`w-2 h-2 rounded-full ${
                  connectionStatus === 'connected' ? 'bg-green-500' : 
                  connectionStatus === 'connecting' ? 'bg-yellow-500' : 'bg-red-500'
                }`}></div>
                <span className="text-sm text-gray-600">
                  {connectionStatus === 'connected' ? 'Подключено' : 
                   connectionStatus === 'connecting' ? 'Подключение...' : 'Отключено'}
                </span>
              </div>
            </div>
            
            <div className="flex items-center space-x-6">
              {/* Часы с биржевым временем */}
              <div className="flex items-center space-x-3 bg-gray-100 rounded-lg px-4 py-2">
                <Clock className="w-5 h-5 text-gray-600" />
                <div className="text-center">
                  <div className="text-lg font-mono font-bold text-gray-900">
                    {timeSync && timeSync.is_synced 
                      ? new Date(timeSync.exchange_time).toLocaleTimeString('ru-RU')
                      : currentTime.toLocaleTimeString('ru-RU')
                    }
                  </div>
                  <div className={`text-xs ${timeSyncStatus.color}`}>
                    {timeSync && timeSync.is_synced ? 'Биржевое время' : 'Локальное время'}
                  </div>
                </div>
                <div className="text-xs text-gray-500">
                  <div className={timeSyncStatus.color}>
                    {timeSyncStatus.text}
                  </div>
                  {timeSync && timeSync.time_offset_ms !== 0 && (
                    <div>
                      {timeSync.time_offset_ms > 0 ? '+' : ''}{Math.round(timeSync.time_offset_ms)}мс
                    </div>
                  )}
                </div>
              </div>
              
              <button
                onClick={() => setShowSettings(true)}
                className="text-gray-600 hover:text-gray-900 p-2 rounded-lg hover:bg-gray-100 transition-colors"
                title="Настройки"
              >
                <Settings className="w-5 h-5" />
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Navigation Tabs */}
      <nav className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex space-x-8">
            {[
              { id: 'volume', label: 'Алерты по объему', icon: TrendingUp, count: volumeAlerts.length },
              { id: 'consecutive', label: 'LONG последовательности', icon: BarChart3, count: consecutiveAlerts.length },
              { id: 'priority', label: 'Приоритетные', icon: Star, count: priorityAlerts.length },
              { id: 'smart_money', label: 'Smart Money', icon: Brain, count: smartMoneyAlerts.length },
              { id: 'watchlist', label: 'Торговые пары', icon: List, count: watchlist.length },
              { id: 'stream', label: 'Потоковые данные', icon: Wifi, count: streamData.length }
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
                {tab.count > 0 && (
                  <span className="bg-gray-100 text-gray-900 py-0.5 px-2 rounded-full text-xs">
                    {tab.count}
                  </span>
                )}
              </button>
            ))}
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Volume Alerts */}
        {activeTab === 'volume' && (
          <div>
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-2xl font-bold text-gray-900">Алерты по объему</h2>
              <button
                onClick={() => clearAlerts('volume_spike')}
                className="bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded-lg transition-colors"
              >
                Очистить
              </button>
            </div>
            
            <div className="space-y-4">
              {volumeAlerts.length === 0 ? (
                <div className="text-center py-12 text-gray-500">
                  <TrendingUp className="w-12 h-12 mx-auto mb-4 text-gray-300" />
                  <p>Нет алертов по объему</p>
                </div>
              ) : (
                volumeAlerts.map(renderAlertCard)
              )}
            </div>
          </div>
        )}

        {/* Consecutive Alerts */}
        {activeTab === 'consecutive' && (
          <div>
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-2xl font-bold text-gray-900">LONG последовательности</h2>
              <button
                onClick={() => clearAlerts('consecutive_long')}
                className="bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded-lg transition-colors"
              >
                Очистить
              </button>
            </div>
            
            <div className="space-y-4">
              {consecutiveAlerts.length === 0 ? (
                <div className="text-center py-12 text-gray-500">
                  <BarChart3 className="w-12 h-12 mx-auto mb-4 text-gray-300" />
                  <p>Нет алертов по последовательностям</p>
                </div>
              ) : (
                consecutiveAlerts.map(renderAlertCard)
              )}
            </div>
          </div>
        )}

        {/* Priority Alerts */}
        {activeTab === 'priority' && (
          <div>
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-2xl font-bold text-gray-900">Приоритетные алерты</h2>
              <button
                onClick={() => clearAlerts('priority')}
                className="bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded-lg transition-colors"
              >
                Очистить
              </button>
            </div>
            
            <div className="space-y-4">
              {priorityAlerts.length === 0 ? (
                <div className="text-center py-12 text-gray-500">
                  <Star className="w-12 h-12 mx-auto mb-4 text-gray-300" />
                  <p>Нет приоритетных алертов</p>
                </div>
              ) : (
                priorityAlerts.map(renderAlertCard)
              )}
            </div>
          </div>
        )}

        {/* Smart Money Alerts */}
        {activeTab === 'smart_money' && (
          <div>
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-2xl font-bold text-gray-900">Smart Money Concepts</h2>
              <button
                onClick={() => setSmartMoneyAlerts([])}
                className="bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded-lg transition-colors"
              >
                Очистить
              </button>
            </div>
            
            <div className="space-y-4">
              {smartMoneyAlerts.length === 0 ? (
                <div className="text-center py-12 text-gray-500">
                  <Brain className="w-12 h-12 mx-auto mb-4 text-gray-300" />
                  <p>Нет сигналов Smart Money</p>
                </div>
              ) : (
                smartMoneyAlerts.map(renderSmartMoneyCard)
              )}
            </div>
          </div>
        )}

        {/* Watchlist */}
        {activeTab === 'watchlist' && (
          <div>
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-2xl font-bold text-gray-900">Список торговых пар</h2>
              <button
                onClick={() => setShowWatchlistModal(true)}
                className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg transition-colors"
              >
                Управление
              </button>
            </div>
            
            <div className="space-y-4">
              {watchlist.length === 0 ? (
                <div className="text-center py-12 text-gray-500">
                  <List className="w-12 h-12 mx-auto mb-4 text-gray-300" />
                  <p>Нет торговых пар в списке</p>
                </div>
              ) : (
                watchlist.map(renderWatchlistCard)
              )}
            </div>
          </div>
        )}

        {/* Stream Data */}
        {activeTab === 'stream' && (
          <div>
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-2xl font-bold text-gray-900">Потоковые данные</h2>
            </div>
            
            <div className="space-y-4">
              {streamData.slice(0, 20).map((item, index) => (
                <div key={`${item.symbol}-${index}`} className="bg-white rounded-lg shadow-md border border-gray-200 p-4 w-full">
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center space-x-3">
                      <div className={`w-3 h-3 rounded-full ${item.is_long ? 'bg-green-500' : 'bg-red-500'}`}></div>
                      <span className="font-bold text-lg text-gray-900">{item.symbol}</span>
                    </div>
                    
                    <button
                      onClick={() => openTradingView(item.symbol)}
                      className="text-blue-600 hover:text-blue-800 p-1"
                    >
                      <ExternalLink className="w-4 h-4" />
                    </button>
                  </div>

                  <div className="grid grid-cols-2 gap-4 text-sm">
                    <div>
                      <span className="text-gray-600">Цена:</span>
                      <div className="font-mono text-gray-900">${item.price.toFixed(8)}</div>
                    </div>
                    
                    <div>
                      <span className="text-gray-600">Объем:</span>
                      <div className="text-gray-900">{formatVolume(item.volume_usdt)}</div>
                    </div>
                  </div>

                  <div className="mt-3 pt-3 border-t border-gray-200 text-xs text-gray-500">
                    {formatTime(item.timestamp)}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </main>

      {/* Modals */}
      {selectedAlert && (
        <ChartModal
          alert={selectedAlert}
          onClose={() => setSelectedAlert(null)}
        />
      )}

      {selectedSmartMoneyAlert && (
        <SmartMoneyChartModal
          alert={selectedSmartMoneyAlert}
          onClose={() => setSelectedSmartMoneyAlert(null)}
        />
      )}

      {showWatchlistModal && (
        <WatchlistModal
          watchlist={watchlist}
          onClose={() => setShowWatchlistModal(false)}
          onUpdate={loadWatchlist}
        />
      )}

      {showStreamModal && (
        <StreamDataModal
          streamData={streamData}
          connectionStatus={connectionStatus}
          onClose={() => setShowStreamModal(false)}
        />
      )}

      {showSettings && (
        <SettingsModal
          settings={settings}
          onClose={() => setShowSettings(false)}
          onSave={handleSettingsSave}
        />
      )}
    </div>
  );
};

export default App;