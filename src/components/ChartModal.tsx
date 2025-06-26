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
    // Простая реализация скачивания данных в CSV
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

    // Подготавливаем данные для свечного графика
    const candleData = chartData.map(d => ({
      x: d.timestamp,
      o: d.open,
      h: d.high,
      l: d.low,
      c: d.close
    }));

    // Данные объема
    const volumeData = chartData.map(d => ({
      x: d.timestamp,
      y: d.volume_usdt
    }));

    // Отметка алерта
    const alertPoint = {
      x: alertTime,
      y: alert.price
    };

    const data = {
      datasets: [
        {
          label: 'Цена',
          data: candleData,
          type: 'line' as const,
          borderColor: 'rgb(59, 130, 246)',
          backgroundColor: 'rgba(59, 130, 246, 0.1)',
          borderWidth: 2,
          pointRadius: 0,
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
          label: 'Алерт',
          data: [alertPoint],
          type: 'scatter' as const,
          backgroundColor: 'rgb(255, 215, 0)',
          borderColor: 'rgb(255, 215, 0)',
          pointRadius: 8,
          pointHoverRadius: 10,
          yAxisID: 'y'
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
          text: `${alert.symbol} - График за последний час`,
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
                return `Цена: $${context.parsed.y.toFixed(8)}`;
              } else if (context.datasetIndex === 1) {
                return `Объем: $${context.parsed.y.toLocaleString()}`;
              } else {
                return `Алерт: $${context.parsed.y.toFixed(8)}`;
              }
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
              График за последний час • Алерт: {new Date(alert.close_timestamp || alert.timestamp).toLocaleString('ru-RU')}
            </p>
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
              <span className="ml-2 text-white">${alert.price.toFixed(8)}</span>
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
        </div>
      </div>
    </div>
  );
};

export default ChartModal;