import React, { useEffect, useRef } from 'react';
import { X, ExternalLink } from 'lucide-react';

interface CryptoCompareWidgetProps {
  symbol: string;
  onClose: () => void;
}

const CryptoCompareWidget: React.FC<CryptoCompareWidgetProps> = ({ symbol, onClose }) => {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    loadWidget();
  }, [symbol]);

  const loadWidget = () => {
    if (!containerRef.current) return;

    // Очищаем контейнер
    containerRef.current.innerHTML = '';

    // Преобразуем символ (BTCUSDT -> BTC)
    const baseCurrency = symbol.replace('USDT', '');

    // Создаем iframe с виджетом CryptoCompare
    const iframe = document.createElement('iframe');
    iframe.src = `https://widget.cryptocompare.com/serve/v3/coin/chart?fsym=${baseCurrency}&tsyms=USD&period=1D`;
    iframe.width = '100%';
    iframe.height = '100%';
    iframe.frameBorder = '0';
    iframe.style.border = 'none';

    containerRef.current.appendChild(iframe);
  };

  const openCryptoCompare = () => {
    const baseCurrency = symbol.replace('USDT', '');
    window.open(`https://www.cryptocompare.com/coins/${baseCurrency.toLowerCase()}/overview/USD`, '_blank');
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-lg w-full max-w-4xl h-[80vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200">
          <div>
            <h2 className="text-2xl font-bold text-gray-900">{symbol}</h2>
            <p className="text-gray-600">График CryptoCompare</p>
          </div>
          
          <div className="flex items-center space-x-3">
            <button
              onClick={openCryptoCompare}
              className="flex items-center space-x-2 bg-orange-600 hover:bg-orange-700 text-white px-4 py-2 rounded-lg transition-colors"
            >
              <ExternalLink className="w-4 h-4" />
              <span>CryptoCompare</span>
            </button>
            
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600 p-2"
            >
              <X className="w-6 h-6" />
            </button>
          </div>
        </div>

        {/* Widget Container */}
        <div className="flex-1 p-6">
          <div
            ref={containerRef}
            className="w-full h-full bg-gray-50 rounded-lg"
          />
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-gray-200 bg-gray-50">
          <div className="flex justify-between items-center text-sm text-gray-600">
            <span>Данные предоставлены CryptoCompare</span>
            <span>Обновляется в реальном времени</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default CryptoCompareWidget;