import React, { useState, useEffect } from 'react';
import { X, ExternalLink, Download, Clock, Globe, Info } from 'lucide-react';
import TradingViewChart from './TradingViewChart';
import CoinGeckoChart from './CoinGeckoChart';
import ChartModal from './ChartModal';

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

interface SmartMoneyChartModalProps {
  alert: SmartMoneyAlert;
  onClose: () => void;
}

type ChartType = 'tradingview' | 'coingecko' | 'internal' | null;

const SmartMoneyChartModal: React.FC<SmartMoneyChartModalProps> = ({ alert, onClose }) => {
  const [selectedChart, setSelectedChart] = useState<ChartType>(null);
  const [relatedAlerts, setRelatedAlerts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadRelatedAlerts();
  }, [alert.symbol]);

  const loadRelatedAlerts = async () => {
    try {
      setLoading(true);
      
      // Загружаем все алерты для данного символа за последние 24 часа
      const response = await fetch(`/api/alerts/symbol/${alert.symbol}?hours=24`);
      if (response.ok) {
        const data = await response.json();
        setRelatedAlerts(data.alerts || []);
      } else {
        // Fallback - загружаем все алерты и фильтруем
        const allResponse = await fetch('/api/alerts/all');
        if (allResponse.ok) {
          const allData = await allResponse.json();
          
          // Объединяем все типы алертов
          const allAlerts = [
            ...(allData.volume_alerts || []),
            ...(allData.consecutive_alerts || []),
            ...(allData.priority_alerts || [])
          ];
          
          // Фильтруем по символу и времени (последние 24 часа)
          const oneDayAgo = Date.now() - (24 * 60 * 60 * 1000);
          const symbolAlerts = allAlerts.filter((a: any) => {
            if (a.symbol !== alert.symbol) return false;
            
            const alertTime = typeof a.timestamp === 'number' ? a.timestamp : new Date(a.timestamp).getTime();
            return alertTime > oneDayAgo;
          });
          
          setRelatedAlerts(symbolAlerts);
        }
      }
    } catch (error) {
      console.error('Ошибка загрузки связанных алертов:', error);
    } finally {
      setLoading(false);
    }
  };

  // Преобразуем Smart Money алерт в формат обычного алерта для TradingView
  const convertedAlert = {
    id: alert.id,
    symbol: alert.symbol,
    alert_type: 'smart_money',
    price: alert.price,
    timestamp: alert.timestamp,
    close_timestamp: alert.timestamp,
    has_imbalance: true,
    imbalance_data: {
      type: alert.type,
      direction: alert.direction,
      strength: alert.strength,
      top: alert.top,
      bottom: alert.bottom
    }
  };

  if (selectedChart === 'tradingview') {
    return (
      <TradingViewChart
        symbol={alert.symbol}
        alertPrice={alert.price}
        alertTime={alert.timestamp}
        alerts={[convertedAlert, ...relatedAlerts]}
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
        alert={convertedAlert}
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
            <h2 className="text-2xl font-bold text-gray-900">Smart Money: {alert.symbol}</h2>
            <p className="text-gray-600">
              {alert.type.replace('_', ' ').toUpperCase()} • {alert.direction === 'bullish' ? 'Бычий' : 'Медвежий'} • ${alert.price.toFixed(6)}
            </p>
            <p className="text-sm text-purple-600 mt-1">
              Сила сигнала: {alert.strength.toFixed(2)}% • {loading ? 'Загрузка...' : `${relatedAlerts.length} связанных алертов`}
            </p>
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
                <Globe className="w-6 h-6 text-blue-600" />
              </div>
              <div className="flex-1 text-left">
                <h3 className="text-lg font-semibold text-gray-900">TradingView с Smart Money зонами</h3>
                <p className="text-gray-600">
                  Профессиональные графики с отметками Smart Money концепций
                </p>
                <div className="flex items-center space-x-4 mt-2 text-sm text-gray-500">
                  <span>✓ Реальное время</span>
                  <span>✓ Smart Money зоны</span>
                  <span>✓ Все сигналы программы</span>
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
                <ExternalLink className="w-6 h-6 text-green-600" />
              </div>
              <div className="flex-1 text-left">
                <h3 className="text-lg font-semibold text-gray-900">CoinGecko</h3>
                <p className="text-gray-600">
                  Рыночные данные и долгосрочные графики
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
                <Info className="w-6 h-6 text-purple-600" />
              </div>
              <div className="flex-1 text-left">
                <h3 className="text-lg font-semibold text-gray-900">Внутренний график</h3>
                <p className="text-gray-600">
                  График на основе собранных данных с Smart Money анализом
                </p>
                <div className="flex items-center space-x-4 mt-2 text-sm text-gray-500">
                  <span>✓ Данные алертов</span>
                  <span>✓ Smart Money зоны</span>
                  <span>✓ Детальный анализ</span>
                </div>
              </div>
            </div>
          </button>
        </div>

        {/* Footer */}
        <div className="p-6 border-t border-gray-200 bg-gray-50">
          <div className="text-sm text-gray-600">
            <p className="mb-2">
              <strong>🧠 Smart Money Concepts:</strong> Анализ институциональной торговли
            </p>
            <div className="grid grid-cols-3 gap-4 text-xs">
              <div>
                <span className="text-blue-600">Fair Value Gap</span> - разрывы в ценах
              </div>
              <div>
                <span className="text-green-600">Order Block</span> - зоны накопления
              </div>
              <div>
                <span className="text-red-600">Breaker Block</span> - пробитые уровни
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SmartMoneyChartModal;