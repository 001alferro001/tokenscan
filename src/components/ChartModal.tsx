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

interface Alert {
  id: number;
  symbol: string;
  alert_type: string;
  price: number;
  timestamp: string;
  close_timestamp?: string;
  preliminary_alert?: Alert;
  has_imbalance?: boolean;
  imbalance_data?: {
    type: 'fair_value_gap' | 'order_block' | 'breaker_block';
    strength: number;
    direction: 'bullish' | 'bearish';
    top: number;
    bottom: number;
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

interface ChartModalProps {
  alert: Alert;
  onClose: () => void;
}

const ChartModal: React.FC<ChartModalProps> = ({ alert, onClose }) => {
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

      const response = await fetch(`/api/chart-data/${alert.symbol}?hours=1&alert_time=${alert.close_timestamp || alert.timestamp}`);
      
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
    a.download = `${alert.symbol}_chart_data.csv`;
    a.click();
    window.URL.revokeObjectURL(url);
  };

  const getChartConfig = () => {
    if (chartData.length === 0) return null;

    const alertTime = new Date(alert.close_timestamp || alert.timestamp).getTime();
    const preliminaryTime = alert.preliminary_alert ? new Date(alert.preliminary_alert.timestamp).getTime() : null;

    // Создаем свечные данные
    const candleData = chartData.map(d => ({
      x: d.timestamp,
      o: d.open,
      h: d.high,
      l: d.low,
      c: d.close
    }));

    // Отметки алертов
    const alertPoints = [];
    
    if (preliminaryTime) {
      alertPoints.push({
        x: preliminaryTime,
        y: alert.preliminary_alert?.price || alert.price
      });
    }
    
    alertPoints.push({
      x: alertTime,
      y: alert.price
    });

    // Уровень алерта
    let alertLevelData = [];
    if (alert.candle_data?.alert_level) {
      alertLevelData = [{
        x: alertTime,
        y: alert.candle_data.alert_level
      }];
    }

    // Аннотации для имбаланса
    const annotations: any = {};
    
    if (alert.has_imbalance && alert.imbalance_data) {
      annotations.imbalanceBox = {
        type: 'box',
        xMin: alertTime - 60000,
        xMax: alertTime + 60000,
        yMin: alert.imbalance_data.bottom,
        yMax: alert.imbalance_data.top,
        backgroundColor: alert.imbalance_data.direction === 'bullish' ? 'rgba(34, 197, 94, 0.2)' : 'rgba(239, 68, 68, 0.2)',
        borderColor: alert.imbalance_data.direction === 'bullish' ? 'rgb(34, 197, 94)' : 'rgb(239, 68, 68)',
        borderWidth: 2,
        label: {
          content: `${alert.imbalance_data.type} (${alert.imbalance_data.strength.toFixed(1)}%)`,
          enabled: true,
          position: 'topLeft'
        }
      };
    }

    // Линия уровня алерта
    if (alert.candle_data?.alert_level) {
      annotations.alertLevel = {
        type: 'line',
        yMin: alert.candle_data.alert_level,
        yMax: alert.candle_data.alert_level,
        borderColor: 'rgb(168, 85, 247)',
        borderWidth: 2,
        borderDash: [5, 5],
        label: {
          content: 'Уровень алерта',
          enabled: true,
          position: 'end'
        }
      };
    }

    // Данные стакана заявок для отображения справа
    let orderbookData = [];
    if (alert.order_book_snapshot) {
      const bids = alert.order_book_snapshot.bids.slice(0, 10);
      const asks = alert.order_book_snapshot.asks.slice(0, 10);
      
      // Добавляем точки для визуализации стакана
      bids.forEach(([price, volume]) => {
        orderbookData.push({
          x: alertTime + 120000, // Справа от графика
          y: price,
          volume: volume,
          type: 'bid'
        });
      });
      
      asks.forEach(([price, volume]) => {
        orderbookData.push({
          x: alertTime + 120000,
          y: price,
          volume: volume,
          type: 'ask'
        });
      });
    }

    const data = {
      datasets: [
        {
          label: 'Свечи',
          data: candleData,
          type: 'candlestick' as const,
          yAxisID: 'y',
          color: {
            up: 'rgb(34, 197, 94)',
            down: 'rgb(239, 68, 68)',
            unchanged: 'rgb(156, 163, 175)'
          }
        },
        {
          label: 'Алерты',
          data: alertPoints,
          type: 'scatter' as const,
          backgroundColor: 'rgb(255, 215, 0)',
          borderColor: 'rgb(255, 193, 7)',
          pointRadius: 8,
          pointHoverRadius: 10,
          yAxisID: 'y'
        },
        ...(alertLevelData.length > 0 ? [{
          label: 'Уровень алерта',
          data: alertLevelData,
          type: 'scatter' as const,
          backgroundColor: 'rgb(168, 85, 247)',
          borderColor: 'rgb(168, 85, 247)',
          pointRadius: 6,
          pointHoverRadius: 8,
          yAxisID: 'y'
        }] : []),
        ...(orderbookData.length > 0 ? [
          {
            label: 'Покупки (Bids)',
            data: orderbookData.filter(d => d.type === 'bid'),
            type: 'scatter' as const,
            backgroundColor: 'rgba(34, 197, 94, 0.6)',
            borderColor: 'rgb(34, 197, 94)',
            pointRadius: (context: any) => Math.min(context.raw.volume / 100, 15),
            yAxisID: 'y'
          },
          {
            label: 'Продажи (Asks)',
            data: orderbookData.filter(d => d.type === 'ask'),
            type: 'scatter' as const,
            backgroundColor: 'rgba(239, 68, 68, 0.6)',
            borderColor: 'rgb(239, 68, 68)',
            pointRadius: (context: any) => Math.min(context.raw.volume / 100, 15),
            yAxisID: 'y'
          }
        ] : [])
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
          text: `${alert.symbol} - Свечной график с данными`,
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
                    `Volume: ${candle.volume.toFixed(2)}`,
                    `Type: ${candle.is_long ? 'LONG' : 'SHORT'}`
                  ];
                }
              } else if (context.datasetIndex === 1) {
                return `Алерт: $${context.parsed.y.toFixed(8)}`;
              } else if (context.raw && typeof context.raw === 'object' && 'volume' in context.raw) {
                const data = context.raw as any;
                return `${data.type === 'bid' ? 'Покупка' : 'Продажа'}: $${context.parsed.y.toFixed(8)} (${data.volume.toFixed(2)} USDT)`;
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
          display: true,
          position: 'left',
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

  const chartConfig = getChartConfig();
  const volumeChartConfig = getVolumeChartConfig();

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-lg w-full max-w-7xl h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200">
          <div>
            <h2 className="text-2xl font-bold text-gray-900">{alert.symbol}</h2>
            <p className="text-gray-600">
              График с данными • Алерт: {new Date(alert.close_timestamp || alert.timestamp).toLocaleString('ru-RU')}
            </p>
            {alert.has_imbalance && (
              <div className="flex items-center space-x-2 mt-2">
                <span className="text-orange-500 text-sm">⚠️ Обнаружен имбаланс</span>
                {alert.imbalance_data && (
                  <span className="text-xs text-gray-500">
                    ({alert.imbalance_data.type}, {alert.imbalance_data.direction}, сила: {alert.imbalance_data.strength.toFixed(1)}%)
                  </span>
                )}
              </div>
            )}
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
          ) : chartConfig && volumeChartConfig ? (
            <div className="h-full flex flex-col space-y-4">
              {/* Основной график с ценами */}
              <div className="flex-1 min-h-0">
                <div className="h-full flex">
                  {/* График свечей */}
                  <div className="flex-1 h-full">
                    <Chart type="candlestick" data={chartConfig.data} options={chartConfig.options} />
                  </div>
                  
                  {/* Стакан заявок справа */}
                  {alert.order_book_snapshot && (
                    <div className="w-64 ml-4 bg-gray-50 rounded-lg p-4">
                      <h4 className="text-sm font-medium text-gray-700 mb-3">Стакан заявок</h4>
                      <div className="space-y-2">
                        <div>
                          <div className="text-xs text-red-600 mb-1">Продажи (Asks)</div>
                          {alert.order_book_snapshot.asks.slice(0, 8).reverse().map(([price, volume], i) => (
                            <div key={i} className="flex justify-between text-xs py-0.5">
                              <span className="text-gray-900 font-mono">${price.toFixed(6)}</span>
                              <span className="text-red-600">${(price * volume).toFixed(0)}</span>
                            </div>
                          ))}
                        </div>
                        
                        <div className="border-t border-gray-300 my-2"></div>
                        
                        <div>
                          <div className="text-xs text-green-600 mb-1">Покупки (Bids)</div>
                          {alert.order_book_snapshot.bids.slice(0, 8).map(([price, volume], i) => (
                            <div key={i} className="flex justify-between text-xs py-0.5">
                              <span className="text-gray-900 font-mono">${price.toFixed(6)}</span>
                              <span className="text-green-600">${(price * volume).toFixed(0)}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </div>
              
              {/* График объемов внизу */}
              <div className="h-48">
                <Chart type="bar" data={volumeChartConfig.data} options={volumeChartConfig.options} />
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-center h-full">
              <p className="text-gray-600">Нет данных для отображения</p>
            </div>
          )}
        </div>

        {/* Alert Info */}
        <div className="p-6 border-t border-gray-200 bg-gray-50">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div>
              <span className="text-gray-600">Тип алерта:</span>
              <span className="ml-2 text-gray-900 font-medium">
                {alert.alert_type === 'volume_spike' ? 'Превышение объема' :
                 alert.alert_type === 'consecutive_long' ? 'LONG последовательность' :
                 alert.alert_type === 'priority' ? 'Приоритетный' : 'Неизвестный'}
              </span>
            </div>
            <div>
              <span className="text-gray-600">Цена алерта:</span>
              <span className="ml-2 text-gray-900 font-mono">${alert.price.toFixed(8)}</span>
            </div>
            <div>
              <span className="text-gray-600">Время:</span>
              <span className="ml-2 text-gray-900">
                {new Date(alert.close_timestamp || alert.timestamp).toLocaleString('ru-RU')}
              </span>
            </div>
            <div>
              <span className="text-gray-600">Свечей на графике:</span>
              <span className="ml-2 text-gray-900">{chartData.length}</span>
            </div>
          </div>
          
          {/* OHLCV данные свечи алерта */}
          {alert.candle_data && (
            <div className="mt-4 p-4 bg-white rounded-lg border border-gray-200">
              <div className="text-sm font-medium text-gray-700 mb-2">Данные свечи алерта (OHLCV):</div>
              <div className="grid grid-cols-5 gap-4 text-sm">
                <div>
                  <span className="text-gray-600">Open:</span>
                  <div className="text-gray-900 font-mono">${alert.candle_data.open.toFixed(8)}</div>
                </div>
                <div>
                  <span className="text-gray-600">High:</span>
                  <div className="text-gray-900 font-mono">${alert.candle_data.high.toFixed(8)}</div>
                </div>
                <div>
                  <span className="text-gray-600">Low:</span>
                  <div className="text-gray-900 font-mono">${alert.candle_data.low.toFixed(8)}</div>
                </div>
                <div>
                  <span className="text-gray-600">Close:</span>
                  <div className="text-gray-900 font-mono">${alert.candle_data.close.toFixed(8)}</div>
                </div>
                <div>
                  <span className="text-gray-600">Volume:</span>
                  <div className="text-gray-900 font-mono">{alert.candle_data.volume.toFixed(2)}</div>
                </div>
              </div>
              {alert.candle_data.alert_level && (
                <div className="mt-2 text-sm">
                  <span className="text-gray-600">Уровень первоначального алерта:</span>
                  <span className="ml-2 text-purple-600 font-mono">${alert.candle_data.alert_level.toFixed(8)}</span>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default ChartModal;