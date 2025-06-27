import React, { useState, useEffect, useRef } from 'react';
import { 
  Settings, 
  Activity, 
  TrendingUp, 
  Star, 
  ExternalLink,
  X,
  Check,
  ArrowUp,
  BarChart3,
  Clock,
  DollarSign,
  Trash2,
  RefreshCw,
  Plus,
  List,
  Wifi,
  WifiOff,
  AlertTriangle
} from 'lucide-react';
import ChartModal from './components/ChartModal';
import WatchlistModal from './components/WatchlistModal';
import StreamDataModal from './components/StreamDataModal';

interface Alert {
  id: number;
  symbol: string;
  alert_type: 'volume_spike' | 'consecutive_long' | 'priority';
  price: number;
  volume_ratio?: number;
  consecutive_count?: number;
  current_volume_usdt?: number;
  average_volume_usdt?: number;
  is_true_signal?: boolean;
  is_closed?: boolean;
  timestamp: string;
  close_timestamp?: string;
  group_id?: number;
  message?: string;
  preliminary_alert?: Alert;
  final_alert?: Alert;
  has_imbalance?: boolean;
  imbalance_data?: {
    type: 'fair_value_gap' | 'order_block' | 'breaker_block';
    strength: number;
    direction: 'bullish' | 'bearish';
  };
  candle_data?: {
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
    alert_level?: number;
  };
  order_book_snapshot?: {
    bids: Array<[number, number]>;
    asks: Array<[number, number]>;
    timestamp: string;
  };
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
  change_24h?: number;
}

interface Settings {
  volume_analyzer: {
    analysis_hours: number;
    offset_minutes: number;
    volume_multiplier: number;
    min_volume_usdt: number;
    alert_grouping_minutes: number;
    consecutive_long_count: number;
    max_shadow_to_body_ratio: number;
    min_body_percentage: number;
    data_retention_hours: number;
  };
  price_filter: {
    price_check_interval_minutes: number;
    price_history_days: number;
    price_drop_percentage: number;
  };
  alerts: {
    volume_alerts_enabled: boolean;
    consecutive_alerts_enabled: boolean;
    priority_alerts_enabled: boolean;
  };
  telegram: {
    enabled: boolean;
  };
  orderbook: {
    enabled: boolean;
    snapshot_on_alert: boolean;
  };
  imbalance: {
    enabled: boolean;
    fair_value_gap_enabled: boolean;
    order_block_enabled: boolean;
    breaker_block_enabled: boolean;
  };
}

interface Stats {
  total_candles: number;
  long_candles: number;
  alerts_count: number;
  consecutive_alerts_count: number;
  priority_alerts_count: number;
  pairs_count: number;
  last_update: string;
}

