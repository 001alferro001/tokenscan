import React, { useEffect, useRef, useState } from 'react';
import { X, ExternalLink, Settings, Maximize2, Minimize2 } from 'lucide-react';

interface TradingViewChartProps {
  symbol: string;
  alertPrice?: number;
  alertTime?: number | string;
  onClose: () => void;
  theme?: 'light' | 'dark';
}

declare global {
  interface Window {
    TradingView: any;
  }
}

const TradingViewChart: React.FC<TradingViewChartProps> = ({ 
  symbol, 
  alertPrice, 
  alertTime, 
  onClose,
  theme = 'light'
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const widgetRef = useRef<any>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [interval, setInterval] = useState('1');
  const [chartType, setChartType] = useState('1'); // 1 = candlesticks
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    loadTradingViewScript();
  }, []);

  useEffect(() => {
    if (window.TradingView && containerRef.current) {
      createWidget();
    }
  }, [symbol, interval, chartType, theme]);

  const loadTradingViewScript = () => {
    if (window.TradingView) {
      createWidget();
      return;
    }

    const script = document.createElement('script');
    script.src = 'https://s3.tradingview.com/tv.js';
    script.async = true;
    script.onload = () => {
      createWidget();
    };
    document.head.appendChild(script);
  };

  const createWidget = () => {
    if (!containerRef.current || !window.TradingView) return;

    // Очищаем предыдущий виджет
    if (widgetRef.current) {
      widgetRef.current.remove();
    }

    // Преобразуем символ для TradingView
    const tvSymbol = `BYBIT:${symbol.replace('USDT', '')}USDT.P`;

    try {
      widgetRef.current = new window.TradingView.widget({
        autosize: true,
        symbol: tvSymbol,
        interval: interval,
        timezone: 'UTC',
        theme: theme,
        style: chartType,
        locale: 'ru',
        toolbar_bg: '#f1f3f6',
        enable_publishing: false,
        hide_top_toolbar: false,
        hide_legend: false,
        save_image: true,
        container_id: containerRef.current.id,
        studies: [
          'Volume@tv-basicstudies',
          'RSI@tv-basicstudies'
        ],
        overrides: {
          // Настройки цветов для свечей
          'mainSeriesProperties.candleStyle.upColor': '#26a69a',
          'mainSeriesProperties.candleStyle.downColor': '#ef5350',
          'mainSeriesProperties.candleStyle.borderUpColor': '#26a69a',
          'mainSeriesProperties.candleStyle.borderDownColor': '#ef5350',
          'mainSeriesProperties.candleStyle.wickUpColor': '#26a69a',
          'mainSeriesProperties.candleStyle.wickDownColor': '#ef5350',
          
          // Настройки объема
          'volumePaneSize': 'medium',
          
          // Настройки сетки
          'paneProperties.background': theme === 'dark' ? '#1e1e1e' : '#ffffff',
          'paneProperties.vertGridProperties.color': theme === 'dark' ? '#2a2a2a' : '#e1e1e1',
          'paneProperties.horzGridProperties.color': theme === 'dark' ? '#2a2a2a' : '#e1e1e1',
        },
        disabled_features: [
          'use_localstorage_for_settings',
          'volume_force_overlay'
        ],
        enabled_features: [
          'study_templates'
        ],
        loading_screen: {
          backgroundColor: theme === 'dark' ? '#1e1e1e' : '#ffffff',
          foregroundColor: theme === 'dark' ? '#ffffff' : '#000000'
        }
      });

      // Добавляем линию алерта, если есть цена
      if (alertPrice && widgetRef.current) {
        widgetRef.current.onChartReady(() => {
          const chart = widgetRef.current.chart();
          
          // Добавляем горизонтальную линию на уровне алерта
          chart.createShape(
            { time: Date.now() / 1000, price: alertPrice },
            {
              shape: 'horizontal_line',
              lock: true,
              disableSelection: true,
              disableSave: true,
              disableUndo: true,
              overrides: {
                linecolor: '#ff9800',
                linewidth: 2,
                linestyle: 2, // пунктирная линия
                showLabel: true,
                textcolor: '#ff9800',
                text: `Alert: $${alertPrice.toFixed(6)}`
              }
            }
          );

          // Если есть время алерта, добавляем вертикальную линию
          if (alertTime) {
            const alertTimestamp = typeof alertTime === 'number' ? alertTime : new Date(alertTime).getTime();
            chart.createShape(
              { time: alertTimestamp / 1000, price: alertPrice },
              {
                shape: 'vertical_line',
                lock: true,
                disableSelection: true,
                disableSave: true,
                disableUndo: true,
                overrides: {
                  linecolor: '#ff5722',
                  linewidth: 1,
                  linestyle: 2,
                  showLabel: true,
                  textcolor: '#ff5722',
                  text: 'Alert Time'
                }
              }
            );
          }

          setIsLoading(false);
        });
      } else {
        setTimeout(() => setIsLoading(false), 2000);
      }

    } catch (error) {
      console.error('Ошибка создания TradingView виджета:', error);
      setIsLoading(false);
    }
  };

  const openInTradingView = () => {
    const cleanSymbol = symbol.replace('USDT', '');
    const url = `https://www.tradingview.com/chart/?symbol=BYBIT:${cleanSymbol}USDT.P&interval=${interval}`;
    window.open(url, '_blank');
  };

  const toggleFullscreen = () => {
    setIsFullscreen(!isFullscreen);
  };

  const intervals = [
    { value: '1', label: '1м' },
    { value: '5', label: '5м' },
    { value: '15', label: '15м' },
    { value: '60', label: '1ч' },
    { value: '240', label: '4ч' },
    { value: '1D', label: '1д' }
  ];

  const chartTypes = [
    { value: '1', label: 'Свечи' },
    { value: '0', label: 'Бары' },
    { value: '3', label: 'Линия' },
    { value: '9', label: 'Hollow' }
  ];

  return (
    <div className={`fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50 ${
      isFullscreen ? 'p-0' : ''
    }`}>
      <div className={`bg-white rounded-lg flex flex-col ${
        isFullscreen ? 'w-full h-full rounded-none' : 'w-full max-w-[95vw] h-[90vh]'
      }`}>
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-200 bg-gray-50">
          <div className="flex items-center space-x-4">
            <h2 className="text-xl font-bold text-gray-900">{symbol}</h2>
            {alertPrice && (
              <span className="text-sm text-orange-600 bg-orange-100 px-2 py-1 rounded">
                Alert: ${alertPrice.toFixed(6)}
              </span>
            )}
          </div>
          
          <div className="flex items-center space-x-3">
            {/* Интервалы */}
            <div className="flex items-center space-x-1 bg-gray-100 rounded-lg p-1">
              {intervals.map((int) => (
                <button
                  key={int.value}
                  onClick={() => setInterval(int.value)}
                  className={`px-2 py-1 text-xs rounded transition-colors ${
                    interval === int.value
                      ? 'bg-blue-600 text-white'
                      : 'text-gray-600 hover:bg-gray-200'
                  }`}
                >
                  {int.label}
                </button>
              ))}
            </div>

            {/* Типы графиков */}
            <div className="flex items-center space-x-1 bg-gray-100 rounded-lg p-1">
              {chartTypes.map((type) => (
                <button
                  key={type.value}
                  onClick={() => setChartType(type.value)}
                  className={`px-2 py-1 text-xs rounded transition-colors ${
                    chartType === type.value
                      ? 'bg-green-600 text-white'
                      : 'text-gray-600 hover:bg-gray-200'
                  }`}
                >
                  {type.label}
                </button>
              ))}
            </div>

            <button
              onClick={toggleFullscreen}
              className="text-gray-600 hover:text-gray-800 p-2"
              title={isFullscreen ? 'Выйти из полноэкранного режима' : 'Полноэкранный режим'}
            >
              {isFullscreen ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
            </button>

            <button
              onClick={openInTradingView}
              className="flex items-center space-x-2 bg-blue-600 hover:bg-blue-700 text-white px-3 py-2 rounded-lg transition-colors"
            >
              <ExternalLink className="w-4 h-4" />
              <span>TradingView</span>
            </button>
            
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600 p-2"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Chart Container */}
        <div className="flex-1 relative">
          {isLoading && (
            <div className="absolute inset-0 flex items-center justify-center bg-white z-10">
              <div className="text-center">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto mb-4"></div>
                <p className="text-gray-600">Загрузка графика TradingView...</p>
              </div>
            </div>
          )}
          
          <div
            ref={containerRef}
            id={`tradingview_${symbol}_${Date.now()}`}
            className="w-full h-full"
          />
        </div>

        {/* Footer */}
        <div className="p-3 border-t border-gray-200 bg-gray-50">
          <div className="flex justify-between items-center text-sm text-gray-600">
            <span>Данные предоставлены TradingView</span>
            <span>Обновляется в реальном времени</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default TradingViewChart;