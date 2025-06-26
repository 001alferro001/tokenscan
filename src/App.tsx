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
  RefreshCw
} from 'lucide-react';
import ChartModal from './components/ChartModal';

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
  const [activeTab, setActiveTab] = useState<'volume' | 'consecutive' | 'priority'>('volume');
  const [showSettings, setShowSettings] = useState(false);
  const [showChart, setShowChart] = useState(false);
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
    }
  });

  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    loadSettings();
    loadStats();
    loadAlerts();
    connectWebSocket();

    const statsInterval = setInterval(loadStats, 30000);
    const alertsInterval = setInterval(loadAlerts, 10000);

    return () => {
      clearInterval(statsInterval);
      clearInterval(alertsInterval);
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
      case 'stats_update':
        setStats(data.stats);
        break;
      default:
        break;
    }
  };

  const handleNewAlert = (alert: Alert) => {
    setAlerts(prev => [alert, ...prev.slice(0, 99)]);
    
    // Распределяем по типам
    switch (alert.alert_type) {
      case 'volume_spike':
        setVolumeAlerts(prev => [alert, ...prev.slice(0, 49)]);
        break;
      case 'consecutive_long':
        setConsecutiveAlerts(prev => [alert, ...prev.slice(0, 49)]);
        break;
      case 'priority':
        setPriorityAlerts(prev => [alert, ...prev.slice(0, 49)]);
        break;
    }
  };

  const handleAlertUpdate = (updatedAlert: Alert) => {
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

  const loadAlerts = async () => {
    try {
      const response = await fetch('/api/alerts/all');
      if (response.ok) {
        const data = await response.json();
        setAlerts(data.alerts || []);
        setVolumeAlerts(data.volume_alerts || []);
        setConsecutiveAlerts(data.consecutive_alerts || []);
        setPriorityAlerts(data.priority_alerts || []);
      }
    } catch (error) {
      console.error('Ошибка загрузки алертов:', error);
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
        if (type) {
          switch (type) {
            case 'volume':
              setVolumeAlerts([]);
              break;
            case 'consecutive':
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
    switch (alert.alert_type) {
      case 'volume_spike':
        if (alert.is_closed) {
          return alert.is_true_signal ? 
            <Check className="w-5 h-5 text-green-400" /> : 
            <X className="w-5 h-5 text-red-400" />;
        }
        return <Activity className="w-5 h-5 text-yellow-400" />;
      case 'consecutive_long':
        return <ArrowUp className="w-5 h-5 text-blue-400" />;
      case 'priority':
        return <Star className="w-5 h-5 text-purple-400" />;
      default:
        return <Activity className="w-5 h-5 text-gray-400" />;
    }
  };

  const getAlertTitle = (alert: Alert) => {
    switch (alert.alert_type) {
      case 'volume_spike':
        const status = alert.is_closed ? 
          (alert.is_true_signal ? ' (Истинный)' : ' (Ложный)') : 
          ' (В процессе)';
        return `Превышение объема${status}`;
      case 'consecutive_long':
        return `${alert.consecutive_count} LONG свечей подряд`;
      case 'priority':
        return 'Приоритетный сигнал';
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
      className="bg-gray-800 rounded-lg p-4 border border-gray-700 hover:border-gray-600 transition-colors cursor-pointer"
      onClick={() => openChart(alert)}
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center space-x-3">
          {getAlertIcon(alert)}
          <div>
            <h3 className="font-semibold text-white">{alert.symbol}</h3>
            <p className="text-sm text-gray-400">{getAlertTitle(alert)}</p>
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

      <div className="grid grid-cols-2 gap-4 text-sm">
        <div>
          <span className="text-gray-400">Цена:</span>
          <span className="ml-2 text-white">${alert.price.toFixed(8)}</span>
        </div>
        <div>
          <span className="text-gray-400">Время:</span>
          <span className="ml-2 text-white">
            {formatTime(alert.close_timestamp || alert.timestamp)}
          </span>
        </div>
        
        {alert.alert_type === 'volume_spike' && (
          <>
            <div>
              <span className="text-gray-400">Объем:</span>
              <span className="ml-2 text-white">
                ${formatVolume(alert.current_volume_usdt || 0)}
              </span>
            </div>
            <div>
              <span className="text-gray-400">Превышение:</span>
              <span className="ml-2 text-white">{alert.volume_ratio}x</span>
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
              onClick={() => loadAlerts()}
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
              { key: 'priority', label: 'Приоритетные', icon: Star }
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
          
          <button
            onClick={() => clearAlerts(activeTab)}
            className="flex items-center space-x-2 bg-red-600 hover:bg-red-700 px-4 py-2 rounded-lg transition-colors"
          >
            <Trash2 className="w-4 h-4" />
            <span>Очистить</span>
          </button>
        </div>

        {/* Alerts */}
        <div className="space-y-4">
          {getCurrentAlerts().length === 0 ? (
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
    </div>
  );
}

export default App;