function App() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [volumeAlerts, setVolumeAlerts] = useState<Alert[]>([]);
  const [consecutiveAlerts, setConsecutiveAlerts] = useState<Alert[]>([]);
  const [priorityAlerts, setPriorityAlerts] = useState<Alert[]>([]);
  const [watchlist, setWatchlist] = useState<WatchlistItem[]>([]);
  const [streamData, setStreamData] = useState<StreamData[]>([]);
  const [activeTab, setActiveTab] = useState<'volume' | 'consecutive' | 'priority' | 'watchlist' | 'stream'>('volume');
  const [showSettings, setShowSettings] = useState(false);
  const [showChart, setShowChart] = useState(false);
  const [showWatchlist, setShowWatchlist] = useState(false);
  const [showStream, setShowStream] = useState(false);
  const [selectedAlert, setSelectedAlert] = useState<Alert | null>(null);
  const [connectionStatus, setConnectionStatus] = useState<'connecting' | 'connected' | 'disconnected'>('connecting');
  const [stats, setStats] = useState<Stats>({
    total_candles: 0,
    long_candles: 0,
    alerts_count: 0,
    consecutive_alerts_count: 0,
    priority_alerts_count: 0,
    pairs_count: 0,
    last_update: ''
  });

  const [settings, setSettings] = useState<Settings>({
    volume_analyzer: {
      analysis_hours: 1,
      offset_minutes: 0,
      volume_multiplier: 2.0,
      min_volume_usdt: 1000,
      alert_grouping_minutes: 5,
      consecutive_long_count: 5,
      max_shadow_to_body_ratio: 1.0,
      min_body_percentage: 0.1,
      data_retention_hours: 2
    },
    price_filter: {
      price_check_interval_minutes: 5,
      price_history_days: 30,
      price_drop_percentage: 10.0
    },
    alerts: {
      volume_alerts_enabled: true,
      consecutive_alerts_enabled: true,
      priority_alerts_enabled: true
    },
    telegram: {
      enabled: false
    },
    orderbook: {
      enabled: false,
      snapshot_on_alert: false
    },
    imbalance: {
      enabled: false,
      fair_value_gap_enabled: true,
      order_block_enabled: true,
      breaker_block_enabled: true
    }
  });

  const wsRef = useRef<WebSocket | null>(null);
  const alertsLoadedRef = useRef(false);

  useEffect(() => {
    loadSettings();
    loadStats();
    loadInitialAlerts();
    loadWatchlist();
    connectWebSocket();

    const statsInterval = setInterval(loadStats, 30000);

    return () => {
      clearInterval(statsInterval);
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  const connectWebSocket = () => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;
    
    wsRef.current = new WebSocket(wsUrl);

    wsRef.current.onopen = () => {
      setConnectionStatus('connected');
      console.log('WebSocket подключен');
    };

    wsRef.current.onclose = () => {
      setConnectionStatus('disconnected');
      console.log('WebSocket отключен');
      setTimeout(connectWebSocket, 5000);
    };

    wsRef.current.onerror = (error) => {
      console.error('WebSocket ошибка:', error);
      setConnectionStatus('disconnected');
    };

    wsRef.current.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        handleWebSocketMessage(data);
      } catch (error) {
        console.error('Ошибка парсинга WebSocket сообщения:', error);
      }
    };
  };

  const handleWebSocketMessage = (data: any) => {
    switch (data.type) {
      case 'new_alert':
        handleNewAlert(data.alert);
        break;
      case 'alert_updated':
        handleAlertUpdate(data.alert);
        break;
      case 'kline_update':
        handleStreamUpdate(data);
        break;
      case 'stats_update':
        setStats(data.stats);
        break;
      case 'watchlist_updated':
        loadWatchlist();
        break;
      case 'alerts_cleared':
        handleAlertsClear(data.alert_type);
        break;
      default:
        break;
    }
  };

  const handleStreamUpdate = (data: any) => {
    const streamItem: StreamData = {
      symbol: data.symbol,
      price: parseFloat(data.data.close),
      volume: parseFloat(data.data.volume),
      volume_usdt: parseFloat(data.data.volume) * parseFloat(data.data.close),
      is_long: parseFloat(data.data.close) > parseFloat(data.data.open),
      timestamp: data.timestamp,
      change_24h: data.change_24h
    };

    setStreamData(prev => {
      const filtered = prev.filter(item => item.symbol !== data.symbol);
      return [streamItem, ...filtered].slice(0, 100);
    });
  };

  const handleNewAlert = (alert: Alert) => {
    console.log('Получен новый алерт:', alert);
    
    // Добавляем алерт в соответствующие списки без перезагрузки
    const addAlertToList = (alerts: Alert[], newAlert: Alert) => {
      // Проверяем, есть ли уже алерт с таким ID
      const existingIndex = alerts.findIndex(a => a.id === newAlert.id);
      
      if (existingIndex >= 0) {
        // Обновляем существующий алерт
        const updated = [...alerts];
        updated[existingIndex] = newAlert;
        return updated;
      } else {
        // Добавляем новый алерт в начало списка
        return [newAlert, ...alerts];
      }
    };

    setAlerts(prev => addAlertToList(prev, alert));
    
    // Распределяем по типам
    switch (alert.alert_type) {
      case 'volume_spike':
        setVolumeAlerts(prev => addAlertToList(prev, alert));
        break;
      case 'consecutive_long':
        setConsecutiveAlerts(prev => addAlertToList(prev, alert));
        break;
      case 'priority':
        setPriorityAlerts(prev => addAlertToList(prev, alert));
        break;
    }
  };

  const handleAlertUpdate = (updatedAlert: Alert) => {
    console.log('Обновление алерта:', updatedAlert);
    
    const updateAlertInList = (alerts: Alert[]) => 
      alerts.map(alert => alert.id === updatedAlert.id ? updatedAlert : alert);

    setAlerts(updateAlertInList);
    
    switch (updatedAlert.alert_type) {
      case 'volume_spike':
        setVolumeAlerts(updateAlertInList);
        break;
      case 'consecutive_long':
        setConsecutiveAlerts(updateAlertInList);
        break;
      case 'priority':
        setPriorityAlerts(updateAlertInList);
        break;
    }
  };

  const handleAlertsClear = (alertType?: string) => {
    if (alertType) {
      switch (alertType) {
        case 'volume_spike':
          setVolumeAlerts([]);
          break;
        case 'consecutive_long':
          setConsecutiveAlerts([]);
          break;
        case 'priority':
          setPriorityAlerts([]);
          break;
      }
    } else {
      setAlerts([]);
      setVolumeAlerts([]);
      setConsecutiveAlerts([]);
      setPriorityAlerts([]);
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

  const loadInitialAlerts = async () => {
    if (alertsLoadedRef.current) return;
    
    try {
      const response = await fetch('/api/alerts/all');
      if (response.ok) {
        const data = await response.json();
        
        // Сортируем алерты по времени закрытия свечи (новые сверху)
        const sortAlerts = (alerts: Alert[]) => 
          alerts.sort((a, b) => {
            const timeA = new Date(a.close_timestamp || a.timestamp).getTime();
            const timeB = new Date(b.close_timestamp || b.timestamp).getTime();
            return timeB - timeA;
          });

        setAlerts(sortAlerts(data.alerts || []));
        setVolumeAlerts(sortAlerts(data.volume_alerts || []));
        setConsecutiveAlerts(sortAlerts(data.consecutive_alerts || []));
        setPriorityAlerts(sortAlerts(data.priority_alerts || []));
        
        alertsLoadedRef.current = true;
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

  const saveSettings = async () => {
    try {
      const response = await fetch('/api/settings', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(settings),
      });

      if (response.ok) {
        setShowSettings(false);
        alert('Настройки сохранены');
      } else {
        alert('Ошибка сохранения настроек');
      }
    } catch (error) {
      console.error('Ошибка сохранения настроек:', error);
      alert('Ошибка сохранения настроек');
    }
  };

  const clearAlerts = async (type?: string) => {
    try {
      const url = type ? `/api/alerts/clear/${type}` : '/api/alerts/clear';
      const response = await fetch(url, { method: 'DELETE' });
      
      if (response.ok) {
        // Очищаем локально без ожидания WebSocket сообщения
        handleAlertsClear(type);
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

  const openChart = (alert: Alert) => {
    setSelectedAlert(alert);
    setShowChart(true);
  };

  const getAlertIcon = (alert: Alert) => {
    const hasImbalance = alert.has_imbalance;
    
    switch (alert.alert_type) {
      case 'volume_spike':
        if (alert.final_alert) {
          const icon = alert.final_alert.is_true_signal ? 
            <Check className="w-5 h-5 text-green-400" /> : 
            <X className="w-5 h-5 text-red-400" />;
          return hasImbalance ? (
            <div className="relative">
              {icon}
              <AlertTriangle className="w-3 h-3 text-yellow-400 absolute -top-1 -right-1" />
            </div>
          ) : icon;
        } else if (alert.preliminary_alert) {
          const icon = <Clock className="w-5 h-5 text-yellow-400" />;
          return hasImbalance ? (
            <div className="relative">
              {icon}
              <AlertTriangle className="w-3 h-3 text-yellow-400 absolute -top-1 -right-1" />
            </div>
          ) : icon;
        }
        const icon = alert.is_closed ? 
          (alert.is_true_signal ? 
            <Check className="w-5 h-5 text-green-400" /> : 
            <X className="w-5 h-5 text-red-400" />) :
          <Activity className="w-5 h-5 text-yellow-400" />;
        return hasImbalance ? (
          <div className="relative">
            {icon}
            <AlertTriangle className="w-3 h-3 text-yellow-400 absolute -top-1 -right-1" />
          </div>
        ) : icon;
      case 'consecutive_long':
        const consecutiveIcon = <ArrowUp className="w-5 h-5 text-blue-400" />;
        return hasImbalance ? (
          <div className="relative">
            {consecutiveIcon}
            <AlertTriangle className="w-3 h-3 text-yellow-400 absolute -top-1 -right-1" />
          </div>
        ) : consecutiveIcon;
      case 'priority':
        const priorityIcon = <Star className="w-5 h-5 text-purple-400" />;
        return hasImbalance ? (
          <div className="relative">
            {priorityIcon}
            <AlertTriangle className="w-3 h-3 text-yellow-400 absolute -top-1 -right-1" />
          </div>
        ) : priorityIcon;
      default:
        return <Activity className="w-5 h-5 text-gray-400" />;
    }
  };

  const getAlertTitle = (alert: Alert) => {
    const imbalanceText = alert.has_imbalance ? ' + Имбаланс' : '';
    
    switch (alert.alert_type) {
      case 'volume_spike':
        if (alert.final_alert) {
          const status = alert.final_alert.is_true_signal ? ' (Истинный)' : ' (Ложный)';
          return `Превышение объема${status}${imbalanceText}`;
        } else if (alert.preliminary_alert) {
          return `Превышение объема (Предварительный)${imbalanceText}`;
        }
        const status = alert.is_closed ? 
          (alert.is_true_signal ? ' (Истинный)' : ' (Ложный)') : 
          ' (В процессе)';
        return `Превышение объема${status}${imbalanceText}`;
      case 'consecutive_long':
        return `${alert.consecutive_count} LONG свечей подряд${imbalanceText}`;
      case 'priority':
        return `Приоритетный сигнал${imbalanceText}`;
      default:
        return 'Неизвестный тип алерта';
    }
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
      return `${(volume / 1000000).toFixed(1)}M`;
    } else if (volume >= 1000) {
      return `${(volume / 1000).toFixed(1)}K`;
    }
    return volume.toFixed(0);
  };

  const renderAlert = (alert: Alert) => (
    <div
      key={alert.id}
      className={`bg-gray-800 rounded-lg p-4 border transition-colors cursor-pointer ${
        alert.has_imbalance ? 'border-yellow-500 bg-yellow-900 bg-opacity-20' : 'border-gray-700 hover:border-gray-600'
      }`}
      onClick={() => openChart(alert)}
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center space-x-3">
          {getAlertIcon(alert)}
          <div>
            <h3 className="font-semibold text-white">{alert.symbol}</h3>
            <p className="text-sm text-gray-400">{getAlertTitle(alert)}</p>
            {alert.has_imbalance && alert.imbalance_data && (
              <div className="text-xs text-yellow-400 mt-1">
                {alert.imbalance_data.type === 'fair_value_gap' && 'Fair Value Gap'}
                {alert.imbalance_data.type === 'order_block' && 'Order Block'}
                {alert.imbalance_data.type === 'breaker_block' && 'Breaker Block'}
                {' '}({alert.imbalance_data.direction}, сила: {alert.imbalance_data.strength})
              </div>
            )}
          </div>
        </div>
        <button
          onClick={(e) => {
            e.stopPropagation();
            openTradingView(alert.symbol);
          }}
          className="flex items-center space-x-1 bg-blue-600 hover:bg-blue-700 px-3 py-1 rounded text-sm transition-colors"
        >
          <ExternalLink className="w-4 h-4" />
          <span>TradingView</span>
        </button>
      </div>

      {/* Предварительный алерт */}
      {alert.preliminary_alert && (
        <div className="mb-3 p-3 bg-yellow-900 bg-opacity-30 rounded border-l-4 border-yellow-400">
          <div className="flex items-center space-x-2 mb-2">
            <Clock className="w-4 h-4 text-yellow-400" />
            <span className="text-sm font-medium text-yellow-400">Предварительный алерт</span>
          </div>
          <div className="grid grid-cols-2 gap-2 text-sm">
            <div>
              <span className="text-gray-400">Цена:</span>
              <span className="ml-2 text-white">${alert.preliminary_alert.price.toFixed(8)}</span>
            </div>
            <div>
              <span className="text-gray-400">Объем:</span>
              <span className="ml-2 text-white">
                ${formatVolume(alert.preliminary_alert.current_volume_usdt || 0)}
              </span>
            </div>
            <div>
              <span className="text-gray-400">Превышение:</span>
              <span className="ml-2 text-white">{alert.preliminary_alert.volume_ratio}x</span>
            </div>
            <div>
              <span className="text-gray-400">Время:</span>
              <span className="ml-2 text-white">
                {formatTime(alert.preliminary_alert.timestamp)}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Основной алерт */}
      <div className="grid grid-cols-2 gap-4 text-sm">
        <div>
          <span className="text-gray-400">Цена:</span>
          <span className="ml-2 text-white">
            ${(alert.final_alert?.price || alert.price).toFixed(8)}
          </span>
        </div>
        <div>
          <span className="text-gray-400">Время закрытия:</span>
          <span className="ml-2 text-white">
            {formatTime(alert.close_timestamp || alert.timestamp)}
          </span>
        </div>
        
        {alert.alert_type === 'volume_spike' && (
          <>
            <div>
              <span className="text-gray-400">Объем:</span>
              <span className="ml-2 text-white">
                ${formatVolume((alert.final_alert?.current_volume_usdt || alert.current_volume_usdt) || 0)}
              </span>
            </div>
            <div>
              <span className="text-gray-400">Превышение:</span>
              <span className="ml-2 text-white">
                {alert.final_alert?.volume_ratio || alert.volume_ratio}x
              </span>
            </div>
          </>
        )}
        
        {alert.alert_type === 'consecutive_long' && (
          <div className="col-span-2">
            <span className="text-gray-400">Подряд LONG свечей:</span>
            <span className="ml-2 text-white font-semibold">
              {alert.consecutive_count}
            </span>
          </div>
        )}
        
        {alert.alert_type === 'priority' && (
          <>
            <div>
              <span className="text-gray-400">Объем:</span>
              <span className="ml-2 text-white">
                ${formatVolume(alert.current_volume_usdt || 0)}
              </span>
            </div>
            <div>
              <span className="text-gray-400">LONG свечей:</span>
              <span className="ml-2 text-white">{alert.consecutive_count}</span>
            </div>
          </>
        )}
      </div>

      {/* Данные свечи */}
      {alert.candle_data && (
        <div className="mt-3 p-3 bg-gray-700 rounded">
          <div className="text-sm font-medium text-gray-300 mb-2">Данные свечи (OHLCV):</div>
          <div className="grid grid-cols-5 gap-2 text-xs">
            <div>
              <span className="text-gray-400">O:</span>
              <span className="ml-1 text-white">{alert.candle_data.open.toFixed(8)}</span>
            </div>
            <div>
              <span className="text-gray-400">H:</span>
              <span className="ml-1 text-white">{alert.candle_data.high.toFixed(8)}</span>
            </div>
            <div>
              <span className="text-gray-400">L:</span>
              <span className="ml-1 text-white">{alert.candle_data.low.toFixed(8)}</span>
            </div>
            <div>
              <span className="text-gray-400">C:</span>
              <span className="ml-1 text-white">{alert.candle_data.close.toFixed(8)}</span>
            </div>
            <div>
              <span className="text-gray-400">V:</span>
              <span className="ml-1 text-white">{formatVolume(alert.candle_data.volume)}</span>
            </div>
          </div>
          {alert.candle_data.alert_level && (
            <div className="mt-2 text-xs">
              <span className="text-gray-400">Уровень алерта:</span>
              <span className="ml-2 text-yellow-400">${alert.candle_data.alert_level.toFixed(8)}</span>
            </div>
          )}
        </div>
      )}

      {/* Снимок стакана */}
      {alert.order_book_snapshot && (
        <div className="mt-3 p-3 bg-gray-700 rounded">
          <div className="text-sm font-medium text-gray-300 mb-2">Снимок стакана:</div>
          <div className="grid grid-cols-2 gap-4 text-xs">
            <div>
              <div className="text-green-400 mb-1">Покупки (Bids):</div>
              {alert.order_book_snapshot.bids.slice(0, 3).map(([price, size], i) => (
                <div key={i} className="flex justify-between">
                  <span className="text-white">${price.toFixed(8)}</span>
                  <span className="text-gray-400">{size.toFixed(2)}</span>
                </div>
              ))}
            </div>
            <div>
              <div className="text-red-400 mb-1">Продажи (Asks):</div>
              {alert.order_book_snapshot.asks.slice(0, 3).map(([price, size], i) => (
                <div key={i} className="flex justify-between">
                  <span className="text-white">${price.toFixed(8)}</span>
                  <span className="text-gray-400">{size.toFixed(2)}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {alert.message && (
        <div className="mt-3 p-2 bg-gray-700 rounded text-sm text-gray-300">
          {alert.message}
        </div>
      )}
    </div>
  );

  const getTabCount = (tab: string) => {
    switch (tab) {
      case 'volume':
        return volumeAlerts.length;
      case 'consecutive':
        return consecutiveAlerts.length;
      case 'priority':
        return priorityAlerts.length;
      case 'watchlist':
        return watchlist.length;
      case 'stream':
        return streamData.length;
      default:
        return 0;
    }
  };

  const getCurrentAlerts = () => {
    switch (activeTab) {
      case 'volume':
        return volumeAlerts;
      case 'consecutive':
        return consecutiveAlerts;
      case 'priority':
        return priorityAlerts;
      default:
        return [];
    }
  };

  const renderWatchlistTab = () => (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h3 className="text-xl font-semibold">Список торговых пар</h3>
        <button
          onClick={() => setShowWatchlist(true)}
          className="flex items-center space-x-2 bg-green-600 hover:bg-green-700 px-4 py-2 rounded-lg transition-colors"
        >
          <Plus className="w-4 h-4" />
          <span>Управление</span>
        </button>
      </div>
      
      {watchlist.length === 0 ? (
        <div className="text-center py-12 text-gray-400">
          <List className="w-16 h-16 mx-auto mb-4 opacity-50" />
          <p>Нет торговых пар в списке</p>
        </div>
      ) : (
        <div className="grid gap-4">
          {watchlist.map((item) => (
            <div key={item.id} className="bg-gray-800 rounded-lg p-4 border border-gray-700">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-3">
                  <div className={`w-3 h-3 rounded-full ${item.is_active ? 'bg-green-400' : 'bg-red-400'}`}></div>
                  <div>
                    <h4 className="font-semibold text-white">{item.symbol}</h4>
                    <p className="text-sm text-gray-400">
                      {item.is_active ? 'Активна' : 'Неактивна'}
                    </p>
                  </div>
                </div>
                
                <div className="text-right text-sm">
                  {item.price_drop_percentage && (
                    <div className="text-red-400">
                      Падение: {item.price_drop_percentage.toFixed(2)}%
                    </div>
                  )}
                  {item.current_price && (
                    <div className="text-gray-400">
                      Цена: ${item.current_price.toFixed(8)}
                    </div>
                  )}
                </div>
                
                <button
                  onClick={() => openTradingView(item.symbol)}
                  className="flex items-center space-x-1 bg-blue-600 hover:bg-blue-700 px-3 py-1 rounded text-sm transition-colors"
                >
                  <ExternalLink className="w-4 h-4" />
                  <span>TradingView</span>
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );

  const renderStreamTab = () => (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h3 className="text-xl font-semibold">Потоковые данные с биржи</h3>
        <div className="flex items-center space-x-2">
          {connectionStatus === 'connected' ? (
            <Wifi className="w-5 h-5 text-green-400" />
          ) : (
            <WifiOff className="w-5 h-5 text-red-400" />
          )}
          <span className="text-sm">
            {connectionStatus === 'connected' ? 'Подключено' : 'Отключено'}
          </span>
        </div>
      </div>
      
      {streamData.length === 0 ? (
        <div className="text-center py-12 text-gray-400">
          <Activity className="w-16 h-16 mx-auto mb-4 opacity-50" />
          <p>Ожидание потоковых данных...</p>
        </div>
      ) : (
        <div className="grid gap-2">
          {streamData.map((item, index) => (
            <div key={`${item.symbol}-${index}`} className="bg-gray-800 rounded-lg p-3 border border-gray-700">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-3">
                  <div className={`w-3 h-3 rounded-full ${item.is_long ? 'bg-green-400' : 'bg-red-400'}`}></div>
                  <div>
                    <span className="font-semibold text-white">{item.symbol}</span>
                    <span className="ml-2 text-sm text-gray-400">
                      {item.is_long ? 'LONG' : 'SHORT'}
                    </span>
                  </div>
                </div>
                
                <div className="text-right text-sm">
                  <div className="text-white">${item.price.toFixed(8)}</div>
                  <div className="text-gray-400">
                    Vol: ${formatVolume(item.volume_usdt)}
                  </div>
                </div>
                
                <div className="text-xs text-gray-500">
                  {formatTime(item.timestamp)}
                </div>
                
                <button
                  onClick={() => openTradingView(item.symbol)}
                  className="flex items-center space-x-1 bg-blue-600 hover:bg-blue-700 px-2 py-1 rounded text-xs transition-colors"
                >
                  <ExternalLink className="w-3 h-3" />
                  <span>TV</span>
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-blue-900 to-purple-900 text-white">
      <div className="container mx-auto px-4 py-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-3xl font-bold mb-2">📊 Анализатор Объемов</h1>
            <div className="flex items-center space-x-4 text-sm">
              <div className="flex items-center space-x-2">
                <div className={`w-3 h-3 rounded-full ${
                  connectionStatus === 'connected' ? 'bg-green-400' : 
                  connectionStatus === 'connecting' ? 'bg-yellow-400' : 'bg-red-400'
                }`}></div>
                <span>
                  {connectionStatus === 'connected' ? 'Подключено' : 
                   connectionStatus === 'connecting' ? 'Подключение...' : 'Отключено'}
                </span>
              </div>
              <span>Пар: {stats.pairs_count}</span>
              <span>Свечей: {stats.total_candles}</span>
            </div>
          </div>
          
          <div className="flex items-center space-x-3">
            <button
              onClick={() => loadInitialAlerts()}
              className="flex items-center space-x-2 bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded-lg transition-colors"
            >
              <RefreshCw className="w-4 h-4" />
              <span>Обновить</span>
            </button>
            <button
              onClick={() => setShowSettings(true)}
              className="flex items-center space-x-2 bg-gray-700 hover:bg-gray-600 px-4 py-2 rounded-lg transition-colors"
            >
              <Settings className="w-4 h-4" />
              <span>Настройки</span>
            </button>
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          <div className="bg-gray-800 rounded-lg p-4">
            <div className="flex items-center space-x-2 mb-2">
              <Activity className="w-5 h-5 text-blue-400" />
              <span className="text-sm text-gray-400">Алерты по объему</span>
            </div>
            <div className="text-2xl font-bold">{stats.alerts_count}</div>
          </div>
          
          <div className="bg-gray-800 rounded-lg p-4">
            <div className="flex items-center space-x-2 mb-2">
              <ArrowUp className="w-5 h-5 text-green-400" />
              <span className="text-sm text-gray-400">LONG последовательности</span>
            </div>
            <div className="text-2xl font-bold">{stats.consecutive_alerts_count}</div>
          </div>
          
          <div className="bg-gray-800 rounded-lg p-4">
            <div className="flex items-center space-x-2 mb-2">
              <Star className="w-5 h-5 text-purple-400" />
              <span className="text-sm text-gray-400">Приоритетные</span>
            </div>
            <div className="text-2xl font-bold">{stats.priority_alerts_count}</div>
          </div>
          
          <div className="bg-gray-800 rounded-lg p-4">
            <div className="flex items-center space-x-2 mb-2">
              <TrendingUp className="w-5 h-5 text-yellow-400" />
              <span className="text-sm text-gray-400">LONG свечи</span>
            </div>
            <div className="text-2xl font-bold">
              {stats.total_candles > 0 ? 
                Math.round((stats.long_candles / stats.total_candles) * 100) : 0}%
            </div>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex space-x-1 bg-gray-800 rounded-lg p-1">
            {[
              { key: 'volume', label: 'Алерты по объему', icon: Activity },
              { key: 'consecutive', label: 'LONG последовательности', icon: ArrowUp },
              { key: 'priority', label: 'Приоритетные', icon: Star },
              { key: 'watchlist', label: 'Торговые пары', icon: List },
              { key: 'stream', label: 'Потоковые данные', icon: Wifi }
            ].map(({ key, label, icon: Icon }) => (
              <button
                key={key}
                onClick={() => setActiveTab(key as any)}
                className={`flex items-center space-x-2 px-4 py-2 rounded-md transition-colors ${
                  activeTab === key
                    ? 'bg-blue-600 text-white'
                    : 'text-gray-400 hover:text-white hover:bg-gray-700'
                }`}
              >
                <Icon className="w-4 h-4" />
                <span>{label}</span>
                <span className="bg-gray-600 text-xs px-2 py-1 rounded-full">
                  {getTabCount(key)}
                </span>
              </button>
            ))}
          </div>
          
          {(activeTab === 'volume' || activeTab === 'consecutive' || activeTab === 'priority') && (
            <button
              onClick={() => clearAlerts(activeTab === 'volume' ? 'volume_spike' : activeTab === 'consecutive' ? 'consecutive_long' : 'priority')}
              className="flex items-center space-x-2 bg-red-600 hover:bg-red-700 px-4 py-2 rounded-lg transition-colors"
            >
              <Trash2 className="w-4 h-4" />
              <span>Очистить</span>
            </button>
          )}
        </div>

        {/* Content */}
        <div className="space-y-4">
          {activeTab === 'watchlist' ? (
            renderWatchlistTab()
          ) : activeTab === 'stream' ? (
            renderStreamTab()
          ) : getCurrentAlerts().length === 0 ? (
            <div className="text-center py-12 text-gray-400">
              <BarChart3 className="w-16 h-16 mx-auto mb-4 opacity-50" />
              <p>Нет алертов данного типа</p>
            </div>
          ) : (
            getCurrentAlerts().map(renderAlert)
          )}
        </div>
      </div>

      {/* Settings Modal */}
      {showSettings && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-gray-800 rounded-lg p-6 max-w-4xl w-full max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-2xl font-bold">Настройки</h2>
              <button
                onClick={() => setShowSettings(false)}
                className="text-gray-400 hover:text-white"
              >
                <X className="w-6 h-6" />
              </button>
            </div>

            <div className="space-y-8">
              {/* Alert Settings */}
              <div>
                <h3 className="text-xl font-semibold mb-4 text-blue-400">Управление алертами</h3>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <label className="flex items-center space-x-3">
                    <input
                      type="checkbox"
                      checked={settings.alerts.volume_alerts_enabled}
                      onChange={(e) => setSettings(prev => ({
                        ...prev,
                        alerts: {
                          ...prev.alerts,
                          volume_alerts_enabled: e.target.checked
                        }
                      }))}
                      className="w-4 h-4 text-blue-600 bg-gray-700 border-gray-600 rounded"
                    />
                    <span>Алерты по объему</span>
                  </label>
                  
                  <label className="flex items-center space-x-3">
                    <input
                      type="checkbox"
                      checked={settings.alerts.consecutive_alerts_enabled}
                      onChange={(e) => setSettings(prev => ({
                        ...prev,
                        alerts: {
                          ...prev.alerts,
                          consecutive_alerts_enabled: e.target.checked
                        }
                      }))}
                      className="w-4 h-4 text-blue-600 bg-gray-700 border-gray-600 rounded"
                    />
                    <span>LONG последовательности</span>
                  </label>
                  
                  <label className="flex items-center space-x-3">
                    <input
                      type="checkbox"
                      checked={settings.alerts.priority_alerts_enabled}
                      onChange={(e) => setSettings(prev => ({
                        ...prev,
                        alerts: {
                          ...prev.alerts,
                          priority_alerts_enabled: e.target.checked
                        }
                      }))}
                      className="w-4 h-4 text-blue-600 bg-gray-700 border-gray-600 rounded"
                    />
                    <span>Приоритетные сигналы</span>
                  </label>
                </div>
              </div>

              {/* Order Book Settings */}
              <div>
                <h3 className="text-xl font-semibold mb-4 text-orange-400">Настройки стакана</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <label className="flex items-center space-x-3">
                    <input
                      type="checkbox"
                      checked={settings.orderbook.enabled}
                      onChange={(e) => setSettings(prev => ({
                        ...prev,
                        orderbook: {
                          ...prev.orderbook,
                          enabled: e.target.checked
                        }
                      }))}
                      className="w-4 h-4 text-blue-600 bg-gray-700 border-gray-600 rounded"
                    />
                    <span>Получение данных стакана</span>
                  </label>
                  
                  <label className="flex items-center space-x-3">
                    <input
                      type="checkbox"
                      checked={settings.orderbook.snapshot_on_alert}
                      onChange={(e) => setSettings(prev => ({
                        ...prev,
                        orderbook: {
                          ...prev.orderbook,
                          snapshot_on_alert: e.target.checked
                        }
                      }))}
                      className="w-4 h-4 text-blue-600 bg-gray-700 border-gray-600 rounded"
                    />
                    <span>Снимок стакана при алерте</span>
                  </label>
                </div>
              </div>

              {/* Imbalance Settings */}
              <div>
                <h3 className="text-xl font-semibold mb-4 text-yellow-400">Анализ имбаланса</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <label className="flex items-center space-x-3">
                    <input
                      type="checkbox"
                      checked={settings.imbalance.enabled}
                      onChange={(e) => setSettings(prev => ({
                        ...prev,
                        imbalance: {
                          ...prev.imbalance,
                          enabled: e.target.checked
                        }
                      }))}
                      className="w-4 h-4 text-blue-600 bg-gray-700 border-gray-600 rounded"
                    />
                    <span>Включить анализ имбаланса</span>
                  </label>
                  
                  <label className="flex items-center space-x-3">
                    <input
                      type="checkbox"
                      checked={settings.imbalance.fair_value_gap_enabled}
                      onChange={(e) => setSettings(prev => ({
                        ...prev,
                        imbalance: {
                          ...prev.imbalance,
                          fair_value_gap_enabled: e.target.checked
                        }
                      }))}
                      className="w-4 h-4 text-blue-600 bg-gray-700 border-gray-600 rounded"
                    />
                    <span>Fair Value Gap</span>
                  </label>
                  
                  <label className="flex items-center space-x-3">
                    <input
                      type="checkbox"
                      checked={settings.imbalance.order_block_enabled}
                      onChange={(e) => setSettings(prev => ({
                        ...prev,
                        imbalance: {
                          ...prev.imbalance,
                          order_block_enabled: e.target.checked
                        }
                      }))}
                      className="w-4 h-4 text-blue-600 bg-gray-700 border-gray-600 rounded"
                    />
                    <span>Order Block</span>
                  </label>
                  
                  <label className="flex items-center space-x-3">
                    <input
                      type="checkbox"
                      checked={settings.imbalance.breaker_block_enabled}
                      onChange={(e) => setSettings(prev => ({
                        ...prev,
                        imbalance: {
                          ...prev.imbalance,
                          breaker_block_enabled: e.target.checked
                        }
                      }))}
                      className="w-4 h-4 text-blue-600 bg-gray-700 border-gray-600 rounded"
                    />
                    <span>Breaker Block</span>
                  </label>
                </div>
              </div>

              {/* Volume Analysis Settings */}
              <div>
                <h3 className="text-xl font-semibold mb-4 text-green-400">Анализ объемов</h3>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium mb-2">Период анализа (часы)</label>
                    <input
                      type="number"
                      min="1"
                      max="24"
                      value={settings.volume_analyzer.analysis_hours}
                      onChange={(e) => setSettings(prev => ({
                        ...prev,
                        volume_analyzer: {
                          ...prev.volume_analyzer,
                          analysis_hours: parseInt(e.target.value)
                        }
                      }))}
                      className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium mb-2">Множитель объема</label>
                    <input
                      type="number"
                      min="1"
                      max="10"
                      step="0.1"
                      value={settings.volume_analyzer.volume_multiplier}
                      onChange={(e) => setSettings(prev => ({
                        ...prev,
                        volume_analyzer: {
                          ...prev.volume_analyzer,
                          volume_multiplier: parseFloat(e.target.value)
                        }
                      }))}
                      className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium mb-2">Мин. объем (USDT)</label>
                    <input
                      type="number"
                      min="100"
                      value={settings.volume_analyzer.min_volume_usdt}
                      onChange={(e) => setSettings(prev => ({
                        ...prev,
                        volume_analyzer: {
                          ...prev.volume_analyzer,
                          min_volume_usdt: parseInt(e.target.value)
                        }
                      }))}
                      className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium mb-2">Количество LONG свечей</label>
                    <select
                      value={settings.volume_analyzer.consecutive_long_count}
                      onChange={(e) => setSettings(prev => ({
                        ...prev,
                        volume_analyzer: {
                          ...prev.volume_analyzer,
                          consecutive_long_count: parseInt(e.target.value)
                        }
                      }))}
                      className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white"
                    >
                      {[2, 3, 4, 5, 6, 7, 8, 9, 10].map(num => (
                        <option key={num} value={num}>{num}</option>
                      ))}
                    </select>
                  </div>

                  <div className="col-span-2">
                    <label className="block text-sm font-medium mb-2">Период хранения данных (часы)</label>
                    <select
                      value={settings.volume_analyzer.data_retention_hours}
                      onChange={(e) => setSettings(prev => ({
                        ...prev,
                        volume_analyzer: {
                          ...prev.volume_analyzer,
                          data_retention_hours: parseInt(e.target.value)
                        }
                      }))}
                      className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white"
                    >
                      {[1, 2, 3, 4, 5].map(num => (
                        <option key={num} value={num}>{num} час{num > 1 ? (num < 5 ? 'а' : 'ов') : ''}</option>
                      ))}
                    </select>
                  </div>
                </div>
              </div>

              {/* Price Filter Settings */}
              <div>
                <h3 className="text-xl font-semibold mb-4 text-purple-400">Фильтр по цене</h3>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium mb-2">Интервал проверки (мин)</label>
                    <input
                      type="number"
                      min="1"
                      max="60"
                      value={settings.price_filter.price_check_interval_minutes}
                      onChange={(e) => setSettings(prev => ({
                        ...prev,
                        price_filter: {
                          ...prev.price_filter,
                          price_check_interval_minutes: parseInt(e.target.value)
                        }
                      }))}
                      className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white"
                    />
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium mb-2">Период истории (дни)</label>
                    <input
                      type="number"
                      min="1"
                      max="365"
                      value={settings.price_filter.price_history_days}
                      onChange={(e) => setSettings(prev => ({
                        ...prev,
                        price_filter: {
                          ...prev.price_filter,
                          price_history_days: parseInt(e.target.value)
                        }
                      }))}
                      className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white"
                    />
                  </div>
                  
                  <div className="col-span-2">
                    <label className="block text-sm font-medium mb-2">Падение цены (%)</label>
                    <input
                      type="number"
                      min="1"
                      max="90"
                      step="0.1"
                      value={settings.price_filter.price_drop_percentage}
                      onChange={(e) => setSettings(prev => ({
                        ...prev,
                        price_filter: {
                          ...prev.price_filter,
                          price_drop_percentage: parseFloat(e.target.value)
                        }
                      }))}
                      className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white"
                    />
                  </div>
                </div>
              </div>

              {/* Telegram Settings */}
              <div>
                <h3 className="text-xl font-semibold mb-4 text-green-400">Telegram уведомления</h3>
                <div className="bg-gray-700 rounded-lg p-4">
                  <div className="flex items-center space-x-2 mb-3">
                    <span className={`w-3 h-3 rounded-full ${settings.telegram.enabled ? 'bg-green-400' : 'bg-red-400'}`}></span>
                    <span className="text-sm">
                      {settings.telegram.enabled ? 'Подключено' : 'Не настроено'}
                    </span>
                  </div>
                  <p className="text-xs text-gray-400">
                    Для настройки Telegram уведомлений добавьте в .env файл:
                  </p>
                  <div className="bg-black bg-opacity-50 rounded p-2 mt-2 text-xs font-mono">
                    TELEGRAM_BOT_TOKEN=your_bot_token<br/>
                    TELEGRAM_CHAT_ID=your_chat_id
                  </div>
                </div>
              </div>
            </div>
            
            <div className="flex space-x-3 mt-8">
              <button
                onClick={saveSettings}
                className="flex-1 bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded-lg transition-colors"
              >
                Сохранить
              </button>
              <button
                onClick={() => setShowSettings(false)}
                className="flex-1 bg-gray-600 hover:bg-gray-700 px-4 py-2 rounded-lg transition-colors"
              >
                Отмена
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Chart Modal */}
      {showChart && selectedAlert && (
        <ChartModal
          alert={selectedAlert}
          onClose={() => {
            setShowChart(false);
            setSelectedAlert(null);
          }}
        />
      )}

      {/* Watchlist Modal */}
      {showWatchlist && (
        <WatchlistModal
          watchlist={watchlist}
          onClose={() => setShowWatchlist(false)}
          onUpdate={loadWatchlist}
        />
      )}
    </div>
  );
}

export default App;