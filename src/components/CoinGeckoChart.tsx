import React, { useEffect, useState } from 'react';
import { X, ExternalLink, TrendingUp, TrendingDown, RefreshCw, AlertTriangle } from 'lucide-react';

interface CoinGeckoChartProps {
  symbol: string;
  onClose: () => void;
}

interface CoinData {
  id: string;
  name: string;
  current_price: number;
  price_change_percentage_24h: number;
  market_cap: number;
  total_volume: number;
  image: string;
  symbol: string;
}

const CoinGeckoChart: React.FC<CoinGeckoChartProps> = ({ symbol, onClose }) => {
  const [coinData, setCoinData] = useState<CoinData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [days, setDays] = useState('7');
  const [chartError, setChartError] = useState(false);

  useEffect(() => {
    loadCoinData();
  }, [symbol]);

  const loadCoinData = async () => {
    try {
      setLoading(true);
      setError(null);
      setChartError(false);

      // Преобразуем символ (например, BTCUSDT -> bitcoin)
      const coinId = getCoinId(symbol);
      
      if (!coinId) {
        // Если не нашли в маппинге, попробуем поиск по символу
        const searchResult = await searchCoinBySymbol(symbol);
        if (!searchResult) {
          setError('Криптовалюта не найдена в CoinGecko');
          setLoading(false);
          return;
        }
        setCoinData(searchResult);
        setLoading(false);
        return;
      }

      // Загружаем данные о монете
      const response = await fetch(
        `https://api.coingecko.com/api/v3/coins/${coinId}?localization=false&tickers=false&market_data=true&community_data=false&developer_data=false&sparkline=false`
      );

      if (!response.ok) {
        throw new Error(`Ошибка загрузки данных CoinGecko: ${response.status}`);
      }

      const data = await response.json();
      
      setCoinData({
        id: data.id,
        name: data.name,
        symbol: data.symbol.toUpperCase(),
        current_price: data.market_data.current_price.usd,
        price_change_percentage_24h: data.market_data.price_change_percentage_24h,
        market_cap: data.market_data.market_cap.usd,
        total_volume: data.market_data.total_volume.usd,
        image: data.image.large
      });

    } catch (err) {
      console.error('CoinGecko API error:', err);
      setError(err instanceof Error ? err.message : 'Неизвестная ошибка');
    } finally {
      setLoading(false);
    }
  };

  const searchCoinBySymbol = async (symbol: string): Promise<CoinData | null> => {
    try {
      // Убираем USDT из символа для поиска
      const cleanSymbol = symbol.replace('USDT', '').toLowerCase();
      
      // Поиск по символу
      const searchResponse = await fetch(
        `https://api.coingecko.com/api/v3/search?query=${cleanSymbol}`
      );
      
      if (!searchResponse.ok) {
        return null;
      }
      
      const searchData = await searchResponse.json();
      const coin = searchData.coins?.find((c: any) => 
        c.symbol.toLowerCase() === cleanSymbol
      );
      
      if (!coin) {
        return null;
      }
      
      // Загружаем полные данные найденной монеты
      const coinResponse = await fetch(
        `https://api.coingecko.com/api/v3/coins/${coin.id}?localization=false&tickers=false&market_data=true&community_data=false&developer_data=false&sparkline=false`
      );
      
      if (!coinResponse.ok) {
        return null;
      }
      
      const coinData = await coinResponse.json();
      
      return {
        id: coinData.id,
        name: coinData.name,
        symbol: coinData.symbol.toUpperCase(),
        current_price: coinData.market_data.current_price.usd,
        price_change_percentage_24h: coinData.market_data.price_change_percentage_24h,
        market_cap: coinData.market_data.market_cap.usd,
        total_volume: coinData.market_data.total_volume.usd,
        image: coinData.image.large
      };
      
    } catch (error) {
      console.error('Ошибка поиска монеты:', error);
      return null;
    }
  };

  const getCoinId = (symbol: string): string | null => {
    // Маппинг популярных символов на ID CoinGecko
    const symbolMap: { [key: string]: string } = {
      'BTCUSDT': 'bitcoin',
      'ETHUSDT': 'ethereum',
      'BNBUSDT': 'binancecoin',
      'ADAUSDT': 'cardano',
      'SOLUSDT': 'solana',
      'XRPUSDT': 'ripple',
      'DOTUSDT': 'polkadot',
      'DOGEUSDT': 'dogecoin',
      'AVAXUSDT': 'avalanche-2',
      'SHIBUSDT': 'shiba-inu',
      'MATICUSDT': 'matic-network',
      'LTCUSDT': 'litecoin',
      'UNIUSDT': 'uniswap',
      'LINKUSDT': 'chainlink',
      'ATOMUSDT': 'cosmos',
      'ETCUSDT': 'ethereum-classic',
      'XLMUSDT': 'stellar',
      'BCHUSDT': 'bitcoin-cash',
      'FILUSDT': 'filecoin',
      'TRXUSDT': 'tron',
      'EOSUSDT': 'eos',
      'AAVEUSDT': 'aave',
      'MKRUSDT': 'maker',
      'COMPUSDT': 'compound-governance-token',
      'ALGOUSDT': 'algorand',
      'VETUSDT': 'vechain',
      'ICPUSDT': 'internet-computer',
      'FTMUSDT': 'fantom',
      'SANDUSDT': 'the-sandbox',
      'MANAUSDT': 'decentraland',
      'AXSUSDT': 'axie-infinity',
      'THETAUSDT': 'theta-token',
      'XTZUSDT': 'tezos',
      'EGLDUSDT': 'elrond-erd-2',
      'KLAYUSDT': 'klay-token',
      'NEARUSDT': 'near',
      'FLOWUSDT': 'flow',
      'IOTAUSDT': 'iota',
      'XMRUSDT': 'monero',
      'ZECUSDT': 'zcash',
      'DASHUSDT': 'dash',
      'NEOUSDT': 'neo',
      'QTUMUSDT': 'qtum',
      'OMGUSDT': 'omisego',
      'BATUSDT': 'basic-attention-token',
      'ZRXUSDT': '0x',
      'ENJUSDT': 'enjincoin',
      'CHZUSDT': 'chiliz',
      'HOTUSDT': 'holotoken',
      'ZILUSDT': 'zilliqa',
      'RVNUSDT': 'ravencoin',
      'SCUSDT': 'siacoin',
      'DGBUSDT': 'digibyte',
      'WAVESUSDT': 'waves',
      'ZENUSDT': 'zencash',
      'ONTUSDT': 'ontology',
      'FETUSDT': 'fetch-ai',
      'CELRUSDT': 'celer-network',
      'BANDUSDT': 'band-protocol'
    };

    return symbolMap[symbol] || null;
  };

  const formatNumber = (num: number): string => {
    if (num >= 1e9) {
      return `$${(num / 1e9).toFixed(2)}B`;
    } else if (num >= 1e6) {
      return `$${(num / 1e6).toFixed(2)}M`;
    } else if (num >= 1e3) {
      return `$${(num / 1e3).toFixed(2)}K`;
    }
    return `$${num.toFixed(2)}`;
  };

  const openCoinGecko = () => {
    if (coinData) {
      window.open(`https://www.coingecko.com/en/coins/${coinData.id}`, '_blank');
    }
  };

  const chartUrl = coinData ? 
    `https://www.coingecko.com/en/coins/${coinData.id}/embedded_chart?locale=en&vs_currency=usd&days=${days}` : 
    '';

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-lg w-full max-w-4xl h-[80vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200">
          <div className="flex items-center space-x-4">
            {coinData && (
              <img 
                src={coinData.image} 
                alt={coinData.name}
                className="w-8 h-8 rounded-full"
                onError={(e) => {
                  // Fallback если изображение не загружается
                  (e.target as HTMLImageElement).style.display = 'none';
                }}
              />
            )}
            <div>
              <h2 className="text-2xl font-bold text-gray-900">
                {coinData ? `${coinData.name} (${coinData.symbol})` : symbol}
              </h2>
              <p className="text-gray-600">Данные CoinGecko</p>
            </div>
          </div>
          
          <div className="flex items-center space-x-3">
            {/* Кнопка обновления */}
            <button
              onClick={loadCoinData}
              disabled={loading}
              className="flex items-center space-x-2 bg-gray-100 hover:bg-gray-200 text-gray-700 px-3 py-2 rounded-lg transition-colors disabled:opacity-50"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
              <span>Обновить</span>
            </button>

            {/* Период графика */}
            <div className="flex items-center space-x-1 bg-gray-100 rounded-lg p-1">
              {[
                { value: '1', label: '1д' },
                { value: '7', label: '7д' },
                { value: '30', label: '30д' },
                { value: '90', label: '90д' },
                { value: '365', label: '1г' }
              ].map((period) => (
                <button
                  key={period.value}
                  onClick={() => setDays(period.value)}
                  className={`px-3 py-1 text-sm rounded transition-colors ${
                    days === period.value
                      ? 'bg-blue-600 text-white'
                      : 'text-gray-600 hover:bg-gray-200'
                  }`}
                >
                  {period.label}
                </button>
              ))}
            </div>

            <button
              onClick={openCoinGecko}
              className="flex items-center space-x-2 bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded-lg transition-colors"
            >
              <ExternalLink className="w-4 h-4" />
              <span>CoinGecko</span>
            </button>
            
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600 p-2"
            >
              <X className="w-6 h-6" />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 p-6">
          {loading ? (
            <div className="flex items-center justify-center h-full">
              <div className="text-center">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-green-500 mx-auto mb-4"></div>
                <p className="text-gray-600">Загрузка данных CoinGecko...</p>
              </div>
            </div>
          ) : error ? (
            <div className="flex items-center justify-center h-full">
              <div className="text-center">
                <AlertTriangle className="w-12 h-12 text-red-500 mx-auto mb-4" />
                <p className="text-red-600 mb-4">Ошибка: {error}</p>
                <button
                  onClick={loadCoinData}
                  className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg transition-colors"
                >
                  Попробовать снова
                </button>
              </div>
            </div>
          ) : coinData ? (
            <div className="h-full flex flex-col">
              {/* Статистика */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                <div className="bg-gray-50 p-4 rounded-lg">
                  <div className="text-sm text-gray-600">Цена</div>
                  <div className="text-xl font-bold text-gray-900">
                    {formatNumber(coinData.current_price)}
                  </div>
                </div>
                
                <div className="bg-gray-50 p-4 rounded-lg">
                  <div className="text-sm text-gray-600">Изменение 24ч</div>
                  <div className={`text-xl font-bold flex items-center ${
                    coinData.price_change_percentage_24h >= 0 ? 'text-green-600' : 'text-red-600'
                  }`}>
                    {coinData.price_change_percentage_24h >= 0 ? (
                      <TrendingUp className="w-5 h-5 mr-1" />
                    ) : (
                      <TrendingDown className="w-5 h-5 mr-1" />
                    )}
                    {Math.abs(coinData.price_change_percentage_24h).toFixed(2)}%
                  </div>
                </div>
                
                <div className="bg-gray-50 p-4 rounded-lg">
                  <div className="text-sm text-gray-600">Рыночная капитализация</div>
                  <div className="text-xl font-bold text-gray-900">
                    {formatNumber(coinData.market_cap)}
                  </div>
                </div>
                
                <div className="bg-gray-50 p-4 rounded-lg">
                  <div className="text-sm text-gray-600">Объем торгов 24ч</div>
                  <div className="text-xl font-bold text-gray-900">
                    {formatNumber(coinData.total_volume)}
                  </div>
                </div>
              </div>

              {/* График */}
              <div className="flex-1 bg-gray-50 rounded-lg overflow-hidden">
                {chartUrl && !chartError ? (
                  <iframe
                    src={chartUrl}
                    width="100%"
                    height="100%"
                    frameBorder="0"
                    title={`${coinData.name} Chart`}
                    className="w-full h-full"
                    onError={() => {
                      console.error('Chart iframe failed to load');
                      setChartError(true);
                    }}
                    onLoad={() => {
                      console.log('Chart iframe loaded successfully');
                    }}
                  />
                ) : (
                  <div className="flex items-center justify-center h-full">
                    <div className="text-center">
                      <AlertTriangle className="w-8 h-8 text-yellow-500 mx-auto mb-2" />
                      <p className="text-gray-600 mb-4">График временно недоступен</p>
                      <button
                        onClick={() => setChartError(false)}
                        className="bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded-lg transition-colors"
                      >
                        Попробовать снова
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-center h-full">
              <p className="text-gray-600">Нет данных для отображения</p>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-gray-200 bg-gray-50">
          <div className="flex justify-between items-center text-sm text-gray-600">
            <span>Данные предоставлены CoinGecko API</span>
            <span>Обновляется каждые 5 минут</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default CoinGeckoChart;