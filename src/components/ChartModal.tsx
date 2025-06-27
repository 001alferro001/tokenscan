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

ChartJS.register(
  CategoryScale,
  LinearScale,
  TimeScale,
  BarElement,
  LineElement,
  PointElement,
  Title,
  Tooltip,
  Legend
);

interface Alert {
  id: number;
  symbol: string;
  alert_type: string;
  price: number;
  timestamp: string;
  close_timestamp?: string;
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

interface ImbalanceZone {
  start: number;
  end: number;
  top: number;
  bottom: number;
  type: 'fair_value_gap' | 'order_block' | 'breaker_block';
  direction: 'bullish' | 'bearish';
  strength: number;
}

interface ChartModalProps {
  alert: Alert;
  onClose: () => void;
}

const ChartModal: React.FC<ChartModalProps> = ({ alert, onClose }) => {
  const [chartData, setChartData] = useState<ChartData[]>([]);
  const [imbalanceZones, setImbalanceZones] = useState<ImbalanceZone[]>([]);
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
      
      // Анализируем имбалансы
      if (data.chart_data && data.chart_data.length > 0) {
        const zones = analyzeImbalances(data.chart_data);
        setImbalanceZones(zones);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Неизвестная ошибка');
    } finally {
      setLoading(false);
    }
  };

