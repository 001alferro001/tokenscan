import React, { useState, useEffect } from 'react';
import { X, Save, RefreshCw } from 'lucide-react';

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
}

interface SettingsModalProps {
  settings: Settings | null;
  onClose: () => void;
  onSave: (settings: Settings) => void;
}

const SettingsModal: React.FC<SettingsModalProps> = ({ settings, onClose, onSave }) => {
  const [localSettings, setLocalSettings] = useState<Settings | null>(null);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<'volume' | 'alerts' | 'imbalance' | 'orderbook'>('volume');

  useEffect(() => {
    if (settings) {
      setLocalSettings(JSON.parse(JSON.stringify(settings)));
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
              { id: 'imbalance', label: 'Имбаланс' },
              { id: 'orderbook', label: 'Стакан заявок' }
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

          {/* Imbalance Settings */}
          {activeTab === 'imbalance' && (
            <div className="space-y-6">
              <h3 className="text-lg font-semibold text-gray-900">Настройки анализа имбаланса (Smart Money)</h3>
              
              <div className="space-y-4">
                <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                  <div>
                    <h4 className="font-medium text-gray-900">Fair Value Gap</h4>
                    <p className="text-sm text-gray-600">Анализ разрывов в ценах между свечами</p>
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
                    <h4 className="font-medium text-gray-900">Order Block</h4>
                    <p className="text-sm text-gray-600">Анализ блоков заявок институциональных игроков</p>
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
                    <h4 className="font-medium text-gray-900">Breaker Block</h4>
                    <p className="text-sm text-gray-600">Анализ пробитых уровней поддержки/сопротивления</p>
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
            </div>
          )}

          {/* Orderbook Settings */}
          {activeTab === 'orderbook' && (
            <div className="space-y-6">
              <h3 className="text-lg font-semibold text-gray-900">Настройки стакана заявок</h3>
              
              <div className="space-y-4">
                <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                  <div>
                    <h4 className="font-medium text-gray-900">Анализ стакана заявок</h4>
                    <p className="text-sm text-gray-600">Включить получение данных стакана с биржи</p>
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
                    <p className="text-sm text-gray-600">Сохранять снимок стакана при срабатывании алерта</p>
                  </div>
                  <label className="relative inline-flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={localSettings.orderbook.snapshot_on_alert}
                      onChange={(e) => updateOrderbookSettings('snapshot_on_alert', e.target.checked)}
                      className="sr-only peer"
                    />
                    <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                  </label>
                </div>
              </div>

              <div className="p-4 bg-yellow-50 rounded-lg">
                <h4 className="font-medium text-yellow-900 mb-2">⚠️ Внимание</h4>
                <p className="text-sm text-yellow-700">
                  Анализ стакана заявок увеличивает нагрузку на API биржи и может замедлить работу системы.
                  Используйте только при необходимости детального анализа.
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between p-6 border-t border-gray-200 bg-gray-50">
          <div className="text-sm text-gray-600">
            Изменения применятся после сохранения
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