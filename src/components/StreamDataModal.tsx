import React from 'react';
import { X, Wifi, WifiOff } from 'lucide-react';

interface StreamData {
  symbol: string;
  price: number;
  volume: number;
  volume_usdt: number;
  is_long: boolean;
  timestamp: string;
  change_24h?: number;
}

interface StreamDataModalProps {
  streamData: StreamData[];
  connectionStatus: 'connecting' | 'connected' | 'disconnected';
  onClose: () => void;
}

const StreamDataModal: React.FC<StreamDataModalProps> = ({ 
  streamData, 
  connectionStatus, 
  onClose 
}) => {
  const formatTime = (timestamp: string) => {
    return new Date(timestamp).toLocaleString('ru-RU', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    });
  };

  const formatVolume = (volume: number) => {
    if (volume >= 1000000) {
      return `${(volume / 1000000).toFixed(1)}M`;
    } else if (volume >= 1000) {
      return `${(volume / 1000).toFixed(1)}K`;
    }
    return volume.toFixed(0);
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
      <div className="bg-gray-800 rounded-lg w-full max-w-6xl h-[80vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-700">
          <div className="flex items-center space-x-3">
            <h2 className="text-2xl font-bold text-white">Потоковые данные с биржи</h2>
            <div className="flex items-center space-x-2">
              {connectionStatus === 'connected' ? (
                <Wifi className="w-5 h-5 text-green-400" />
              ) : (
                <WifiOff className="w-5 h-5 text-red-400" />
              )}
              <span className="text-sm text-gray-400">
                {connectionStatus === 'connected' ? 'Подключено' : 
                 connectionStatus === 'connecting' ? 'Подключение...' : 'Отключено'}
              </span>
            </div>
          </div>
          
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white p-2"
          >
            <X className="w-6 h-6" />
          </button>
        </div>

        {/* Stream Data */}
        <div className="flex-1 overflow-y-auto p-6">
          {streamData.length === 0 ? (
            <div className="flex items-center justify-center h-full">
              <div className="text-center">
                <div className="animate-pulse rounded-full h-12 w-12 bg-blue-500 mx-auto mb-4"></div>
                <p className="text-gray-400">Ожидание потоковых данных...</p>
              </div>
            </div>
          ) : (
            <div className="space-y-2">
              {streamData.map((item, index) => (
                <div 
                  key={`${item.symbol}-${index}`} 
                  className="bg-gray-700 rounded-lg p-4 border border-gray-600 hover:border-gray-500 transition-colors"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-4">
                      <div className={`w-4 h-4 rounded-full ${
                        item.is_long ? 'bg-green-400' : 'bg-red-400'
                      }`}></div>
                      
                      <div>
                        <span className="font-semibold text-white text-lg">{item.symbol}</span>
                        <div className="flex items-center space-x-2 text-sm">
                          <span className={`px-2 py-1 rounded text-xs font-medium ${
                            item.is_long ? 'bg-green-900 text-green-300' : 'bg-red-900 text-red-300'
                          }`}>
                            {item.is_long ? 'LONG' : 'SHORT'}
                          </span>
                          {item.change_24h && (
                            <span className={`text-xs ${
                              item.change_24h > 0 ? 'text-green-400' : 'text-red-400'
                            }`}>
                              {item.change_24h > 0 ? '+' : ''}{item.change_24h.toFixed(2)}%
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                    
                    <div className="text-right">
                      <div className="text-xl font-bold text-white">
                        ${item.price.toFixed(8)}
                      </div>
                      <div className="text-sm text-gray-400">
                        Vol: ${formatVolume(item.volume_usdt)}
                      </div>
                    </div>
                    
                    <div className="text-right text-sm text-gray-500">
                      <div>{formatTime(item.timestamp)}</div>
                      <div className="text-xs">
                        {formatVolume(item.volume)} {item.symbol.replace('USDT', '')}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-6 border-t border-gray-700 bg-gray-900">
          <div className="flex justify-between items-center text-sm text-gray-400">
            <span>Обновлений: {streamData.length}</span>
            <span>Статус: {
              connectionStatus === 'connected' ? '🟢 Активно' : 
              connectionStatus === 'connecting' ? '🟡 Подключение' : '🔴 Отключено'
            }</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default StreamDataModal;