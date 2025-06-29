import React, { useEffect, useRef, useState } from 'react';
import { X, ExternalLink, Settings, Maximize2, Minimize2, Target, Zap, AlertTriangle } from 'lucide-react';

interface TradingViewChartProps {
  symbol: string;
  alertPrice?: number;
  alertTime?: number | string;
  alerts?: Alert[];  // Массив всех алертов для символа
  onClose: () => void;
  theme?: 'light' | 'dark';
}

interface Alert {
  id: number;
  symbol: string;
  alert_type: string;
  price: number;
  timestamp: number | string;
  close_timestamp?: number | string;
  volume_ratio?: number;
  consecutive_count?: number;
  has_imbalance?: boolean;
  imbalance_data?: {
    type: string;
    direction: 'bullish' | 'bearish';
    top: number;
    bottom: number;
    strength: number;
  };
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
  alerts = [],
  onClose,
  theme = 'light'
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const widgetRef = useRef<any>(null);
  const chartRef = useRef<any>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [interval, setInterval] = useState('1');
  const [chartType, setChartType] = useState('1');
  const [isLoading, setIsLoading] = useState(true);
  const [showSignals, setShowSignals] = useState(true);
  const [signalShapes, setSignalShapes] = useState<any[]>([]);
  const [scriptLoaded, setScriptLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [retryCount, setRetryCount] = useState(0);

  useEffect(() => {
    loadTradingViewScript();
    return () => {
      // Cleanup при размонтировании
      if (widgetRef.current) {
        try {
          widgetRef.current.remove();
        } catch (e) {
          console.log('Widget cleanup error:', e);
        }
      }
    };
  }, []);

  useEffect(() => {
    if (scriptLoaded && containerRef.current) {
      createWidget();
    }
  }, [scriptLoaded, symbol, interval, chartType, theme]);

  useEffect(() => {
    if (chartRef.current && showSignals && alerts.length > 0) {
      // Добавляем задержку для стабильности
      const timer = setTimeout(() => {
        addSignalsToChart();
      }, 2000);
      
      return () => clearTimeout(timer);
    }
  }, [alerts, showSignals, chartRef.current]);

  const loadTradingViewScript = () => {
    if (window.TradingView) {
      setScriptLoaded(true);
      return;
    }

    // Проверяем, не загружается ли уже скрипт
    const existingScript = document.querySelector('script[src*="charting_library"]') || 
                          document.querySelector('script[src*="tv.js"]');
    if (existingScript) {
      existingScript.addEventListener('load', () => setScriptLoaded(true));
      existingScript.addEventListener('error', handleScriptError);
      return;
    }

    // Пробуем загрузить основной скрипт TradingView
    const script = document.createElement('script');
    script.src = 'https://s3.tradingview.com/tv.js';
    script.async = true;
    script.onload = () => {
      console.log('TradingView script loaded successfully');
      setScriptLoaded(true);
      setError(null);
      setRetryCount(0);
    };
    script.onerror = () => {
      console.log('Primary script failed, trying alternative...');
      // Пробуем альтернативный URL
      loadAlternativeScript();
    };
    document.head.appendChild(script);
  };

  const loadAlternativeScript = () => {
    const script = document.createElement('script');
    script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js';
    script.async = true;
    script.onload = () => {
      console.log('Alternative TradingView script loaded');
      // Создаем простую заглушку для TradingView API
      if (!window.TradingView) {
        window.TradingView = {
          widget: function(config: any) {
            console.log('Creating TradingView widget with config:', config);
            return {
              onChartReady: (callback: Function) => {
                setTimeout(callback, 1000);
              },
              chart: () => ({
                createShape: () => null,
                remove: () => null
              }),
              remove: () => null
            };
          }
        };
      }
      setScriptLoaded(true);
      setError(null);
    };
    script.onerror = handleScriptError;
    document.head.appendChild(script);
  };

  const handleScriptError = () => {
    console.error('Ошибка загрузки TradingView скрипта');
    setError('Ошибка загрузки TradingView. Проверьте подключение к интернету.');
    setIsLoading(false);
    setRetryCount(prev => prev + 1);
  };

  const createWidget = () => {
    if (!containerRef.current) {
      console.error('Container not available');
      return;
    }

    // Если TradingView недоступен, создаем простую заглушку
    if (!window.TradingView) {
      createFallbackChart();
      return;
    }

    const tvSymbol = `BYBIT:${symbol.replace('USDT', '')}USDT.P`;
    const containerId = `tradingview_${symbol}_${Date.now()}`;
    
    // Устанавливаем ID контейнера
    containerRef.current.id = containerId;

    try {
      console.log('Creating TradingView widget for:', tvSymbol);
      
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
        container_id: containerId,
        studies: [
          'Volume@tv-basicstudies'
        ],
        overrides: {
          'mainSeriesProperties.candleStyle.upColor': '#26a69a',
          'mainSeriesProperties.candleStyle.downColor': '#ef5350',
          'mainSeriesProperties.candleStyle.borderUpColor': '#26a69a',
          'mainSeriesProperties.candleStyle.borderDownColor': '#ef5350',
          'mainSeriesProperties.candleStyle.wickUpColor': '#26a69a',
          'mainSeriesProperties.candleStyle.wickDownColor': '#ef5350',
          'volumePaneSize': 'medium',
          'paneProperties.background': theme === 'dark' ? '#1e1e1e' : '#ffffff',
          'paneProperties.vertGridProperties.color': theme === 'dark' ? '#2a2a2a' : '#e1e1e1',
          'paneProperties.horzGridProperties.color': theme === 'dark' ? '#2a2a2a' : '#e1e1e1',
        },
        disabled_features: [
          'use_localstorage_for_settings',
          'volume_force_overlay'
        ],
        enabled_features: [
          'study_templates',
          'create_volume_indicator_by_default'
        ],
        loading_screen: {
          backgroundColor: theme === 'dark' ? '#1e1e1e' : '#ffffff',
          foregroundColor: theme === 'dark' ? '#ffffff' : '#000000'
        }
      });

      widgetRef.current.onChartReady(() => {
        try {
          console.log('TradingView chart ready');
          chartRef.current = widgetRef.current.chart();
          
          // Добавляем основной алерт
          if (alertPrice) {
            addMainAlert();
          }

          // Добавляем все сигналы
          if (showSignals && alerts.length > 0) {
            setTimeout(() => {
              addSignalsToChart();
            }, 1000);
          }

          setIsLoading(false);
          setError(null);
        } catch (error) {
          console.error('Ошибка инициализации графика:', error);
          setError('Ошибка инициализации графика TradingView');
          setIsLoading(false);
        }
      });

    } catch (error) {
      console.error('Ошибка создания TradingView виджета:', error);
      createFallbackChart();
    }
  };

  const createFallbackChart = () => {
    if (!containerRef.current) return;

    containerRef.current.innerHTML = `
      <div style="
        width: 100%; 
        height: 100%; 
        display: flex; 
        flex-direction: column; 
        align-items: center; 
        justify-content: center;
        background: #f8f9fa;
        border: 2px dashed #dee2e6;
        border-radius: 8px;
      ">
        <div style="text-align: center; padding: 20px;">
          <h3 style="color: #495057; margin-bottom: 16px;">График недоступен</h3>
          <p style="color: #6c757d; margin-bottom: 20px;">
            TradingView временно недоступен.<br>
            Используйте внешнюю ссылку для просмотра графика.
          </p>
          <div style="margin-bottom: 16px;">
            <strong style="color: #495057;">Символ:</strong> ${symbol}<br>
            ${alertPrice ? `<strong style="color: #495057;">Цена алерта:</strong> $${alertPrice.toFixed(6)}<br>` : ''}
            <strong style="color: #495057;">Сигналов:</strong> ${alerts.length}
          </div>
          <button 
            onclick="window.open('${getTradingViewUrl()}', '_blank')"
            style="
              background: #007bff;
              color: white;
              border: none;
              padding: 10px 20px;
              border-radius: 4px;
              cursor: pointer;
              font-size: 14px;
            "
          >
            Открыть в TradingView
          </button>
        </div>
      </div>
    `;

    setIsLoading(false);
    setError('TradingView недоступен - используется резервный режим');
  };

  const getTradingViewUrl = () => {
    const cleanSymbol = symbol.replace('USDT', '');
    return `https://www.tradingview.com/chart/?symbol=BYBIT:${cleanSymbol}USDT.P&interval=${interval}`;
  };

  const addMainAlert = () => {
    if (!chartRef.current || !alertPrice) return;

    try {
      console.log('Adding main alert at price:', alertPrice);
      
      // Горизонтальная линия уровня алерта
      const alertLine = chartRef.current.createShape(
        { time: Date.now() / 1000, price: alertPrice },
        {
          shape: 'horizontal_line',
          lock: true,
          disableSelection: false,
          disableSave: true,
          disableUndo: true,
          overrides: {
            linecolor: '#ff9800',
            linewidth: 3,
            linestyle: 2,
            showLabel: true,
            textcolor: '#ff9800',
            text: `🎯 Alert: $${alertPrice.toFixed(6)}`,
            horzLabelsAlign: 'right',
            vertLabelsAlign: 'middle'
          }
        }
      );

      // Вертикальная линия времени алерта
      if (alertTime) {
        const alertTimestamp = typeof alertTime === 'number' ? alertTime : new Date(alertTime).getTime();
        const alertTimeLine = chartRef.current.createShape(
          { time: alertTimestamp / 1000, price: alertPrice },
          {
            shape: 'vertical_line',
            lock: true,
            disableSelection: false,
            disableSave: true,
            disableUndo: true,
            overrides: {
              linecolor: '#ff5722',
              linewidth: 2,
              linestyle: 1,
              showLabel: true,
              textcolor: '#ff5722',
              text: '⏰ Alert Time',
              horzLabelsAlign: 'center',
              vertLabelsAlign: 'top'
            }
          }
        );
      }
      
      console.log('Main alert added successfully');
    } catch (error) {
      console.error('Ошибка добавления основного алерта:', error);
    }
  };

  const addSignalsToChart = () => {
    if (!chartRef.current || !alerts.length) {
      console.log('Cannot add signals: chart or alerts not available');
      return;
    }

    console.log('Adding signals to chart:', alerts.length, 'alerts');

    // Очищаем предыдущие сигналы
    clearSignals();

    const newShapes: any[] = [];

    alerts.forEach((alert, index) => {
      try {
        const alertTimestamp = typeof alert.timestamp === 'number' ? 
          alert.timestamp : new Date(alert.timestamp).getTime();
        
        const timeInSeconds = alertTimestamp / 1000;

        // Определяем цвет и иконку по типу алерта
        let color = '#2196f3';
        let icon = '📊';
        let label = '';

        switch (alert.alert_type) {
          case 'volume_spike':
            color = '#ff9800';
            icon = '📈';
            label = `Volume ${alert.volume_ratio}x`;
            break;
          case 'consecutive_long':
            color = '#4caf50';
            icon = '🕯️';
            label = `${alert.consecutive_count} LONG`;
            break;
          case 'priority':
            color = '#e91e63';
            icon = '⭐';
            label = 'Priority Signal';
            break;
          case 'smart_money':
            color = '#9c27b0';
            icon = '🧠';
            label = 'Smart Money';
            break;
        }

        console.log(`Adding signal ${index + 1}:`, {
          type: alert.alert_type,
          time: timeInSeconds,
          price: alert.price,
          color,
          label
        });

        // Создаем стрелку вверх для сигнала
        const signalShape = chartRef.current.createShape(
          { time: timeInSeconds, price: alert.price },
          {
            shape: 'arrow_up',
            lock: false,
            disableSelection: false,
            disableSave: true,
            disableUndo: false,
            overrides: {
              color: color,
              transparency: 20,
              size: 'normal',
              showLabel: true,
              textcolor: color,
              text: `${icon} ${label}`,
              fontsize: 12,
              bold: true
            }
          }
        );

        if (signalShape) {
          newShapes.push(signalShape);
        }

        // Добавляем зоны имбаланса для Smart Money сигналов
        if (alert.has_imbalance && alert.imbalance_data && alert.imbalance_data.top && alert.imbalance_data.bottom) {
          const imbalanceColor = alert.imbalance_data.direction === 'bullish' ? 
            'rgba(76, 175, 80, 0.2)' : 'rgba(244, 67, 54, 0.2)';

          console.log('Adding imbalance zone:', {
            top: alert.imbalance_data.top,
            bottom: alert.imbalance_data.bottom,
            direction: alert.imbalance_data.direction
          });

          // Создаем прямоугольник для зоны имбаланса
          const imbalanceZone = chartRef.current.createShape(
            [
              { time: timeInSeconds - 300, price: alert.imbalance_data.top },
              { time: timeInSeconds + 300, price: alert.imbalance_data.bottom }
            ],
            {
              shape: 'rectangle',
              lock: false,
              disableSelection: false,
              disableSave: true,
              disableUndo: false,
              overrides: {
                color: imbalanceColor,
                transparency: 80,
                showLabel: true,
                textcolor: alert.imbalance_data.direction === 'bullish' ? '#4caf50' : '#f44336',
                text: `${alert.imbalance_data.type.toUpperCase()} (${alert.imbalance_data.strength.toFixed(1)}%)`,
                fontsize: 10
              }
            }
          );

          if (imbalanceZone) {
            newShapes.push(imbalanceZone);
          }
        }

        // Добавляем текстовую метку с деталями
        const textLabel = chartRef.current.createShape(
          { time: timeInSeconds, price: alert.price * 1.001 }, // Немного выше цены
          {
            shape: 'text',
            lock: false,
            disableSelection: false,
            disableSave: true,
            disableUndo: false,
            overrides: {
              color: color,
              fontsize: 10,
              text: getAlertDetails(alert),
              bold: false,
              italic: false
            }
          }
        );

        if (textLabel) {
          newShapes.push(textLabel);
        }

      } catch (error) {
        console.error(`Ошибка добавления сигнала ${index}:`, error);
      }
    });

    setSignalShapes(newShapes);
    console.log('Signals added successfully:', newShapes.length, 'shapes created');
  };

  const getAlertDetails = (alert: Alert): string => {
    const time = new Date(typeof alert.timestamp === 'number' ? alert.timestamp : alert.timestamp);
    const timeStr = time.toLocaleTimeString('ru-RU', { 
      hour: '2-digit', 
      minute: '2-digit',
      timeZone: 'UTC'
    });

    let details = `${timeStr} UTC\n$${alert.price.toFixed(6)}`;

    if (alert.volume_ratio) {
      details += `\nVolume: ${alert.volume_ratio}x`;
    }

    if (alert.consecutive_count) {
      details += `\nLONG: ${alert.consecutive_count}`;
    }

    if (alert.has_imbalance && alert.imbalance_data) {
      details += `\n${alert.imbalance_data.type.toUpperCase()}`;
      details += `\n${alert.imbalance_data.direction.toUpperCase()}`;
    }

    return details;
  };

  const clearSignals = () => {
    console.log('Clearing signals:', signalShapes.length, 'shapes');
    signalShapes.forEach(shape => {
      try {
        if (shape && shape.remove) {
          shape.remove();
        }
      } catch (error) {
        console.error('Ошибка удаления сигнала:', error);
      }
    });
    setSignalShapes([]);
  };

  const toggleSignals = () => {
    if (showSignals) {
      clearSignals();
    } else {
      addSignalsToChart();
    }
    setShowSignals(!showSignals);
  };

  const openInTradingView = () => {
    window.open(getTradingViewUrl(), '_blank');
  };

  const toggleFullscreen = () => {
    setIsFullscreen(!isFullscreen);
  };

  const retryLoad = () => {
    setError(null);
    setIsLoading(true);
    setScriptLoaded(false);
    setRetryCount(0);
    
    // Удаляем существующие скрипты
    const existingScripts = document.querySelectorAll('script[src*="tradingview"], script[src*="tv.js"]');
    existingScripts.forEach(script => script.remove());
    
    // Перезагружаем скрипт
    loadTradingViewScript();
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
            {alerts.length > 0 && (
              <span className="text-sm text-blue-600 bg-blue-100 px-2 py-1 rounded">
                {alerts.length} сигналов
              </span>
            )}
            {error && (
              <span className="text-sm text-red-600 bg-red-100 px-2 py-1 rounded flex items-center">
                <AlertTriangle className="w-3 h-3 mr-1" />
                График недоступен
              </span>
            )}
          </div>
          
          <div className="flex items-center space-x-3">
            {/* Переключатель сигналов */}
            <button
              onClick={toggleSignals}
              disabled={!chartRef.current || alerts.length === 0}
              className={`flex items-center space-x-2 px-3 py-2 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${
                showSignals 
                  ? 'bg-green-100 text-green-700 hover:bg-green-200' 
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
              title={showSignals ? 'Скрыть сигналы' : 'Показать сигналы'}
            >
              <Target className="w-4 h-4" />
              <span className="text-sm">
                {showSignals ? 'Скрыть сигналы' : 'Показать сигналы'}
              </span>
            </button>

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
                {!scriptLoaded && (
                  <p className="text-sm text-gray-500 mt-2">Загрузка скрипта TradingView...</p>
                )}
              </div>
            </div>
          )}

          {error && !isLoading && (
            <div className="absolute inset-0 flex items-center justify-center bg-white z-10">
              <div className="text-center">
                <AlertTriangle className="w-12 h-12 text-orange-500 mx-auto mb-4" />
                <p className="text-orange-600 mb-4">{error}</p>
                {retryCount < 3 && (
                  <button
                    onClick={retryLoad}
                    className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg transition-colors mr-2"
                  >
                    Попробовать снова ({retryCount + 1}/3)
                  </button>
                )}
                <button
                  onClick={openInTradingView}
                  className="bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded-lg transition-colors"
                >
                  Открыть в TradingView
                </button>
              </div>
            </div>
          )}
          
          <div
            ref={containerRef}
            className="w-full h-full"
          />
        </div>

        {/* Footer */}
        <div className="p-3 border-t border-gray-200 bg-gray-50">
          <div className="flex justify-between items-center text-sm text-gray-600">
            <div className="flex items-center space-x-4">
              <span>Данные предоставлены TradingView</span>
              {alerts.length > 0 && (
                <span className="flex items-center space-x-1">
                  <Zap className="w-3 h-3" />
                  <span>{alerts.length} сигналов программы на графике</span>
                </span>
              )}
              {signalShapes.length > 0 && (
                <span className="text-green-600">
                  ✓ {signalShapes.length} объектов добавлено
                </span>
              )}
            </div>
            <span>Обновляется в реальном времени</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default TradingViewChart;