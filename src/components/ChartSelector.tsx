import React, { useState, useEffect } from 'react';
import { BarChart3, TrendingUp, Globe, X, Target } from 'lucide-react';
import TradingViewChart from './TradingViewChart';
import CoinGeckoChart from './CoinGeckoChart';
import ChartModal from './ChartModal';

interface Alert {
  id: number;
  symbol: string;
  alert_type: string;
  price: number;
  timestamp: number | string;
  close_timestamp?: number | string;
  preliminary_alert?: Alert;
  has_imbalance?: boolean;
  imbalance_data?: any;
  candle_data?: any;
  order_book_snapshot?: any;
  volume_ratio?: number;
  consecutive_count?: number;
}

interface ChartSelectorProps {
  alert: Alert;
  onClose: () => void;
}

type ChartType = 'tradingview' | 'coingecko' | 'internal' | null;

const ChartSelector: React.FC<ChartSelectorProps> = ({ alert, onClose }) => {
  const [selectedChart, setSelectedChart] = useState<ChartType>(null);
  const [relatedAlerts, setRelatedAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadRelatedAlerts();
  }, [alert.symbol]);

  const loadRelatedAlerts = async () => {
    try {
      setLoading(true);
      
      // Загружаем все алерты для данного символа за последние 24 часа
      const response = await fetch('/api/alerts/all');
      if (response.ok) {
        const data = await response.json();
        
        // Объединяем все типы алертов
        const allAlerts = [
          ...(data.volume_alerts || []),
          ...(data.consecutive_alerts || []),
          ...(data.priority_alerts || [])
        ];
        
        // Фильтруем по символу и времени (последние 24 часа)
        const oneDayAgo = Date.now() - (24 * 60 * 60 * 1000);
        const symbolAlerts = allAlerts.filter((a: Alert) => {
          if (a.symbol !== alert.symbol) return false;
          
          const alertTime = typeof a.timestamp === 'number' ? a.timestamp : new Date(a.timestamp).getTime();
          return alertTime > oneDayAgo;
        });
        
        // Сортируем по времени
        symbolAlerts.sort((a: Alert, b: Alert) => {
          const timeA = typeof a.timestamp === 'number' ? a.timestamp : new Date(a.timestamp).getTime();
          const timeB = typeof b.timestamp === 'number' ? b.timestamp : new Date(b.timestamp).getTime();
          return timeA - timeB;
        });
        
        setRelatedAlerts(symbolAlerts);
      }
    } catch (error) {
      console.error('Ошибка загрузки связанных алертов:', error);
    } finally {
      setLoading(false);
    }
  };

  if (selectedChart === 'tradingview') {
    return (
      <TradingViewChart
        symbol={alert.symbol}
        alertPrice={alert.price}
        alertTime={alert.close_timestamp || alert.timestamp}
        alerts={relatedAlerts}
        onClose={onClose}
      />
    );
  }

  if (selectedChart === 'coingecko') {
    return (
      <CoinGeckoChart
        symbol={alert.symbol}
        onClose={onClose}
      />
    );
  }

  if (selectedChart === 'internal') {
    return (
      <ChartModal
        alert={alert}
        onClose={onClose}
      />
    );
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-lg w-full max-w-2xl">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200">
          <div>
            <h2 className="text-2xl font-bold text-gray-900">Выберите источник графика</h2>
            <p className="text-gray-600">{alert.symbol} • ${alert.price.toFixed(6)}</p>
            {!loading && relatedAlerts.length > 0 && (
              <p className="text-sm text-blue-600 mt-1">
                Найдено {relatedAlerts.length} сигналов за 24 часа
              </p>
            )}
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 p-2"
          >
            <X className="w-6 h-6" />
          </button>
        </div>

        {/* Chart Options */}
        <div className="p-6 space-y-4">
          {/* TradingView */}
          <button
            onClick={() => setSelectedChart('tradingview')}
            className="w-full p-6 border-2 border-gray-200 rounded-lg hover:border-blue-500 hover:bg-blue-50 transition-all group"
          >
            <div className="flex items-center space-x-4">
              <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center group-hover:bg-blue-200">
                <TrendingUp className="w-6 h-6 text-blue-600" />
              </div>
              <div className="flex-1 text-left">
                <h3 className="text-lg font-semibold text-gray-900">TradingView с сигналами</h3>
                <p className="text-gray-600">
                  Профессиональные графики с отметками всех сигналов программы
                </p>
                <div className="flex items-center space-x-4 mt-2 text-sm text-gray-500">
                  <span>✓ Реальное время</span>
                  <span>✓ Сигналы программы</span>
                  <span>✓ Smart Money зоны</span>
                  {!loading && relatedAlerts.length > 0 && (
                    <span className="flex items-center space-x-1 text-blue-600">
                      <Target className="w-3 h-3" />
                      <span>{relatedAlerts.length} сигналов</span>
                    </span>
                  )}
                </div>
              </div>
              <div className="text-green-600 font-semibold">Рекомендуется</div>
            </div>
          </button>

          {/* CoinGecko */}
          <button
            onClick={() => setSelectedChart('coingecko')}
            className="w-full p-6 border-2 border-gray-200 rounded-lg hover:border-green-500 hover:bg-green-50 transition-all group"
          >
            <div className="flex items-center space-x-4">
              <div className="w-12 h-12 bg-green-100 rounded-lg flex items-center justify-center group-hover:bg-green-200">
                <Globe className="w-6 h-6 text-green-600" />
              </div>
              <div className="flex-1 text-left">
                <h3 className="text-lg font-semibold text-gray-900">CoinGecko</h3>
                <p className="text-gray-600">
                  Рыночные данные, статистика и долгосрочные графики
                </p>
                <div className="flex items-center space-x-4 mt-2 text-sm text-gray-500">
                  <span>✓ Рыночная капитализация</span>
                  <span>✓ Объемы торгов</span>
                  <span>✓ Исторические данные</span>
                </div>
              </div>
            </div>
          </button>

          {/* Internal Chart */}
          <button
            onClick={() => setSelectedChart('internal')}
            className="w-full p-6 border-2 border-gray-200 rounded-lg hover:border-purple-500 hover:bg-purple-50 transition-all group"
          >
            <div className="flex items-center space-x-4">
              <div className="w-12 h-12 bg-purple-100 rounded-lg flex items-center justify-center group-hover:bg-purple-200">
                <BarChart3 className="w-6 h-6 text-purple-600" />
              </div>
              <div className="flex-1 text-left">
                <h3 className="text-lg font-semibold text-gray-900">Внутренний график</h3>
                <p className="text-gray-600">
                  График на основе собранных данных с отметками алертов
                </p>
                <div className="flex items-center space-x-4 mt-2 text-sm text-gray-500">
                  <span>✓ Данные алертов</span>
                  <span>✓ Smart Money зоны</span>
                  <span>✓ Стакан заявок</span>
                </div>
              </div>
            </div>
          </button>
        </div>

        {/* Footer */}
        <div className="p-6 border-t border-gray-200 bg-gray-50">
          <div className="text-sm text-gray-600">
            <p className="mb-2">
              <strong>🎯 Новая функция:</strong> TradingView теперь показывает все сигналы программы прямо на графике!
            </p>
            <div className="grid grid-cols-3 gap-4 text-xs">
              <div>
                <span className="text-orange-600">📈 Объемные алерты</span> - оранжевые стрелки
              </div>
              <div>
                <span className="text-green-600">🕯️ LONG последовательности</span> - зеленые стрелки
              </div>
              <div>
                <span className="text-pink-600">⭐ Приоритетные</span> - розовые стрелки
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ChartSelector;