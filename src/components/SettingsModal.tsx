import React, { useState, useEffect } from 'react';
import { X, Save, RefreshCw, DollarSign, Settings as SettingsIcon, Shield, AlertTriangle } from 'lucide-react';

interface Settings {
  volume_analyzer: {
    analysis_hours: number;
    offset_minutes: number;
    volume_multiplier: number;
    min_volume_usdt: number;
    consecutive_long_count: number;
    alert_grouping_minutes: number;
    data_retention_hours: number;
    update_interval_seconds: number;
    notification_enabled: boolean;
    volume_type: 'all' | 'long' | 'short';
    pairs_check_interval_minutes: number;
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
  trading: {
    account_balance: number;
    max_risk_per_trade: number;
    max_open_trades: number;
    default_stop_loss_percentage: number;
    default_take_profit_percentage: number;
    auto_calculate_quantity: boolean;
    api_key?: string;
    api_secret?: string;
    enable_real_trading?: boolean;
    default_leverage?: number;
    default_margin_type?: 'isolated' | 'cross';
    confirm_trades?: boolean;
  };
}

interface SettingsModalProps {
  settings: Settings | null;
  onClose: () => void;
  onSave: (settings: Settings) => void;
}

const SettingsModal: React.FC<SettingsModalProps> = ({ settings, onClose, onSave }) => {
  const [localSettings, setLocalSettings] = useState<Settings | null>(null);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<'volume' | 'alerts' | 'imbalance' | 'orderbook' | 'trading'>('volume');
  const [showApiSecret, setShowApiSecret] = useState(false);
  const [testApiStatus, setTestApiStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle');
  const [testApiMessage, setTestApiMessage] = useState('');

  useEffect(() => {
    if (settings) {
      // Создаем полную копию настроек с дефолтными значениями
      const defaultSettings: Settings = {
        volume_analyzer: {
          analysis_hours: 1,
          offset_minutes: 0,
          volume_multiplier: 2.0,
          min_volume_usdt: 1000,
          consecutive_long_count: 5,
          alert_grouping_minutes: 5,
          data_retention_hours: 2,
          update_interval_seconds: 1,
          notification_enabled: true,
          volume_type: 'long',
          pairs_check_interval_minutes: 30,
          ...settings.volume_analyzer
        },
        alerts: {
          volume_alerts_enabled: true,
          consecutive_alerts_enabled: true,
          priority_alerts_enabled: true,
          ...settings.alerts
        },
        imbalance: {
          fair_value_gap_enabled: true,
          order_block_enabled: true,
          breaker_block_enabled: true,
          min_gap_percentage: 0.1,
          min_strength: 0.5,
          ...settings.imbalance
        },
        orderbook: {
          enabled: false,
          snapshot_on_alert: false,
          ...settings.orderbook
        },
        telegram: {
          enabled: false,
          ...settings.telegram
        },
        trading: {
          account_balance: 10000,
          max_risk_per_trade: 2,
          max_open_trades: 5,
          default_stop_loss_percentage: 2,
          default_take_profit_percentage: 6,
          auto_calculate_quantity: true,
          enable_real_trading: false,
          default_leverage: 1,
          default_margin_type: 'isolated',
          confirm_trades: true,
          ...settings.trading
        }
      };
      
      setLocalSettings(defaultSettings);
    }
  }, [settings]);

  const handleSave = async () => {
    if (!localSettings) return;

    setLoading(true);
    try {
      const response = await fetch('/api/settings', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(localSettings),
      });

      if (response.ok) {
        onSave(localSettings);
        onClose();
      } else {
        alert('Ошибка сохранения настроек');
      }
    } catch (error) {
      console.error('Ошибка сохранения настроек:', error);
      alert('Ошибка сохранения настроек');
    } finally {
      setLoading(false);
    }
  };

  const updateVolumeSettings = (key: string, value: any) => {
    if (!localSettings) return;
    setLocalSettings({
      ...localSettings,
      volume_analyzer: {
        ...localSettings.volume_analyzer,
        [key]: value
      }
    });
  };

  const updateAlertSettings = (key: string, value: any) => {
    if (!localSettings) return;
    setLocalSettings({
      ...localSettings,
      alerts: {
        ...localSettings.alerts,
        [key]: value
      }
    });
  };

  const updateImbalanceSettings = (key: string, value: any) => {
    if (!localSettings) return;
    setLocalSettings({
      ...localSettings,
      imbalance: {
        ...localSettings.imbalance,
        [key]: value
      }
    });
  };

  const updateOrderbookSettings = (key: string, value: any) => {
    if (!localSettings) return;
    setLocalSettings({
      ...localSettings,
      orderbook: {
        ...localSettings.orderbook,
        [key]: value
      }
    });
  };

  const updateTradingSettings = (key: string, value: any) => {
    if (!localSettings) return;
    setLocalSettings({
      ...localSettings,
      trading: {
        ...localSettings.trading,
        [key]: value
      }
    });
  };

  const testApiConnection = async () => {
    if (!localSettings?.trading.api_key || !localSettings?.trading.api_secret) {
      setTestApiStatus('error');
      setTestApiMessage('API ключ и секрет должны быть заполнены');
      return;
    }

    setTestApiStatus('loading');
    setTestApiMessage('Проверка подключения...');

    try {
      const response = await fetch('/api/trading/test-connection', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          api_key: localSettings.trading.api_key,
          api_secret: localSettings.trading.api_secret
        }),
      });