  const analyzeImbalances = (candles: ChartData[]): ImbalanceZone[] => {
    const zones: ImbalanceZone[] = [];
    
    // Анализ Fair Value Gaps
    for (let i = 2; i < candles.length; i++) {
      const prev = candles[i - 2];
      const current = candles[i - 1];
      const next = candles[i];
      
      // Bullish FVG: предыдущая свеча low > следующая свеча high
      if (prev.low > next.high && current.is_long) {
        zones.push({
          start: current.timestamp,
          end: next.timestamp,
          top: prev.low,
          bottom: next.high,
          type: 'fair_value_gap',
          direction: 'bullish',
          strength: (prev.low - next.high) / next.high * 100
        });
      }
      
      // Bearish FVG: предыдущая свеча high < следующая свеча low
      if (prev.high < next.low && !current.is_long) {
        zones.push({
          start: current.timestamp,
          end: next.timestamp,
          top: next.low,
          bottom: prev.high,
          type: 'fair_value_gap',
          direction: 'bearish',
          strength: (next.low - prev.high) / prev.high * 100
        });
      }
    }
    
    // Анализ Order Blocks
    for (let i = 5; i < candles.length; i++) {
      const window = candles.slice(i - 5, i);
      const current = candles[i];
      
      // Bullish Order Block: последняя медвежья свеча перед сильным восходящим движением
      const lastBearish = window.reverse().find(c => !c.is_long);
      if (lastBearish && current.is_long && current.close > lastBearish.high * 1.02) {
        zones.push({
          start: lastBearish.timestamp,
          end: current.timestamp,
          top: lastBearish.high,
          bottom: lastBearish.low,
          type: 'order_block',
          direction: 'bullish',
          strength: (current.close - lastBearish.high) / lastBearish.high * 100
        });
      }
      
      // Bearish Order Block: последняя бычья свеча перед сильным нисходящим движением
      const lastBullish = window.reverse().find(c => c.is_long);
      if (lastBullish && !current.is_long && current.close < lastBullish.low * 0.98) {
        zones.push({
          start: lastBullish.timestamp,
          end: current.timestamp,
          top: lastBullish.high,
          bottom: lastBullish.low,
          type: 'order_block',
          direction: 'bearish',
          strength: (lastBullish.low - current.close) / lastBullish.low * 100
        });
      }
    }
    
    return zones.filter(zone => zone.strength > 0.5); // Фильтруем слабые зоны
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
      c: d.close,
      color: d.is_long ? 'rgba(34, 197, 94, 0.8)' : 'rgba(239, 68, 68, 0.8)',
      borderColor: d.is_long ? 'rgb(34, 197, 94)' : 'rgb(239, 68, 68)'
    }));

    // Данные объема
    const volumeData = chartData.map(d => ({
      x: d.timestamp,
      y: d.volume_usdt
    }));

    // Отметки алертов
    const alertPoints = [];
    
    if (preliminaryTime) {
      alertPoints.push({
        x: preliminaryTime,
        y: alert.preliminary_alert?.price || alert.price,
        label: 'Предварительный'
      });
    }
    
    alertPoints.push({
      x: alertTime,
      y: alert.final_alert?.price || alert.price,
      label: 'Финальный'
    });

    // Уровень алерта
    let alertLevelData = [];
    if (alert.candle_data?.alert_level) {
      alertLevelData = [{
        x: alertTime,
        y: alert.candle_data.alert_level
      }];
    }

    // Зоны имбаланса
    const imbalanceAnnotations = imbalanceZones.map((zone, index) => ({
      type: 'box',
      xMin: zone.start,
      xMax: zone.end,
      yMin: zone.bottom,
      yMax: zone.top,
      backgroundColor: zone.direction === 'bullish' ? 'rgba(34, 197, 94, 0.2)' : 'rgba(239, 68, 68, 0.2)',
      borderColor: zone.direction === 'bullish' ? 'rgb(34, 197, 94)' : 'rgb(239, 68, 68)',
      borderWidth: 1,
      label: {
        content: `${zone.type} (${zone.strength.toFixed(1)}%)`,
        enabled: true,
        position: 'topLeft'
      }
    }));

    const data = {
      datasets: [
        {
          label: 'Свечи',
          data: candleData,
          type: 'candlestick' as const,
          yAxisID: 'y'
        },
        {
          label: 'Объем (USDT)',
          data: volumeData,
          type: 'bar' as const,
          backgroundColor: chartData.map(d => d.is_long ? 'rgba(34, 197, 94, 0.6)' : 'rgba(239, 68, 68, 0.6)'),
          borderColor: chartData.map(d => d.is_long ? 'rgb(34, 197, 94)' : 'rgb(239, 68, 68)'),
          borderWidth: 1,
          yAxisID: 'y1'
        },
        {
          label: 'Алерты',
          data: alertPoints,
          type: 'scatter' as const,
          backgroundColor: alertPoints.map((_, i) => i === 0 ? 'rgb(255, 193, 7)' : 'rgb(255, 215, 0)'),
          borderColor: alertPoints.map((_, i) => i === 0 ? 'rgb(255, 193, 7)' : 'rgb(255, 215, 0)'),
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
        }] : [])
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
          text: `${alert.symbol} - Свечной график с анализом имбаланса`,
          color: 'white'
        },
        legend: {
          labels: {
            color: 'white'
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
                return `Объем: $${context.parsed.y.toLocaleString()}`;
              } else if (context.datasetIndex === 2) {
                const point = alertPoints[context.dataIndex];
                return `${point.label} алерт: $${context.parsed.y.toFixed(8)}`;
              } else {
                return `Уровень алерта: $${context.parsed.y.toFixed(8)}`;
              }
              return '';
            }
          }
        },
        annotation: {
          annotations: imbalanceAnnotations
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
            color: 'white'
          },
          grid: {
            color: 'rgba(255, 255, 255, 0.1)'
          }
        },
        y: {
          type: 'linear',
          display: true,
          position: 'left',
          ticks: {
            color: 'white',
            callback: function(value) {
              return '$' + Number(value).toFixed(8);
            }
          },
          grid: {
            color: 'rgba(255, 255, 255, 0.1)'
          }
        },
        y1: {
          type: 'linear',
          display: true,
          position: 'right',
          ticks: {
            color: 'white',
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
            drawOnChartArea: false,
          },
        }
      }
    };

    return { data, options };
  };

  const chartConfig = getChartConfig();

  return (
    <div className="fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center p-4 z-50">
      <div className="bg-gray-800 rounded-lg w-full max-w-6xl h-[80vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-700">
          <div>
            <h2 className="text-2xl font-bold text-white">{alert.symbol}</h2>
            <p className="text-gray-400">
              Свечной график с анализом имбаланса • Алерт: {new Date(alert.close_timestamp || alert.timestamp).toLocaleString('ru-RU')}
            </p>
            {alert.has_imbalance && (
              <div className="flex items-center space-x-2 mt-2">
                <span className="text-yellow-400 text-sm">⚠️ Обнаружен имбаланс</span>
                {alert.imbalance_data && (
                  <span className="text-xs text-gray-400">
                    ({alert.imbalance_data.type}, {alert.imbalance_data.direction}, сила: {alert.imbalance_data.strength})
                  </span>
                )}
              </div>
            )}
          </div>
          
          <div className="flex items-center space-x-3">
            <button
              onClick={downloadChart}
              className="flex items-center space-x-2 bg-green-600 hover:bg-green-700 px-4 py-2 rounded-lg transition-colors"
            >
              <Download className="w-4 h-4" />
              <span>Скачать</span>
            </button>
            
            <button
              onClick={openTradingView}
              className="flex items-center space-x-2 bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded-lg transition-colors"
            >
              <ExternalLink className="w-4 h-4" />
              <span>TradingView</span>
            </button>
            
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-white p-2"
            >
              <X className="w-6 h-6" />
            </button>
          </div>
        </div>

        {/* Chart Content */}
        <div className="flex-1 p-6">
          {loading ? (
            <div className="flex items-center justify-center h-full">
              <div className="text-center">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto mb-4"></div>
                <p className="text-gray-400">Загрузка данных графика...</p>
              </div>
            </div>
          ) : error ? (
            <div className="flex items-center justify-center h-full">
              <div className="text-center">
                <p className="text-red-400 mb-4">Ошибка: {error}</p>
                <button
                  onClick={loadChartData}
                  className="bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded-lg transition-colors"
                >
                  Попробовать снова
                </button>
              </div>
            </div>
          ) : chartConfig ? (
            <div className="h-full">
              <Chart type="line" data={chartConfig.data} options={chartConfig.options} />
            </div>
          ) : (
            <div className="flex items-center justify-center h-full">
              <p className="text-gray-400">Нет данных для отображения</p>
            </div>
          )}
        </div>

        {/* Alert Info */}
        <div className="p-6 border-t border-gray-700 bg-gray-900">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div>
              <span className="text-gray-400">Тип алерта:</span>
              <span className="ml-2 text-white">
                {alert.alert_type === 'volume_spike' ? 'Превышение объема' :
                 alert.alert_type === 'consecutive_long' ? 'LONG последовательность' :
                 alert.alert_type === 'priority' ? 'Приоритетный' : 'Неизвестный'}
              </span>
            </div>
            <div>
              <span className="text-gray-400">Цена алерта:</span>
              <span className="ml-2 text-white">${(alert.final_alert?.price || alert.price).toFixed(8)}</span>
            </div>
            <div>
              <span className="text-gray-400">Время:</span>
              <span className="ml-2 text-white">
                {new Date(alert.close_timestamp || alert.timestamp).toLocaleString('ru-RU')}
              </span>
            </div>
            <div>
              <span className="text-gray-400">Свечей на графике:</span>
              <span className="ml-2 text-white">{chartData.length}</span>
            </div>
          </div>
          
          {/* Зоны имбаланса */}
          {imbalanceZones.length > 0 && (
            <div className="mt-4 p-4 bg-gray-800 rounded-lg">
              <div className="text-sm font-medium text-gray-300 mb-2">Обнаруженные зоны имбаланса:</div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs">
                {imbalanceZones.slice(0, 4).map((zone, index) => (
                  <div key={index} className="flex justify-between items-center p-2 bg-gray-700 rounded">
                    <span className="text-white">
                      {zone.type === 'fair_value_gap' && 'Fair Value Gap'}
                      {zone.type === 'order_block' && 'Order Block'}
                      {zone.type === 'breaker_block' && 'Breaker Block'}
                    </span>
                    <span className={`text-xs ${zone.direction === 'bullish' ? 'text-green-400' : 'text-red-400'}`}>
                      {zone.direction} ({zone.strength.toFixed(1)}%)
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
          
          {/* OHLCV данные свечи алерта */}
          {alert.candle_data && (
            <div className="mt-4 p-4 bg-gray-800 rounded-lg">
              <div className="text-sm font-medium text-gray-300 mb-2">Данные свечи алерта (OHLCV):</div>
              <div className="grid grid-cols-5 gap-4 text-sm">
                <div>
                  <span className="text-gray-400">Open:</span>
                  <div className="text-white font-mono">${alert.candle_data.open.toFixed(8)}</div>
                </div>
                <div>
                  <span className="text-gray-400">High:</span>
                  <div className="text-white font-mono">${alert.candle_data.high.toFixed(8)}</div>
                </div>
                <div>
                  <span className="text-gray-400">Low:</span>
                  <div className="text-white font-mono">${alert.candle_data.low.toFixed(8)}</div>
                </div>
                <div>
                  <span className="text-gray-400">Close:</span>
                  <div className="text-white font-mono">${alert.candle_data.close.toFixed(8)}</div>
                </div>
                <div>
                  <span className="text-gray-400">Volume:</span>
                  <div className="text-white font-mono">{alert.candle_data.volume.toFixed(2)}</div>
                </div>
              </div>
              {alert.candle_data.alert_level && (
                <div className="mt-2 text-sm">
                  <span className="text-gray-400">Уровень первоначального алерта:</span>
                  <span className="ml-2 text-yellow-400 font-mono">${alert.candle_data.alert_level.toFixed(8)}</span>
                </div>
              )}
            </div>
          )}

          {/* Снимок стакана */}
          {alert.order_book_snapshot && (
            <div className="mt-4 p-4 bg-gray-800 rounded-lg">
              <div className="text-sm font-medium text-gray-300 mb-2">
                Снимок стакана на момент алерта ({new Date(alert.order_book_snapshot.timestamp).toLocaleString('ru-RU')}):
              </div>
              <div className="grid grid-cols-2 gap-4 text-xs">
                <div>
                  <div className="text-green-400 mb-2 font-medium">Покупки (Bids):</div>
                  {alert.order_book_snapshot.bids.slice(0, 5).map(([price, size], i) => (
                    <div key={i} className="flex justify-between py-1">
                      <span className="text-white font-mono">${price.toFixed(8)}</span>
                      <span className="text-gray-400">{size.toFixed(2)}</span>
                    </div>
                  ))}
                </div>
                <div>
                  <div className="text-red-400 mb-2 font-medium">Продажи (Asks):</div>
                  {alert.order_book_snapshot.asks.slice(0, 5).map(([price, size], i) => (
                    <div key={i} className="flex justify-between py-1">
                      <span className="text-white font-mono">${price.toFixed(8)}</span>
                      <span className="text-gray-400">{size.toFixed(2)}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default ChartModal;