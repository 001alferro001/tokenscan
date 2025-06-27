import React, { useState, useEffect } from 'react';
import { X, ExternalLink, Download } from 'lucide-react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  TimeScale,
  BarElement,
  LineElement,
  PointElement,
  Title,
  Tooltip,
  Legend,
  ChartOptions
} from 'chart.js';
import { Chart } from 'react-chartjs-2';
import 'chartjs-adapter-date-fns';
import annotationPlugin from 'chartjs-plugin-annotation';
import { CandlestickController, CandlestickElement } from 'chartjs-chart-financial';

ChartJS.register(
  CategoryScale,
  LinearScale,
  TimeScale,
  BarElement,
  LineElement,
  PointElement,
  Title,
  Tooltip,
  Legend,
  annotationPlugin,
  CandlestickController,
  CandlestickElement
);

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

interface ChartData {
  timestamp: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  volume_usdt: number;
  is_long: boolean;
}

interface SmartMoneyChartModalProps {
  alert: SmartMoneyAlert;
  onClose: () => void;
}

const SmartMoneyChartModal: React.FC<SmartMoneyChartModalProps> = ({ alert, onClose }) => {
  const [chartData, setChartData] = useState<ChartData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadChartData();
  }, [alert]);

  const loadChartData = async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await fetch(`/api/chart-data/${alert.symbol}?hours=1&alert_time=${alert.timestamp}`);
      
      if (!response.ok) {
        throw new Error('Ошибка загрузки данных графика');
      }

      const data = await response.json();
      setChartData(data.chart_data || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Неизвестная ошибка');
    } finally {
      setLoading(false);
    }
  };

  const openTradingView = () => {
    const cleanSymbol = alert.symbol.replace('USDT', '');
    const url = `https://www.tradingview.com/chart/?symbol=BYBIT:${cleanSymbol}USDT.P&interval=1`;
    window.open(url, '_blank');
  };

  const downloadChart = () => {
    const csvContent = [
      'Timestamp,Open,High,Low,Close,Volume,Volume_USDT,Is_Long',
      ...chartData.map(d => 
        `${new Date(d.timestamp).toISOString()},${d.open},${d.high},${d.low},${d.close},${d.volume},${d.volume_usdt},${d.is_long}`
      )
    ].join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${alert.symbol}_smart_money_chart.csv`;
    a.click();
    window.URL.revokeObjectURL(url);
  };

  const getMainChartConfig = () => {
    if (chartData.length === 0) return null;

    const alertTime = new Date(alert.timestamp).getTime();

    // Создаем свечные данные
    const candleData = chartData.map(d => ({
      x: d.timestamp,
      o: d.open,
      h: d.high,
      l: d.low,
      c: d.close
    }));

    // Отметка Smart Money сигнала
    const smartMoneyPoints = [{
      x: alertTime,
      y: alert.price
    }];

    // Аннотации для Smart Money паттернов
    const annotations: any = {};
    
    if (alert.top && alert.bottom) {
      // Линии границ паттерна
      annotations.patternTop = {
        type: 'line',
        xMin: alertTime,
        xMax: alertTime + 300000, // 5 минут вправо
        yMin: alert.top,
        yMax: alert.top,
        borderColor: alert.direction === 'bullish' ? 'rgb(34, 197, 94)' : 'rgb(239, 68, 68)',
        borderWidth: 2,
        borderDash: [3, 3],
        label: {
          content: `${alert.type.toUpperCase()} TOP`,
          enabled: true,
          position: 'end',
          backgroundColor: alert.direction === 'bullish' ? 'rgb(34, 197, 94)' : 'rgb(239, 68, 68)',
          color: 'white',
          padding: 4
        }
      };

      annotations.patternBottom = {
        type: 'line',
        xMin: alertTime,
        xMax: alertTime + 300000, // 5 минут вправо
        yMin: alert.bottom,
        yMax: alert.bottom,
        borderColor: alert.direction === 'bullish' ? 'rgb(34, 197, 94)' : 'rgb(239, 68, 68)',
        borderWidth: 2,
        borderDash: [3, 3],
        label: {
          content: `${alert.type.toUpperCase()} BOTTOM`,
          enabled: true,
          position: 'end',
          backgroundColor: alert.direction === 'bullish' ? 'rgb(34, 197, 94)' : 'rgb(239, 68, 68)',
          color: 'white',
          padding: 4
        }
      };

      // Зона паттерна
      annotations.patternZone = {
        type: 'box',
        xMin: alertTime,
        xMax: alertTime + 300000,
        yMin: alert.bottom,
        yMax: alert.top,
        backgroundColor: alert.direction === 'bullish' ? 'rgba(34, 197, 94, 0.1)' : 'rgba(239, 68, 68, 0.1)',
        borderColor: 'transparent'
      };
    }

    const data = {
      datasets: [
        {
          label: 'Свечи',
          data: candleData,
          type: 'candlestick' as const,
          color: {
            up: 'rgb(34, 197, 94)',
            down: 'rgb(239, 68, 68)',
            unchanged: 'rgb(156, 163, 175)'
          }
        },
        {
          label: 'Smart Money Signal',
          data: smartMoneyPoints,
          type: 'scatter' as const,
          backgroundColor: alert.direction === 'bullish' ? 'rgb(34, 197, 94)' : 'rgb(239, 68, 68)',
          borderColor: alert.direction === 'bullish' ? 'rgb(21, 128, 61)' : 'rgb(185, 28, 28)',
          pointRadius: 10,
          pointHoverRadius: 12
        }
      ]
    };

    const options: ChartOptions = {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        mode: 'index' as const,
        intersect: false,
      },
      plugins: {
        title: {
          display: true,
          text: `${alert.symbol} - Smart Money: ${alert.type.replace('_', ' ').toUpperCase()}`,
          color: '#374151'
        },
        legend: {
          labels: {
            color: '#374151'
          }
        },
        tooltip: {
          callbacks: {
            title: (context) => {
              return new Date(context[0].parsed.x).toLocaleString('ru-RU');
            },
            label: (context) => {
              if (context.datasetIndex === 0) {
                const candle = chartData.find(d => d.timestamp === context.parsed.x);
                if (candle) {
                  return [
                    `Open: $${candle.open.toFixed(8)}`,
                    `High: $${candle.high.toFixed(8)}`,
                    `Low: $${candle.low.toFixed(8)}`,
                    `Close: $${candle.close.toFixed(8)}`,
                    `Type: ${candle.is_long ? 'LONG' : 'SHORT'}`
                  ];
                }
              } else if (context.datasetIndex === 1) {
                return [
                  `Smart Money: ${alert.type.replace('_', ' ').toUpperCase()}`,
                  `Direction: ${alert.direction.toUpperCase()}`,
                  `Strength: ${alert.strength.toFixed(2)}%`,
                  `Price: $${context.parsed.y.toFixed(8)}`
                ];
              }
              return '';
            }
          }
        },
        annotation: {
          annotations
        }
      },
      scales: {
        x: {
          type: 'time',
          time: {
            unit: 'minute',
            displayFormats: {
              minute: 'HH:mm'
            }
          },
          ticks: {
            color: '#6B7280'
          },
          grid: {
            color: 'rgba(107, 114, 128, 0.1)'
          }
        },
        y: {
          type: 'linear',
          ticks: {
            color: '#6B7280',
            callback: function(value) {
              return '$' + Number(value).toFixed(8);
            }
          },
          grid: {
            color: 'rgba(107, 114, 128, 0.1)'
          }
        }
      }
    };

    return { data, options };
  };

  const getVolumeChartConfig = () => {
    if (chartData.length === 0) return null;

    const volumeData = chartData.map(d => ({
      x: d.timestamp,
      y: d.volume_usdt
    }));

    const data = {
      datasets: [
        {
          label: 'Объем (USDT)',
          data: volumeData,
          type: 'bar' as const,
          backgroundColor: chartData.map(d => d.is_long ? 'rgba(34, 197, 94, 0.6)' : 'rgba(239, 68, 68, 0.6)'),
          borderColor: chartData.map(d => d.is_long ? 'rgb(34, 197, 94)' : 'rgb(239, 68, 68)'),
          borderWidth: 1
        }
      ]
    };

    const options: ChartOptions = {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        title: {
          display: true,
          text: 'Объем торгов',
          color: '#374151'
        },
        legend: {
          display: false
        },
        tooltip: {
          callbacks: {
            title: (context) => {
              return new Date(context[0].parsed.x).toLocaleString('ru-RU');
            },
            label: (context) => {
              const num = Number(context.parsed.y);
              if (num >= 1000000) {
                return `Объем: $${(num / 1000000).toFixed(1)}M`;
              } else if (num >= 1000) {
                return `Объем: $${(num / 1000).toFixed(1)}K`;
              }
              return `Объем: $${num.toFixed(0)}`;
            }
          }
        }
      },
      scales: {
        x: {
          type: 'time',
          time: {
            unit: 'minute',
            displayFormats: {
              minute: 'HH:mm'
            }
          },
          ticks: {
            color: '#6B7280'
          },
          grid: {
            color: 'rgba(107, 114, 128, 0.1)'
          }
        },
        y: {
          type: 'linear',
          ticks: {
            color: '#6B7280',
            callback: function(value) {
              const num = Number(value);
              if (num >= 1000000) {
                return '$' + (num / 1000000).toFixed(1) + 'M';
              } else if (num >= 1000) {
                return '$' + (num / 1000).toFixed(1) + 'K';
              }
              return '$' + num.toFixed(0);
            }
          },
          grid: {
            color: 'rgba(107, 114, 128, 0.1)'
          }
        }
      }
    };

    return { data, options };
  };

  const mainChartConfig = getMainChartConfig();
  const volumeChartConfig = getVolumeChartConfig();

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-lg w-full max-w-[95vw] h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200">
          <div>
            <h2 className="text-2xl font-bold text-gray-900">{alert.symbol}</h2>
            <p className="text-gray-600">
              Smart Money: {alert.type.replace('_', ' ').toUpperCase()} • {new Date(alert.timestamp).toLocaleString('ru-RU')}
            </p>
            <div className="flex items-center space-x-4 mt-2">
              <span className={`px-3 py-1 rounded-full text-sm font-medium ${
                alert.direction === 'bullish' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
              }`}>
                {alert.direction === 'bullish' ? 'Бычий' : 'Медвежий'}
              </span>
              <span className="text-sm text-gray-600">
                Сила: <span className="font-semibold text-purple-600">{alert.strength.toFixed(2)}%</span>
              </span>
            </div>
          </div>
          
          <div className="flex items-center space-x-3">
            <button
              onClick={downloadChart}
              className="flex items-center space-x-2 bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded-lg transition-colors"
            >
              <Download className="w-4 h-4" />
              <span>Скачать</span>
            </button>
            
            <button
              onClick={openTradingView}
              className="flex items-center space-x-2 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg transition-colors"
            >
              <ExternalLink className="w-4 h-4" />
              <span>TradingView</span>
            </button>
            
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600 p-2"
            >
              <X className="w-6 h-6" />
            </button>
          </div>
        </div>

        {/* Chart Content */}
        <div className="flex-1 p-6 overflow-hidden">
          {loading ? (
            <div className="flex items-center justify-center h-full">
              <div className="text-center">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto mb-4"></div>
                <p className="text-gray-600">Загрузка данных графика...</p>
              </div>
            </div>
          ) : error ? (
            <div className="flex items-center justify-center h-full">
              <div className="text-center">
                <p className="text-red-600 mb-4">Ошибка: {error}</p>
                <button
                  onClick={loadChartData}
                  className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg transition-colors"
                >
                  Попробовать снова
                </button>
              </div>
            </div>
          ) : mainChartConfig && volumeChartConfig ? (
            <div className="h-full flex flex-col">
              {/* Основной график свечей */}
              <div className="flex-1 min-h-0 mb-4">
                <Chart type="candlestick" data={mainChartConfig.data} options={mainChartConfig.options} />
              </div>
              
              {/* График объемов */}
              <div className="h-48 border-t border-gray-200 pt-4">
                <Chart type="bar" data={volumeChartConfig.data} options={volumeChartConfig.options} />
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-center h-full">
              <p className="text-gray-600">Нет данных для отображения</p>
            </div>
          )}
        </div>

        {/* Pattern Info */}
        <div className="p-6 border-t border-gray-200 bg-gray-50">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div>
              <span className="text-gray-600">Паттерн:</span>
              <span className="ml-2 text-gray-900 font-medium">
                {alert.type === 'fair_value_gap' && 'Fair Value Gap'}
                {alert.type === 'order_block' && 'Order Block'}
                {alert.type === 'breaker_block' && 'Breaker Block'}
              </span>
            </div>
            <div>
              <span className="text-gray-600">Направление:</span>
              <span className={`ml-2 font-medium ${
                alert.direction === 'bullish' ? 'text-green-600' : 'text-red-600'
              }`}>
                {alert.direction === 'bullish' ? 'Бычий' : 'Медвежий'}
              </span>
            </div>
            <div>
              <span className="text-gray-600">Сила сигнала:</span>
              <span className="ml-2 text-purple-600 font-semibold">{alert.strength.toFixed(2)}%</span>
            </div>
            <div>
              <span className="text-gray-600">Цена:</span>
              <span className="ml-2 text-gray-900 font-mono">${alert.price.toFixed(8)}</span>
            </div>
          </div>
          
          {/* Pattern boundaries */}
          {alert.top && alert.bottom && (
            <div className="mt-4 p-4 bg-white rounded-lg border border-gray-200">
              <div className="text-sm font-medium text-gray-700 mb-2">Границы паттерна:</div>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-gray-600">Верхняя граница:</span>
                  <div className="text-gray-900 font-mono">${alert.top.toFixed(8)}</div>
                </div>
                <div>
                  <span className="text-gray-600">Нижняя граница:</span>
                  <div className="text-gray-900 font-mono">${alert.bottom.toFixed(8)}</div>
                </div>
              </div>
            </div>
          )}

          {/* Pattern explanation */}
          <div className="mt-4 p-4 bg-blue-50 rounded-lg">
            <div className="text-sm font-medium text-blue-900 mb-2">Объяснение паттерна:</div>
            <div className="text-sm text-blue-700">
              {alert.type === 'fair_value_gap' && (
                <p>Fair Value Gap - разрыв в ценах между свечами, указывающий на дисбаланс спроса и предложения. Часто цена возвращается для заполнения этого разрыва.</p>
              )}
              {alert.type === 'order_block' && (
                <p>Order Block - зона накопления крупных заявок институциональных игроков. Эти уровни часто выступают как сильная поддержка или сопротивление.</p>
              )}
              {alert.type === 'breaker_block' && (
                <p>Breaker Block - пробитый уровень поддержки/сопротивления, который меняет свою роль. Бывшая поддержка становится сопротивлением и наоборот.</p>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SmartMoneyChartModal;