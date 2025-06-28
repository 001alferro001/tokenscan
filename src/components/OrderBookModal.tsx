import React, { useState, useRef, useEffect } from 'react';
import { X, Move } from 'lucide-react';
import { useTimeZone } from '../contexts/TimeZoneContext';
import { formatTime } from '../utils/timeUtils';

interface OrderBookModalProps {
  orderBook: {
    bids: Array<[number, number]>;
    asks: Array<[number, number]>;
    timestamp: string;
  };
  alertPrice: number;
  symbol: string;
  onClose: () => void;
}

const OrderBookModal: React.FC<OrderBookModalProps> = ({ 
  orderBook, 
  alertPrice, 
  symbol, 
  onClose 
}) => {
  const [position, setPosition] = useState({ x: 100, y: 100 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 });
  const modalRef = useRef<HTMLDivElement>(null);
  
  const { timeZone } = useTimeZone();

  const handleMouseDown = (e: React.MouseEvent) => {
    if (modalRef.current) {
      const rect = modalRef.current.getBoundingClientRect();
      setDragOffset({
        x: e.clientX - rect.left,
        y: e.clientY - rect.top
      });
      setIsDragging(true);
    }
  };

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (isDragging) {
        setPosition({
          x: e.clientX - dragOffset.x,
          y: e.clientY - dragOffset.y
        });
      }
    };

    const handleMouseUp = () => {
      setIsDragging(false);
    };

    if (isDragging) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
    }

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDragging, dragOffset]);

  const bids = orderBook.bids.slice(0, 20);
  const asks = orderBook.asks.slice(0, 20);

  // Находим максимальный объем для нормализации
  const maxVolume = Math.max(
    ...bids.map(([, volume]) => volume),
    ...asks.map(([, volume]) => volume)
  );

  const formatVolume = (volume: number) => {
    if (volume >= 1000000) {
      return `${(volume / 1000000).toFixed(1)}M`;
    } else if (volume >= 1000) {
      return `${(volume / 1000).toFixed(1)}K`;
    }
    return volume.toFixed(0);
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-30 flex items-start justify-start z-[60]">
      <div
        ref={modalRef}
        className="bg-white rounded-lg shadow-2xl border border-gray-300 w-96 select-none"
        style={{
          position: 'absolute',
          left: position.x,
          top: position.y,
          cursor: isDragging ? 'grabbing' : 'default'
        }}
      >
        {/* Header */}
        <div
          className="flex items-center justify-between p-4 border-b border-gray-200 bg-gray-50 rounded-t-lg cursor-grab active:cursor-grabbing"
          onMouseDown={handleMouseDown}
        >
          <div className="flex items-center space-x-2">
            <Move className="w-4 h-4 text-gray-400" />
            <h3 className="text-lg font-semibold text-gray-900">
              Стакан заявок - {symbol}
            </h3>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 p-1"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Order Book Content */}
        <div className="p-4 max-h-96 overflow-y-auto">
          {/* Продажи (Asks) - сверху */}
          <div className="mb-4">
            <div className="text-sm text-red-600 mb-3 font-semibold text-center">
              Продажи (Asks) - в USDT
            </div>
            <div className="space-y-1">
              {asks.reverse().map(([price, volume], i) => {
                const volumeUSDT = price * volume;
                const widthPercent = (volume / maxVolume) * 100;
                const isNearAlert = Math.abs(price - alertPrice) / alertPrice < 0.001;
                
                return (
                  <div key={i} className={`relative flex justify-between text-xs py-2 px-3 rounded ${
                    isNearAlert ? 'bg-yellow-100 border border-yellow-300' : 'hover:bg-red-50'
                  }`}>
                    <div 
                      className="absolute left-0 top-0 h-full bg-red-100 opacity-70 rounded"
                      style={{ width: `${widthPercent}%` }}
                    />
                    <span className="relative z-10 text-gray-900 font-mono font-medium">
                      ${price.toFixed(6)}
                    </span>
                    <span className="relative z-10 text-red-600 font-semibold">
                      ${volumeUSDT >= 1000 ? (volumeUSDT / 1000).toFixed(1) + 'K' : volumeUSDT.toFixed(0)}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Линия алерта */}
          <div className="border-t-3 border-yellow-500 my-4 relative bg-yellow-50 py-2">
            <div className="text-center">
              <div className="inline-block bg-yellow-500 text-white text-sm px-3 py-1 rounded-full font-semibold">
                Уровень алерта: ${alertPrice.toFixed(6)}
              </div>
            </div>
          </div>
          
          {/* Покупки (Bids) - снизу */}
          <div>
            <div className="text-sm text-green-600 mb-3 font-semibold text-center">
              Покупки (Bids) - в USDT
            </div>
            <div className="space-y-1">
              {bids.map(([price, volume], i) => {
                const volumeUSDT = price * volume;
                const widthPercent = (volume / maxVolume) * 100;
                const isNearAlert = Math.abs(price - alertPrice) / alertPrice < 0.001;
                
                return (
                  <div key={i} className={`relative flex justify-between text-xs py-2 px-3 rounded ${
                    isNearAlert ? 'bg-yellow-100 border border-yellow-300' : 'hover:bg-green-50'
                  }`}>
                    <div 
                      className="absolute left-0 top-0 h-full bg-green-100 opacity-70 rounded"
                      style={{ width: `${widthPercent}%` }}
                    />
                    <span className="relative z-10 text-gray-900 font-mono font-medium">
                      ${price.toFixed(6)}
                    </span>
                    <span className="relative z-10 text-green-600 font-semibold">
                      ${volumeUSDT >= 1000 ? (volumeUSDT / 1000).toFixed(1) + 'K' : volumeUSDT.toFixed(0)}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-gray-200 bg-gray-50 rounded-b-lg">
          <div className="text-xs text-gray-500 text-center">
            <div>Снимок: {formatTime(orderBook.timestamp, timeZone)}</div>
            <div className="mt-1">Объемы показаны в USDT • Перетаскивайте окно за заголовок</div>
            <div className="mt-1">Часовой пояс: {timeZone === 'UTC' ? 'UTC' : 'Локальное время'}</div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default OrderBookModal;