      const data = await response.json();

      if (response.ok) {
        setTestApiStatus('success');
        setTestApiMessage(`Подключение успешно! Баланс: $${data.balance.toFixed(2)}`);
      } else {
        setTestApiStatus('error');
        setTestApiMessage(`Ошибка: ${data.error || 'Не удалось подключиться к API'}`);
      }
    } catch (error) {
      console.error('Ошибка проверки API:', error);
      setTestApiStatus('error');
      setTestApiMessage('Ошибка соединения с сервером');
    }
  };

  if (!localSettings) {
    return (
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
        <div className="bg-white rounded-lg p-8">
          <div className="flex items-center justify-center">
            <RefreshCw className="w-6 h-6 animate-spin text-blue-600 mr-2" />
            <span className="text-gray-700">Загрузка настроек...</span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-lg w-full max-w-4xl max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200">
          <h2 className="text-2xl font-bold text-gray-900">Настройки системы</h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 p-2"
          >
            <X className="w-6 h-6" />
          </button>
        </div>

        {/* Tabs */}
        <div className="border-b border-gray-200">
          <nav className="flex space-x-8 px-6">
            {[
              { id: 'volume', label: 'Анализ объемов' },
              { id: 'alerts', label: 'Алерты' },
              { id: 'imbalance', label: 'Smart Money' },
              { id: 'orderbook', label: 'Стакан заявок' },
              { id: 'trading', label: 'Торговля' }
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={`py-4 px-1 border-b-2 font-medium text-sm transition-colors ${
                  activeTab === tab.id
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </nav>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {/* Volume Analyzer Settings */}
          {activeTab === 'volume' && (
            <div className="space-y-6">
              <h3 className="text-lg font-semibold text-gray-900">Настройки анализа объемов</h3>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Период анализа (часы)
                  </label>
                  <input
                    type="number"
                    min="1"
                    max="24"
                    value={localSettings.volume_analyzer.analysis_hours}
                    onChange={(e) => updateVolumeSettings('analysis_hours', parseInt(e.target.value))}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  />
                  <p className="text-xs text-gray-500 mt-1">За какой период анализировать исторические объемы</p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Смещение (минуты)
                  </label>
                  <input
                    type="number"
                    min="0"
                    max="60"
                    value={localSettings.volume_analyzer.offset_minutes}
                    onChange={(e) => updateVolumeSettings('offset_minutes', parseInt(e.target.value))}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  />
                  <p className="text-xs text-gray-500 mt-1">Смещение для расчета среднего объема</p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Множитель объема
                  </label>
                  <input
                    type="number"
                    min="1.1"
                    max="10"
                    step="0.1"
                    value={localSettings.volume_analyzer.volume_multiplier}
                    onChange={(e) => updateVolumeSettings('volume_multiplier', parseFloat(e.target.value))}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  />
                  <p className="text-xs text-gray-500 mt-1">Во сколько раз объем должен превышать средний</p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Тип свечей для анализа
                  </label>
                  <select
                    value={localSettings.volume_analyzer.volume_type}
                    onChange={(e) => updateVolumeSettings('volume_type', e.target.value)}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  >
                    <option value="all">Все свечи</option>
                    <option value="long">Только LONG</option>
                    <option value="short">Только SHORT</option>
                  </select>
                  <p className="text-xs text-gray-500 mt-1">Какие свечи учитывать при расчете среднего объема</p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Минимальный объем (USDT)
                  </label>
                  <input
                    type="number"
                    min="100"
                    max="100000"
                    step="100"
                    value={localSettings.volume_analyzer.min_volume_usdt}
                    onChange={(e) => updateVolumeSettings('min_volume_usdt', parseInt(e.target.value))}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  />
                  <p className="text-xs text-gray-500 mt-1">Минимальный объем для анализа</p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    LONG свечей подряд
                  </label>
                  <input
                    type="number"
                    min="2"
                    max="20"
                    value={localSettings.volume_analyzer.consecutive_long_count}
                    onChange={(e) => updateVolumeSettings('consecutive_long_count', parseInt(e.target.value))}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  />
                  <p className="text-xs text-gray-500 mt-1">Количество подряд идущих LONG свечей для алерта</p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Интервал обновления (секунды)
                  </label>
                  <input
                    type="number"
                    min="1"
                    max="60"
                    value={localSettings.volume_analyzer.update_interval_seconds}
                    onChange={(e) => updateVolumeSettings('update_interval_seconds', parseInt(e.target.value))}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  />
                  <p className="text-xs text-gray-500 mt-1">Частота получения данных с биржи</p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Хранение данных (часы)
                  </label>
                  <input
                    type="number"
                    min="1"
                    max="24"
                    value={localSettings.volume_analyzer.data_retention_hours}
                    onChange={(e) => updateVolumeSettings('data_retention_hours', parseInt(e.target.value))}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  />
                  <p className="text-xs text-gray-500 mt-1">Сколько часов хранить исторические данные</p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Интервал проверки пар (минуты)
                  </label>
                  <input
                    type="number"
                    min="5"
                    max="1440"
                    value={localSettings.volume_analyzer.pairs_check_interval_minutes}
                    onChange={(e) => updateVolumeSettings('pairs_check_interval_minutes', parseInt(e.target.value))}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  />
                  <p className="text-xs text-gray-500 mt-1">Как часто проверять список торговых пар на бирже</p>
                </div>
              </div>

              <div className="p-4 bg-blue-50 rounded-lg">
                <h4 className="font-medium text-blue-900 mb-2">Логика расчета среднего объема</h4>
                <p className="text-sm text-blue-700">
                  От текущей свечи отступаем влево на <strong>{localSettings.volume_analyzer.offset_minutes + localSettings.volume_analyzer.analysis_hours * 60}</strong> минут, 
                  затем анализируем <strong>{localSettings.volume_analyzer.analysis_hours * 60}</strong> минут данных 
                  ({localSettings.volume_analyzer.volume_type === 'all' ? 'все свечи' : 
                    localSettings.volume_analyzer.volume_type === 'long' ? 'только LONG свечи' : 'только SHORT свечи'}).
                </p>
              </div>
            </div>
          )}

          {/* Alert Settings */}
          {activeTab === 'alerts' && (
            <div className="space-y-6">
              <h3 className="text-lg font-semibold text-gray-900">Настройки алертов</h3>
              
              <div className="space-y-4">
                <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                  <div>
                    <h4 className="font-medium text-gray-900">Алерты по объему</h4>
                    <p className="text-sm text-gray-600">Уведомления при превышении объема</p>
                  </div>
                  <label className="relative inline-flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={localSettings.alerts.volume_alerts_enabled}
                      onChange={(e) => updateAlertSettings('volume_alerts_enabled', e.target.checked)}
                      className="sr-only peer"
                    />
                    <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                  </label>
                </div>

                <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                  <div>
                    <h4 className="font-medium text-gray-900">Алерты по последовательностям</h4>
                    <p className="text-sm text-gray-600">Уведомления при подряд идущих LONG свечах</p>
                  </div>
                  <label className="relative inline-flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={localSettings.alerts.consecutive_alerts_enabled}
                      onChange={(e) => updateAlertSettings('consecutive_alerts_enabled', e.target.checked)}
                      className="sr-only peer"
                    />
                    <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                  </label>
                </div>

                <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                  <div>
                    <h4 className="font-medium text-gray-900">Приоритетные алерты</h4>
                    <p className="text-sm text-gray-600">Комбинированные сигналы высокого приоритета</p>
                  </div>
                  <label className="relative inline-flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={localSettings.alerts.priority_alerts_enabled}
                      onChange={(e) => updateAlertSettings('priority_alerts_enabled', e.target.checked)}
                      className="sr-only peer"
                    />
                    <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                  </label>
                </div>

                <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                  <div>
                    <h4 className="font-medium text-gray-900">Всплывающие уведомления</h4>
                    <p className="text-sm text-gray-600">Показывать уведомления в браузере при новых алертах</p>
                  </div>
                  <label className="relative inline-flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={localSettings.volume_analyzer.notification_enabled}
                      onChange={(e) => updateVolumeSettings('notification_enabled', e.target.checked)}
                      className="sr-only peer"
                    />
                    <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                  </label>
                </div>
              </div>

              <div className="mt-6 p-4 bg-blue-50 rounded-lg">
                <h4 className="font-medium text-blue-900 mb-2">Telegram уведомления</h4>
                <p className="text-sm text-blue-700">
                  Статус: {localSettings.telegram?.enabled ? '✅ Включены' : '❌ Отключены'}
                </p>
                <p className="text-xs text-blue-600 mt-1">
                  Настройте TELEGRAM_BOT_TOKEN и TELEGRAM_CHAT_ID в файле .env для включения
                </p>
              </div>
            </div>
          )}

          {/* Smart Money Settings */}
          {activeTab === 'imbalance' && (
            <div className="space-y-6">
              <h3 className="text-lg font-semibold text-gray-900">Настройки Smart Money Concepts</h3>
              
              <div className="p-4 bg-purple-50 rounded-lg mb-6">
                <h4 className="font-medium text-purple-900 mb-2">🧠 Smart Money Concepts</h4>
                <p className="text-sm text-purple-700">
                  Анализ имбалансов на основе концепций институциональной торговли. 
                  Система автоматически определяет Fair Value Gaps, Order Blocks и Breaker Blocks.
                </p>
              </div>
              
              <div className="space-y-4">
                <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                  <div>
                    <h4 className="font-medium text-gray-900">Fair Value Gap (FVG)</h4>
                    <p className="text-sm text-gray-600">Анализ разрывов в ценах между свечами - зоны несбалансированности</p>
                  </div>
                  <label className="relative inline-flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={localSettings.imbalance.fair_value_gap_enabled}
                      onChange={(e) => updateImbalanceSettings('fair_value_gap_enabled', e.target.checked)}
                      className="sr-only peer"
                    />
                    <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                  </label>
                </div>

                <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                  <div>
                    <h4 className="font-medium text-gray-900">Order Block (OB)</h4>
                    <p className="text-sm text-gray-600">Анализ блоков заявок институциональных игроков - зоны накопления</p>
                  </div>
                  <label className="relative inline-flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={localSettings.imbalance.order_block_enabled}
                      onChange={(e) => updateImbalanceSettings('order_block_enabled', e.target.checked)}
                      className="sr-only peer"
                    />
                    <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                  </label>
                </div>

                <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                  <div>
                    <h4 className="font-medium text-gray-900">Breaker Block (BB)</h4>
                    <p className="text-sm text-gray-600">Анализ пробитых уровней поддержки/сопротивления - смена структуры</p>
                  </div>
                  <label className="relative inline-flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={localSettings.imbalance.breaker_block_enabled}
                      onChange={(e) => updateImbalanceSettings('breaker_block_enabled', e.target.checked)}
                      className="sr-only peer"
                    />
                    <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                  </label>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Минимальный размер гэпа (%)
                  </label>
                  <input
                    type="number"
                    min="0.01"
                    max="5"
                    step="0.01"
                    value={localSettings.imbalance.min_gap_percentage}
                    onChange={(e) => updateImbalanceSettings('min_gap_percentage', parseFloat(e.target.value))}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  />
                  <p className="text-xs text-gray-500 mt-1">Минимальный размер разрыва для Fair Value Gap</p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Минимальная сила сигнала
                  </label>
                  <input
                    type="number"
                    min="0.1"
                    max="10"
                    step="0.1"
                    value={localSettings.imbalance.min_strength}
                    onChange={(e) => updateImbalanceSettings('min_strength', parseFloat(e.target.value))}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  />
                  <p className="text-xs text-gray-500 mt-1">Минимальная сила сигнала для анализа</p>
                </div>
              </div>

              <div className="p-4 bg-green-50 rounded-lg">
                <h4 className="font-medium text-green-900 mb-2">📊 Как это работает</h4>
                <ul className="text-sm text-green-700 space-y-1">
                  <li>• <strong>FVG:</strong> Ищет разрывы между high/low соседних свечей</li>
                  <li>• <strong>OB:</strong> Определяет последние противоположные свечи перед сильным движением</li>
                  <li>• <strong>BB:</strong> Находит пробитые уровни с последующим возвратом</li>
                  <li>• Сигналы отображаются в отдельной вкладке "Smart Money"</li>
                </ul>
              </div>
            </div>
          )}

          {/* Orderbook Settings */}
          {activeTab === 'orderbook' && (
            <div className="space-y-6">
              <h3 className="text-lg font-semibold text-gray-900">Настройки стакана заявок</h3>
              
              <div className="p-4 bg-blue-50 rounded-lg mb-6">
                <h4 className="font-medium text-blue-900 mb-2">📋 Анализ стакана заявок</h4>
                <p className="text-sm text-blue-700">
                  Получение и анализ данных стакана заявок с биржи Bybit для более глубокого понимания рыночной ситуации.
                  Снимки стакана сохраняются в момент срабатывания алертов.
                </p>
              </div>
              
              <div className="space-y-4">
                <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                  <div>
                    <h4 className="font-medium text-gray-900">Анализ стакана заявок</h4>
                    <p className="text-sm text-gray-600">Включить получение данных стакана с биржи Bybit</p>
                  </div>
                  <label className="relative inline-flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={localSettings.orderbook.enabled}
                      onChange={(e) => updateOrderbookSettings('enabled', e.target.checked)}
                      className="sr-only peer"
                    />
                    <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                  </label>
                </div>

                <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                  <div>
                    <h4 className="font-medium text-gray-900">Снимок при алерте</h4>
                    <p className="text-sm text-gray-600">Автоматически сохранять снимок стакана при срабатывании алерта</p>
                  </div>
                  <label className="relative inline-flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={localSettings.orderbook.snapshot_on_alert}
                      onChange={(e) => updateOrderbookSettings('snapshot_on_alert', e.target.checked)}
                      disabled={!localSettings.orderbook.enabled}
                      className="sr-only peer"
                    />
                    <div className={`w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600 ${!localSettings.orderbook.enabled ? 'opacity-50 cursor-not-allowed' : ''}`}></div>
                  </label>
                </div>
              </div>

              <div className="p-4 bg-yellow-50 rounded-lg">
                <h4 className="font-medium text-yellow-900 mb-2">⚠️ Важная информация</h4>
                <ul className="text-sm text-yellow-700 space-y-1">
                  <li>• Анализ стакана увеличивает нагрузку на API биржи</li>
                  <li>• Может замедлить работу системы при большом количестве пар</li>
                  <li>• Снимки стакана отображаются в модальном окне графика</li>
                  <li>• Рекомендуется использовать только при необходимости</li>
                </ul>
              </div>

              <div className="p-4 bg-green-50 rounded-lg">
                <h4 className="font-medium text-green-900 mb-2">📈 Что вы получите</h4>
                <ul className="text-sm text-green-700 space-y-1">
                  <li>• Топ-25 заявок на покупку и продажу</li>
                  <li>• Точное время снимка стакана</li>
                  <li>• Анализ дисбаланса спроса и предложения</li>
                  <li>• Дополнительный контекст для принятия решений</li>
                </ul>
              </div>
            </div>
          )}

          {/* Trading Settings */}
          {activeTab === 'trading' && (
            <div className="space-y-6">
              <h3 className="text-lg font-semibold text-gray-900">Настройки торговли</h3>
              
              <div className="p-4 bg-green-50 rounded-lg mb-6">
                <h4 className="font-medium text-green-900 mb-2 flex items-center">
                  <DollarSign className="w-5 h-5 mr-2" />
                  Настройки торговли
                </h4>
                <p className="text-sm text-green-700">
                  Настройте параметры бумажной и реальной торговли. Бумажная торговля позволяет практиковаться без риска реальных денег.
                </p>
              </div>
              
              {/* Бумажная торговля */}
              <div className="border border-gray-200 rounded-lg p-4">
                <h4 className="font-medium text-gray-900 mb-4">Бумажная торговля</h4>
                
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Баланс аккаунта
                    </label>
                    <div className="relative">
                      <span className="absolute left-3 top-2 text-gray-500">$</span>
                      <input
                        type="number"
                        step="1"
                        min="100"
                        value={localSettings.trading.account_balance}
                        onChange={(e) => updateTradingSettings('account_balance', parseFloat(e.target.value))}
                        className="w-full border border-gray-300 rounded-lg pl-8 pr-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                      />
                    </div>
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Максимальный риск на сделку (%)
                    </label>
                    <div className="relative">
                      <input
                        type="number"
                        step="0.1"
                        min="0.1"
                        max="100"
                        value={localSettings.trading.max_risk_per_trade}
                        onChange={(e) => updateTradingSettings('max_risk_per_trade', parseFloat(e.target.value))}
                        className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                      />
                      <span className="absolute right-3 top-2 text-gray-500">%</span>
                    </div>
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Максимум открытых сделок
                    </label>
                    <input
                      type="number"
                      step="1"
                      min="1"
                      max="100"
                      value={localSettings.trading.max_open_trades}
                      onChange={(e) => updateTradingSettings('max_open_trades', parseInt(e.target.value))}
                      className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    />
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Стоп-лосс по умолчанию (%)
                    </label>
                    <div className="relative">
                      <input
                        type="number"
                        step="0.1"
                        min="0.1"
                        max="50"
                        value={localSettings.trading.default_stop_loss_percentage}
                        onChange={(e) => updateTradingSettings('default_stop_loss_percentage', parseFloat(e.target.value))}
                        className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                      />
                      <span className="absolute right-3 top-2 text-gray-500">%</span>
                    </div>
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Тейк-профит по умолчанию (%)
                    </label>
                    <div className="relative">
                      <input
                        type="number"
                        step="0.1"
                        min="0.1"
                        max="100"
                        value={localSettings.trading.default_take_profit_percentage}
                        onChange={(e) => updateTradingSettings('default_take_profit_percentage', parseFloat(e.target.value))}
                        className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                      />
                      <span className="absolute right-3 top-2 text-gray-500">%</span>
                    </div>
                  </div>
                  
                  <div className="flex items-center space-x-3 pt-2">
                    <input
                      type="checkbox"
                      id="auto_calculate"
                      checked={localSettings.trading.auto_calculate_quantity}
                      onChange={(e) => updateTradingSettings('auto_calculate_quantity', e.target.checked)}
                      className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                    />
                    <label htmlFor="auto_calculate" className="text-sm text-gray-700">
                      Автоматически рассчитывать количество на основе риска
                    </label>
                  </div>
                </div>
              </div>
              
              {/* Реальная торговля */}
              <div className="border border-gray-200 rounded-lg p-4">
                <div className="flex items-center justify-between mb-4">
                  <h4 className="font-medium text-gray-900">Реальная торговля</h4>
                  <label className="relative inline-flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={localSettings.trading.enable_real_trading}
                      onChange={(e) => updateTradingSettings('enable_real_trading', e.target.checked)}
                      className="sr-only peer"
                    />
                    <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-red-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-red-600"></div>
                  </label>
                </div>
                
                {localSettings.trading.enable_real_trading && (
                  <div className="bg-red-50 p-4 rounded-lg mb-4">
                    <div className="flex items-start space-x-3">
                      <AlertTriangle className="w-5 h-5 text-red-600 mt-0.5" />
                      <div>
                        <h5 className="font-medium text-red-900">Внимание! Реальная торговля включена</h5>
                        <p className="text-sm text-red-700 mt-1">
                          Вы включили режим реальной торговли с использованием API ключей. 
                          Это означает, что система сможет открывать и закрывать сделки с реальными деньгами.
                          Убедитесь, что вы понимаете риски и правильно настроили параметры торговли.
                        </p>
                      </div>
                    </div>
                  </div>
                )}
                
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      API ключ Bybit
                    </label>
                    <input
                      type="text"
                      value={localSettings.trading.api_key || ''}
                      onChange={(e) => updateTradingSettings('api_key', e.target.value)}
                      className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                      placeholder="Введите API ключ"
                    />
                    <p className="text-xs text-gray-500 mt-1">API ключ от вашего аккаунта Bybit</p>
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      API секрет Bybit
                    </label>
                    <div className="relative">
                      <input
                        type={showApiSecret ? "text" : "password"}
                        value={localSettings.trading.api_secret || ''}
                        onChange={(e) => updateTradingSettings('api_secret', e.target.value)}
                        className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                        placeholder="Введите API секрет"
                      />
                      <button
                        type="button"
                        onClick={() => setShowApiSecret(!showApiSecret)}
                        className="absolute right-3 top-2 text-gray-500 hover:text-gray-700"
                      >
                        {showApiSecret ? 'Скрыть' : 'Показать'}
                      </button>
                    </div>
                    <p className="text-xs text-gray-500 mt-1">API секрет от вашего аккаунта Bybit</p>
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Кредитное плечо по умолчанию
                    </label>
                    <input
                      type="number"
                      min="1"
                      max="100"
                      value={localSettings.trading.default_leverage || 1}
                      onChange={(e) => updateTradingSettings('default_leverage', parseInt(e.target.value))}
                      className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    />
                    <p className="text-xs text-gray-500 mt-1">Кредитное плечо для новых сделок</p>
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Тип маржи по умолчанию
                    </label>
                    <select
                      value={localSettings.trading.default_margin_type || 'isolated'}
                      onChange={(e) => updateTradingSettings('default_margin_type', e.target.value)}
                      className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    >
                      <option value="isolated">Изолированная</option>
                      <option value="cross">Кросс</option>
                    </select>
                    <p className="text-xs text-gray-500 mt-1">Тип маржи для новых сделок</p>
                  </div>
                </div>
                
                <div className="mt-4 flex items-center space-x-3">
                  <input
                    type="checkbox"
                    id="confirm_trades"
                    checked={localSettings.trading.confirm_trades}
                    onChange={(e) => updateTradingSettings('confirm_trades', e.target.checked)}
                    className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                  />
                  <label htmlFor="confirm_trades" className="text-sm text-gray-700">
                    Запрашивать подтверждение перед открытием реальных сделок
                  </label>
                </div>
                
                {/* Тест API подключения */}
                <div className="mt-4">
                  <button
                    onClick={testApiConnection}
                    disabled={!localSettings.trading.api_key || !localSettings.trading.api_secret || testApiStatus === 'loading'}
                    className="flex items-center space-x-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 text-white px-4 py-2 rounded-lg transition-colors"
                  >
                    {testApiStatus === 'loading' ? (
                      <RefreshCw className="w-5 h-5 animate-spin" />
                    ) : (
                      <Shield className="w-5 h-5" />
                    )}
                    <span>Проверить API подключение</span>
                  </button>
                  
                  {testApiStatus !== 'idle' && (
                    <div className={`mt-3 p-3 rounded-lg ${
                      testApiStatus === 'success' ? 'bg-green-50 text-green-700' : 
                      testApiStatus === 'error' ? 'bg-red-50 text-red-700' : 
                      'bg-blue-50 text-blue-700'
                    }`}>
                      {testApiMessage}
                    </div>
                  )}
                </div>
                
                <div className="mt-4 p-4 bg-yellow-50 rounded-lg">
                  <h5 className="font-medium text-yellow-900 mb-2">⚠️ Важная информация о безопасности</h5>
                  <ul className="text-sm text-yellow-700 space-y-1">
                    <li>• API ключи хранятся только на вашем устройстве и не передаются третьим лицам</li>
                    <li>• Рекомендуется создать отдельный API ключ с ограниченными правами только для торговли</li>
                    <li>• Не включайте права на вывод средств в настройках API ключа</li>
                    <li>• Ограничьте доступ API ключа по IP-адресу для дополнительной безопасности</li>
                  </ul>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between p-6 border-t border-gray-200 bg-gray-50">
          <div className="text-sm text-gray-600">
            Изменения применятся после сохранения и перезапуска системы
          </div>
          
          <div className="flex items-center space-x-3">
            <button
              onClick={onClose}
              className="px-4 py-2 text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
            >
              Отмена
            </button>
            
            <button
              onClick={handleSave}
              disabled={loading}
              className="flex items-center space-x-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white rounded-lg transition-colors"
            >
              {loading ? (
                <RefreshCw className="w-4 h-4 animate-spin" />
              ) : (
                <Save className="w-4 h-4" />
              )}
              <span>{loading ? 'Сохранение...' : 'Сохранить'}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SettingsModal;