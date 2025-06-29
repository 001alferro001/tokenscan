import React, { useState, useEffect } from 'react';
import { X, Calculator, TrendingUp, TrendingDown, DollarSign, Target, AlertTriangle, BarChart3, Settings, Shield, RefreshCw } from 'lucide-react';
import { formatTime } from '../utils/timeUtils';
import { useTimeZone } from '../contexts/TimeZoneContext';

interface RealTradingModalProps {
  symbol?: string;
  alertPrice?: number;
  alertId?: number;
  onClose: () => void;
}

interface TradingSettings {
  account_balance: number;
  max_risk_per_trade: number;
  max_open_trades: number;
  default_stop_loss_percentage: number;
  default_take_profit_percentage: number;
  auto_calculate_quantity: boolean;
  api_key?: string;
  api_secret?: string;
  enable_real_trading?: boolean;
  default_leverage?: number;
  default_margin_type?: 'isolated' | 'cross';
  confirm_trades?: boolean;
}

interface RealTrade {
  id: number;
  symbol: string;
  trade_type: string;
  entry_price: number;
  quantity: number;
  stop_loss?: number;
  take_profit?: number;
  risk_amount: number;
  risk_percentage: number;
  potential_profit?: number;
  potential_loss?: number;
  risk_reward_ratio?: number;
  status: string;
  exit_price?: number;
  exit_reason?: string;
  pnl?: number;
  pnl_percentage?: number;
  notes?: string;
  opened_at_ms: number;
  closed_at_ms?: number;
  alert_id?: number;
  order_id?: string;
  leverage: number;
  margin_type: string;
}

interface RiskCalculation {
  entry_price: number;
  stop_loss?: number;
  take_profit?: number;
  trade_type: string;
  account_balance: number;
  risk_amount: number;
  risk_percentage: number;
  quantity?: number;
  position_size?: number;
  potential_profit?: number;
  potential_profit_percentage?: number;
  potential_loss?: number;
  potential_loss_percentage?: number;
  risk_reward_ratio?: number;
  error?: string;
}

interface TradingStatistics {
  total_trades: number;
  open_trades: number;
  closed_trades: number;
  winning_trades: number;
  losing_trades: number;
  win_rate: number;
  total_pnl: number;
  avg_pnl_percentage: number;
  max_profit: number;
  max_loss: number;
}

interface AccountInfo {
  balance: number;
  available_balance: number;
  used_margin: number;
  unrealized_pnl: number;
  open_positions: number;
}

const RealTradingModal: React.FC<RealTradingModalProps> = ({ 
  symbol = '', 
  alertPrice, 
  alertId,
  onClose 
}) => {
  const [activeTab, setActiveTab] = useState<'calculator' | 'trades' | 'positions'>('calculator');
  const [tradeType, setTradeType] = useState<'LONG' | 'SHORT'>('LONG');
  const [entryPrice, setEntryPrice] = useState<number>(alertPrice || 0);
  const [stopLoss, setStopLoss] = useState<number | undefined>(undefined);
  const [takeProfit, setTakeProfit] = useState<number | undefined>(undefined);
  const [quantity, setQuantity] = useState<number | undefined>(undefined);
  const [riskAmount, setRiskAmount] = useState<number>(100);
  const [riskPercentage, setRiskPercentage] = useState<number>(1);
  const [notes, setNotes] = useState<string>('');
  const [calculation, setCalculation] = useState<RiskCalculation | null>(null);
  const [settings, setSettings] = useState<TradingSettings | null>(null);
  const [trades, setTrades] = useState<RealTrade[]>([]);
  const [statistics, setStatistics] = useState<TradingStatistics | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [symbolInput, setSymbolInput] = useState(symbol);
  const [selectedTradeId, setSelectedTradeId] = useState<number | null>(null);
  const [exitPrice, setExitPrice] = useState<number>(0);
  const [exitReason, setExitReason] = useState<string>('MANUAL');
  const [stopLossPercentage, setStopLossPercentage] = useState<number>(2);
  const [takeProfitPercentage, setTakeProfitPercentage] = useState<number>(6);
  const [leverage, setLeverage] = useState<number>(1);
  const [marginType, setMarginType] = useState<'isolated' | 'cross'>('isolated');
  const [accountInfo, setAccountInfo] = useState<AccountInfo | null>(null);
  const [confirmTradeOpen, setConfirmTradeOpen] = useState(false);
  const [confirmTradeClose, setConfirmTradeClose] = useState(false);
  const [apiConnected, setApiConnected] = useState(false);
  const [apiCheckLoading, setApiCheckLoading] = useState(false);
  
  const { timeZone } = useTimeZone();

  useEffect(() => {
    loadSettings();
    loadTrades();
    loadStatistics();
    checkApiConnection();
    
    if (symbol) {
      setSymbolInput(symbol);
    }
    
    if (alertPrice) {
      setEntryPrice(alertPrice);
      calculateDefaultLevels(alertPrice);
    }
  }, [symbol, alertPrice]);

  useEffect(() => {
    if (settings && entryPrice > 0) {
      calculateRisk();
    }
  }, [settings, entryPrice, stopLoss, takeProfit, riskAmount, riskPercentage, tradeType, leverage]);

  const loadSettings = async () => {
    try {
      const response = await fetch('/api/settings');
      if (response.ok) {
        const data = await response.json();
        if (data.trading) {
          setSettings(data.trading);
          
          // Устанавливаем значения по умолчанию из настроек
          setRiskPercentage(data.trading.max_risk_per_trade || 2);
          setStopLossPercentage(data.trading.default_stop_loss_percentage || 2);
          setTakeProfitPercentage(data.trading.default_take_profit_percentage || 6);
          setLeverage(data.trading.default_leverage || 1);
          setMarginType(data.trading.default_margin_type || 'isolated');
        }
      }
    } catch (error) {
      console.error('Ошибка загрузки настроек торговли:', error);
    }
  };

  const checkApiConnection = async () => {
    try {
      setApiCheckLoading(true);
      const response = await fetch('/api/trading/account-info');
      if (response.ok) {
        const data = await response.json();
        setAccountInfo(data);
        setApiConnected(true);
      } else {
        setApiConnected(false);
      }
    } catch (error) {
      console.error('Ошибка проверки API соединения:', error);
      setApiConnected(false);
    } finally {
      setApiCheckLoading(false);
    }
  };

  const loadTrades = async () => {
    try {
      const response = await fetch('/api/trading/real-trades');
      if (response.ok) {
        const data = await response.json();
        setTrades(data.trades || []);
      }
    } catch (error) {
      console.error('Ошибка загрузки сделок:', error);
    }
  };

  const loadStatistics = async () => {
    try {
      const response = await fetch('/api/trading/real-statistics');
      if (response.ok) {
        const data = await response.json();
        setStatistics(data.statistics || null);
      }
    } catch (error) {
      console.error('Ошибка загрузки статистики:', error);
    }
  };

  const calculateDefaultLevels = (price: number) => {
    if (settings) {
      const slPercentage = settings.default_stop_loss_percentage || 2;
      const tpPercentage = settings.default_take_profit_percentage || 6;
      
      if (tradeType === 'LONG') {
        setStopLoss(parseFloat((price * (1 - slPercentage / 100)).toFixed(8)));
        setTakeProfit(parseFloat((price * (1 + tpPercentage / 100)).toFixed(8)));
      } else {
        setStopLoss(parseFloat((price * (1 + slPercentage / 100)).toFixed(8)));
        setTakeProfit(parseFloat((price * (1 - tpPercentage / 100)).toFixed(8)));
      }
    }
  };

  const calculateRisk = async () => {
    if (!entryPrice) {
      setError('Введите цену входа');
      return;
    }

    try {
      setLoading(true);
      setError(null);
      
      const requestData = {
        entry_price: entryPrice,
        stop_loss: stopLoss,
        take_profit: takeProfit,
        risk_amount: riskAmount,
        risk_percentage: riskPercentage,
        account_balance: accountInfo?.available_balance || settings?.account_balance,
        trade_type: tradeType,
        leverage: leverage
      };
      
      const response = await fetch('/api/trading/calculate-risk', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestData),
      });
      
      if (response.ok) {
        const data = await response.json();
        setCalculation(data);
        
        // Обновляем поля на основе расчета
        if (data.quantity) {
          setQuantity(data.quantity);
        }
      } else {
        const error = await response.json();
        setError(error.detail || 'Ошибка расчета риска');
      }
    } catch (error) {
      console.error('Ошибка расчета риска:', error);
      setError('Ошибка расчета риска');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateTrade = async () => {
    if (!symbolInput || !entryPrice || !quantity) {
      setError('Заполните обязательные поля: символ, цена входа, количество');
      return;
    }

    if (!apiConnected) {
      setError('API не подключено. Проверьте настройки API ключей.');
      return;
    }

    // Проверяем, нужно ли подтверждение
    if (settings?.confirm_trades && !confirmTradeOpen) {
      setConfirmTradeOpen(true);
      return;
    }

    try {
      setLoading(true);
      setError(null);
      
      const tradeData = {
        symbol: symbolInput.toUpperCase(),
        trade_type: tradeType,
        entry_price: entryPrice,
        quantity: quantity,
        stop_loss: stopLoss,
        take_profit: takeProfit,
        risk_amount: calculation?.risk_amount || riskAmount,
        risk_percentage: calculation?.risk_percentage || riskPercentage,
        notes: notes,
        alert_id: alertId,
        leverage: leverage,
        margin_type: marginType
      };
      
      const response = await fetch('/api/trading/real-trades', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(tradeData),
      });
      
      if (response.ok) {
        const data = await response.json();
        setSuccess(`Сделка успешно создана (ID: ${data.trade_id}). Ордер отправлен на биржу.`);
        
        // Очищаем форму
        if (!symbol) {
          setSymbolInput('');
        }
        setStopLoss(undefined);
        setTakeProfit(undefined);
        setQuantity(undefined);
        setNotes('');
        setConfirmTradeOpen(false);
        
        // Обновляем список сделок и статистику
        loadTrades();
        loadStatistics();
        checkApiConnection();
        
        // Переключаемся на вкладку сделок
        setActiveTab('trades');
        
        // Сбрасываем сообщение об успехе через 3 секунды
        setTimeout(() => {
          setSuccess(null);
        }, 3000);
      } else {
        const error = await response.json();
        setError(error.detail || 'Ошибка создания сделки');
        setConfirmTradeOpen(false);
      }
    } catch (error) {
      console.error('Ошибка создания сделки:', error);
      setError('Ошибка создания сделки');
      setConfirmTradeOpen(false);
    } finally {
      setLoading(false);
    }
  };

  const handleCloseTrade = async (tradeId: number) => {
    if (!exitPrice) {
      setError('Введите цену выхода');
      return;
    }

    if (!apiConnected) {
      setError('API не подключено. Проверьте настройки API ключей.');
      return;
    }

    // Проверяем, нужно ли подтверждение
    if (settings?.confirm_trades && !confirmTradeClose) {
      setConfirmTradeClose(true);
      return;
    }

    try {
      setLoading(true);
      setError(null);
      
      const response = await fetch(`/api/trading/real-trades/${tradeId}/close`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          exit_price: exitPrice,
          exit_reason: exitReason
        }),
      });
      
      if (response.ok) {
        setSuccess('Сделка успешно закрыта. Ордер отправлен на биржу.');
        setSelectedTradeId(null);
        setExitPrice(0);
        setExitReason('MANUAL');
        setConfirmTradeClose(false);
        
        // Обновляем список сделок и статистику
        loadTrades();
        loadStatistics();
        checkApiConnection();
        
        // Сбрасываем сообщение об успехе через 3 секунды
        setTimeout(() => {
          setSuccess(null);
        }, 3000);
      } else {
        const error = await response.json();
        setError(error.detail || 'Ошибка закрытия сделки');
        setConfirmTradeClose(false);
      }
    } catch (error) {
      console.error('Ошибка закрытия сделки:', error);
      setError('Ошибка закрытия сделки');
      setConfirmTradeClose(false);
    } finally {
      setLoading(false);
    }
  };

  const handleStopLossPercentageChange = (percentage: number) => {
    setStopLossPercentage(percentage);
    if (entryPrice) {
      if (tradeType === 'LONG') {
        setStopLoss(parseFloat((entryPrice * (1 - percentage / 100)).toFixed(8)));
      } else {
        setStopLoss(parseFloat((entryPrice * (1 + percentage / 100)).toFixed(8)));
      }
    }
  };

  const handleTakeProfitPercentageChange = (percentage: number) => {
    setTakeProfitPercentage(percentage);
    if (entryPrice) {
      if (tradeType === 'LONG') {
        setTakeProfit(parseFloat((entryPrice * (1 + percentage / 100)).toFixed(8)));
      } else {
        setTakeProfit(parseFloat((entryPrice * (1 - percentage / 100)).toFixed(8)));
      }
    }
  };

  const handleStopLossChange = (value: number) => {
    setStopLoss(value);
    if (entryPrice) {
      if (tradeType === 'LONG') {
        setStopLossPercentage(parseFloat((((entryPrice - value) / entryPrice) * 100).toFixed(2)));
      } else {
        setStopLossPercentage(parseFloat((((value - entryPrice) / entryPrice) * 100).toFixed(2)));
      }
    }
  };

  const handleTakeProfitChange = (value: number) => {
    setTakeProfit(value);
    if (entryPrice) {
      if (tradeType === 'LONG') {
        setTakeProfitPercentage(parseFloat((((value - entryPrice) / entryPrice) * 100).toFixed(2)));
      } else {
        setTakeProfitPercentage(parseFloat((((entryPrice - value) / entryPrice) * 100).toFixed(2)));
      }
    }
  };

  const handleTradeTypeChange = (type: 'LONG' | 'SHORT') => {
    setTradeType(type);
    // Пересчитываем стоп-лосс и тейк-профит при смене типа сделки
    if (entryPrice) {
      if (type === 'LONG') {
        setStopLoss(parseFloat((entryPrice * (1 - stopLossPercentage / 100)).toFixed(8)));
        setTakeProfit(parseFloat((entryPrice * (1 + takeProfitPercentage / 100)).toFixed(8)));
      } else {
        setStopLoss(parseFloat((entryPrice * (1 + stopLossPercentage / 100)).toFixed(8)));
        setTakeProfit(parseFloat((entryPrice * (1 - takeProfitPercentage / 100)).toFixed(8)));
      }
    }
  };

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('ru-RU', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    }).format(value);
  };

  const formatPercentage = (value: number) => {
    return `${value.toFixed(2)}%`;
  };

  const formatCrypto = (value: number, precision: number = 8) => {
    return value.toFixed(precision);
  };

  const getTradeStatusBadge = (status: string) => {
    switch (status) {
      case 'OPEN':
        return <span className="px-2 py-1 bg-blue-100 text-blue-800 text-xs rounded-full">Открыта</span>;
      case 'CLOSED':
        return <span className="px-2 py-1 bg-green-100 text-green-800 text-xs rounded-full">Закрыта</span>;
      case 'CANCELLED':
        return <span className="px-2 py-1 bg-gray-100 text-gray-800 text-xs rounded-full">Отменена</span>;
      case 'PENDING':
        return <span className="px-2 py-1 bg-yellow-100 text-yellow-800 text-xs rounded-full">В ожидании</span>;
      case 'ERROR':
        return <span className="px-2 py-1 bg-red-100 text-red-800 text-xs rounded-full">Ошибка</span>;
      default:
        return <span className="px-2 py-1 bg-gray-100 text-gray-800 text-xs rounded-full">{status}</span>;
    }
  };

  const getPnLBadge = (pnl?: number, pnlPercentage?: number) => {
    if (pnl === undefined) return null;
    
    const isPositive = pnl >= 0;
    
    return (
      <span className={`px-2 py-1 ${isPositive ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'} text-xs rounded-full`}>
        {isPositive ? '+' : ''}{formatCurrency(pnl)} ({isPositive ? '+' : ''}{pnlPercentage?.toFixed(2)}%)
      </span>
    );
  };

  const renderCalculatorTab = () => (
    <div className="space-y-6">
      {!apiConnected && (
        <div className="bg-red-50 p-4 rounded-lg flex items-start space-x-3">
          <AlertTriangle className="w-5 h-5 text-red-600 mt-0.5" />
          <div>
            <h4 className="font-medium text-red-900">API не подключено</h4>
            <p className="text-sm text-red-700 mt-1">
              Для реальной торговли необходимо настроить API ключи в настройках системы.
              Вы можете рассчитать параметры сделки, но не сможете открыть реальную позицию.
            </p>
            <button
              onClick={checkApiConnection}
              disabled={apiCheckLoading}
              className="mt-2 flex items-center space-x-2 bg-red-600 hover:bg-red-700 disabled:bg-red-300 text-white px-3 py-1 rounded transition-colors text-sm"
            >
              {apiCheckLoading ? (
                <RefreshCw className="w-4 h-4 animate-spin" />
              ) : (
                <RefreshCw className="w-4 h-4" />
              )}
              <span>Проверить подключение</span>
            </button>
          </div>
        </div>
      )}

      {accountInfo && (
        <div className="bg-blue-50 p-4 rounded-lg">
          <h3 className="font-medium text-blue-900 mb-2 flex items-center">
            <DollarSign className="w-5 h-5 mr-2" />
            Информация об аккаунте
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div>
              <span className="text-blue-700">Баланс:</span>
              <div className="font-medium text-blue-900">{formatCurrency(accountInfo.balance)}</div>
            </div>
            <div>
              <span className="text-blue-700">Доступно:</span>
              <div className="font-medium text-blue-900">{formatCurrency(accountInfo.available_balance)}</div>
            </div>
            <div>
              <span className="text-blue-700">Используемая маржа:</span>
              <div className="font-medium text-blue-900">{formatCurrency(accountInfo.used_margin)}</div>
            </div>
            <div>
              <span className="text-blue-700">Нереализованный P&L:</span>
              <div className={`font-medium ${accountInfo.unrealized_pnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                {formatCurrency(accountInfo.unrealized_pnl)}
              </div>
            </div>
          </div>
        </div>
      )}

      <div className="bg-green-50 p-4 rounded-lg">
        <h3 className="font-medium text-green-900 mb-2 flex items-center">
          <Calculator className="w-5 h-5 mr-2" />
          Калькулятор риска и прибыли
        </h3>
        <p className="text-sm text-green-700">
          Рассчитайте оптимальный размер позиции на основе вашего риска и целевых уровней
        </p>
      </div>

      {/* Тип сделки */}
      <div className="flex space-x-4">
        <button
          onClick={() => handleTradeTypeChange('LONG')}
          className={`flex-1 py-3 px-4 rounded-lg flex items-center justify-center space-x-2 ${
            tradeType === 'LONG' 
              ? 'bg-green-600 text-white' 
              : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
          }`}
        >
          <TrendingUp className="w-5 h-5" />
          <span className="font-medium">LONG</span>
        </button>
        <button
          onClick={() => handleTradeTypeChange('SHORT')}
          className={`flex-1 py-3 px-4 rounded-lg flex items-center justify-center space-x-2 ${
            tradeType === 'SHORT' 
              ? 'bg-red-600 text-white' 
              : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
          }`}
        >
          <TrendingDown className="w-5 h-5" />
          <span className="font-medium">SHORT</span>
        </button>
      </div>

      {/* Основные параметры */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Символ *
          </label>
          <input
            type="text"
            value={symbolInput}
            onChange={(e) => setSymbolInput(e.target.value.toUpperCase())}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            placeholder="Например, BTCUSDT"
            disabled={!!symbol}
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Цена входа *
          </label>
          <input
            type="number"
            step="0.00000001"
            value={entryPrice || ''}
            onChange={(e) => setEntryPrice(parseFloat(e.target.value))}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            placeholder="Цена входа"
          />
        </div>
      </div>

      {/* Стоп-лосс и тейк-профит */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Стоп-лосс
          </label>
          <div className="flex space-x-2">
            <input
              type="number"
              step="0.00000001"
              value={stopLoss || ''}
              onChange={(e) => handleStopLossChange(parseFloat(e.target.value))}
              className="flex-1 border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              placeholder="Уровень стоп-лосса"
            />
            <div className="relative">
              <input
                type="number"
                step="0.1"
                min="0.1"
                max="50"
                value={stopLossPercentage}
                onChange={(e) => handleStopLossPercentageChange(parseFloat(e.target.value))}
                className="w-20 border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
              <span className="absolute right-3 top-2 text-gray-500">%</span>
            </div>
          </div>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Тейк-профит
          </label>
          <div className="flex space-x-2">
            <input
              type="number"
              step="0.00000001"
              value={takeProfit || ''}
              onChange={(e) => handleTakeProfitChange(parseFloat(e.target.value))}
              className="flex-1 border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              placeholder="Уровень тейк-профита"
            />
            <div className="relative">
              <input
                type="number"
                step="0.1"
                min="0.1"
                max="100"
                value={takeProfitPercentage}
                onChange={(e) => handleTakeProfitPercentageChange(parseFloat(e.target.value))}
                className="w-20 border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
              <span className="absolute right-3 top-2 text-gray-500">%</span>
            </div>
          </div>
        </div>
      </div>

      {/* Риск и плечо */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Риск в деньгах
          </label>
          <div className="relative">
            <span className="absolute left-3 top-2 text-gray-500">$</span>
            <input
              type="number"
              step="1"
              min="1"
              value={riskAmount}
              onChange={(e) => {
                setRiskAmount(parseFloat(e.target.value));
                if (accountInfo?.available_balance) {
                  setRiskPercentage(parseFloat(((parseFloat(e.target.value) / accountInfo.available_balance) * 100).toFixed(2)));
                }
              }}
              className="w-full border border-gray-300 rounded-lg pl-8 pr-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
          </div>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Риск в процентах
          </label>
          <div className="relative">
            <input
              type="number"
              step="0.1"
              min="0.1"
              max="100"
              value={riskPercentage}
              onChange={(e) => {
                setRiskPercentage(parseFloat(e.target.value));
                if (accountInfo?.available_balance) {
                  setRiskAmount(parseFloat(((accountInfo.available_balance * parseFloat(e.target.value)) / 100).toFixed(2)));
                }
              }}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
            <span className="absolute right-3 top-2 text-gray-500">%</span>
          </div>
        </div>
      </div>

      {/* Кредитное плечо и тип маржи */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Кредитное плечо
          </label>
          <div className="flex items-center space-x-2">
            <input
              type="range"
              min="1"
              max="100"
              value={leverage}
              onChange={(e) => setLeverage(parseInt(e.target.value))}
              className="flex-1"
            />
            <div className="w-16 text-center font-medium text-gray-900">
              {leverage}x
            </div>
          </div>
          <div className="flex justify-between text-xs text-gray-500 mt-1">
            <span>1x</span>
            <span>25x</span>
            <span>50x</span>
            <span>100x</span>
          </div>
        </div>
        
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Тип маржи
          </label>
          <div className="flex space-x-2">
            <button
              onClick={() => setMarginType('isolated')}
              className={`flex-1 py-2 px-3 rounded-lg text-sm font-medium transition-colors ${
                marginType === 'isolated' 
                  ? 'bg-blue-600 text-white' 
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              Изолированная
            </button>
            <button
              onClick={() => setMarginType('cross')}
              className={`flex-1 py-2 px-3 rounded-lg text-sm font-medium transition-colors ${
                marginType === 'cross' 
                  ? 'bg-blue-600 text-white' 
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              Кросс
            </button>
          </div>
        </div>
      </div>

      {/* Размер позиции */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Количество *
          </label>
          <input
            type="number"
            step="0.00000001"
            value={quantity || ''}
            onChange={(e) => setQuantity(parseFloat(e.target.value))}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            placeholder="Количество токенов"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Размер позиции
          </label>
          <div className="relative">
            <span className="absolute left-3 top-2 text-gray-500">$</span>
            <input
              type="text"
              value={quantity && entryPrice ? (quantity * entryPrice).toFixed(2) : ''}
              readOnly
              className="w-full border border-gray-300 rounded-lg pl-8 pr-3 py-2 bg-gray-50"
            />
          </div>
        </div>
      </div>

      {/* Заметки */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Заметки
        </label>
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          rows={3}
          placeholder="Заметки о сделке..."
        />
      </div>

      {/* Результаты расчета */}
      {calculation && (
        <div className="bg-gray-50 p-4 rounded-lg">
          <h3 className="font-medium text-gray-900 mb-3">Результаты расчета</h3>
          
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <span className="text-gray-600">Баланс аккаунта:</span>
              <div className="font-medium text-gray-900">{formatCurrency(calculation.account_balance)}</div>
            </div>
            
            <div>
              <span className="text-gray-600">Размер позиции:</span>
              <div className="font-medium text-gray-900">{calculation.position_size ? formatCurrency(calculation.position_size) : '-'}</div>
            </div>
            
            <div>
              <span className="text-gray-600">Риск:</span>
              <div className="font-medium text-red-600">{formatCurrency(calculation.risk_amount)} ({formatPercentage(calculation.risk_percentage)})</div>
            </div>
            
            <div>
              <span className="text-gray-600">Потенциальная прибыль:</span>
              <div className="font-medium text-green-600">
                {calculation.potential_profit 
                  ? `${formatCurrency(calculation.potential_profit)} (${formatPercentage(calculation.potential_profit_percentage || 0)})`
                  : '-'
                }
              </div>
            </div>
            
            <div>
              <span className="text-gray-600">Соотношение риск/прибыль:</span>
              <div className="font-medium text-blue-600">{calculation.risk_reward_ratio ? `1:${calculation.risk_reward_ratio.toFixed(2)}` : '-'}</div>
            </div>
            
            <div>
              <span className="text-gray-600">Количество:</span>
              <div className="font-medium text-gray-900">{calculation.quantity ? formatCrypto(calculation.quantity) : '-'}</div>
            </div>
            
            <div>
              <span className="text-gray-600">Кредитное плечо:</span>
              <div className="font-medium text-orange-600">{leverage}x</div>
            </div>
            
            <div>
              <span className="text-gray-600">Тип маржи:</span>
              <div className="font-medium text-gray-900">{marginType === 'isolated' ? 'Изолированная' : 'Кросс'}</div>
            </div>
          </div>
          
          {calculation.error && (
            <div className="mt-3 text-sm text-red-600">
              Ошибка: {calculation.error}
            </div>
          )}
        </div>
      )}

      {/* Кнопки действий */}
      <div className="flex space-x-4">
        <button
          onClick={calculateRisk}
          disabled={loading || !entryPrice}
          className="flex-1 flex items-center justify-center space-x-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 text-white py-3 px-4 rounded-lg transition-colors"
        >
          <Calculator className="w-5 h-5" />
          <span>Рассчитать</span>
        </button>
        
        <button
          onClick={handleCreateTrade}
          disabled={loading || !symbolInput || !entryPrice || !quantity || !apiConnected}
          className="flex-1 flex items-center justify-center space-x-2 bg-green-600 hover:bg-green-700 disabled:bg-green-300 text-white py-3 px-4 rounded-lg transition-colors"
        >
          <DollarSign className="w-5 h-5" />
          <span>Открыть сделку</span>
        </button>
      </div>

      {/* Сообщения об ошибках и успехе */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg flex items-start">
          <AlertTriangle className="w-5 h-5 mr-2 mt-0.5 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}
      
      {success && (
        <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded-lg">
          {success}
        </div>
      )}
    </div>
  );

  const renderTradesTab = () => (
    <div className="space-y-6">
      <div className="bg-green-50 p-4 rounded-lg">
        <h3 className="font-medium text-green-900 mb-2 flex items-center">
          <BarChart3 className="w-5 h-5 mr-2" />
          Реальные сделки
        </h3>
        <p className="text-sm text-green-700">
          Отслеживайте свои реальные сделки и анализируйте результаты торговли
        </p>
      </div>

      {/* Статистика */}
      {statistics && (
        <div className="bg-white rounded-lg shadow border border-gray-200 p-4">
          <h3 className="font-medium text-gray-900 mb-3">Статистика торговли</h3>
          
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div>
              <span className="text-gray-600">Всего сделок:</span>
              <div className="font-medium text-gray-900">{statistics.total_trades}</div>
            </div>
            
            <div>
              <span className="text-gray-600">Открытых:</span>
              <div className="font-medium text-blue-600">{statistics.open_trades}</div>
            </div>
            
            <div>
              <span className="text-gray-600">Закрытых:</span>
              <div className="font-medium text-gray-900">{statistics.closed_trades}</div>
            </div>
            
            <div>
              <span className="text-gray-600">Винрейт:</span>
              <div className="font-medium text-green-600">{formatPercentage(statistics.win_rate)}</div>
            </div>
            
            <div>
              <span className="text-gray-600">Общий P&L:</span>
              <div className={`font-medium ${statistics.total_pnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                {formatCurrency(statistics.total_pnl)}
              </div>
            </div>
            
            <div>
              <span className="text-gray-600">Средний P&L:</span>
              <div className={`font-medium ${statistics.avg_pnl_percentage >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                {formatPercentage(statistics.avg_pnl_percentage)}
              </div>
            </div>
            
            <div>
              <span className="text-gray-600">Макс. прибыль:</span>
              <div className="font-medium text-green-600">{formatCurrency(statistics.max_profit)}</div>
            </div>
            
            <div>
              <span className="text-gray-600">Макс. убыток:</span>
              <div className="font-medium text-red-600">{formatCurrency(statistics.max_loss)}</div>
            </div>
          </div>
        </div>
      )}

      {/* Список сделок */}
      <div>
        <h3 className="font-medium text-gray-900 mb-3">Ваши сделки</h3>
        
        {trades.length === 0 ? (
          <div className="text-center py-8 bg-gray-50 rounded-lg">
            <DollarSign className="w-12 h-12 mx-auto mb-3 text-gray-300" />
            <p className="text-gray-500">У вас пока нет сделок</p>
            <button
              onClick={() => setActiveTab('calculator')}
              className="mt-3 text-blue-600 hover:text-blue-800"
            >
              Открыть новую сделку
            </button>
          </div>
        ) : (
          <div className="space-y-4">
            {trades.map(trade => (
              <div key={trade.id} className="bg-white rounded-lg shadow border border-gray-200 p-4">
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center space-x-3">
                    <div className={`w-3 h-3 rounded-full ${
                      trade.trade_type === 'LONG' ? 'bg-green-500' : 'bg-red-500'
                    }`}></div>
                    <span className="font-bold text-lg text-gray-900">{trade.symbol}</span>
                    {getTradeStatusBadge(trade.status)}
                    {trade.status === 'CLOSED' && getPnLBadge(trade.pnl, trade.pnl_percentage)}
                  </div>
                  
                  <div className="flex items-center space-x-2">
                    {trade.status === 'OPEN' && (
                      <button
                        onClick={() => setSelectedTradeId(trade.id)}
                        className="text-blue-600 hover:text-blue-800 px-3 py-1 rounded border border-blue-600 hover:border-blue-800 text-sm"
                      >
                        Закрыть
                      </button>
                    )}
                  </div>
                </div>
                
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                  <div>
                    <span className="text-gray-600">Тип:</span>
                    <div className={`font-medium ${
                      trade.trade_type === 'LONG' ? 'text-green-600' : 'text-red-600'
                    }`}>
                      {trade.trade_type}
                    </div>
                  </div>
                  
                  <div>
                    <span className="text-gray-600">Цена входа:</span>
                    <div className="font-mono text-gray-900">${formatCrypto(trade.entry_price)}</div>
                  </div>
                  
                  <div>
                    <span className="text-gray-600">Количество:</span>
                    <div className="font-mono text-gray-900">{formatCrypto(trade.quantity)}</div>
                  </div>
                  
                  <div>
                    <span className="text-gray-600">Размер позиции:</span>
                    <div className="font-medium text-gray-900">{formatCurrency(trade.entry_price * trade.quantity)}</div>
                  </div>
                  
                  <div>
                    <span className="text-gray-600">Плечо:</span>
                    <div className="font-medium text-orange-600">{trade.leverage}x</div>
                  </div>
                  
                  <div>
                    <span className="text-gray-600">Тип маржи:</span>
                    <div className="font-medium text-gray-900">{trade.margin_type === 'isolated' ? 'Изолированная' : 'Кросс'}</div>
                  </div>
                  
                  {trade.stop_loss && (
                    <div>
                      <span className="text-gray-600">Стоп-лосс:</span>
                      <div className="font-mono text-red-600">${formatCrypto(trade.stop_loss)}</div>
                    </div>
                  )}
                  
                  {trade.take_profit && (
                    <div>
                      <span className="text-gray-600">Тейк-профит:</span>
                      <div className="font-mono text-green-600">${formatCrypto(trade.take_profit)}</div>
                    </div>
                  )}
                  
                  <div>
                    <span className="text-gray-600">Риск:</span>
                    <div className="font-medium text-red-600">{formatCurrency(trade.risk_amount)} ({formatPercentage(trade.risk_percentage)})</div>
                  </div>
                  
                  {trade.risk_reward_ratio && (
                    <div>
                      <span className="text-gray-600">R/R:</span>
                      <div className="font-medium text-blue-600">1:{trade.risk_reward_ratio.toFixed(2)}</div>
                    </div>
                  )}
                  
                  {trade.exit_price && (
                    <div>
                      <span className="text-gray-600">Цена выхода:</span>
                      <div className="font-mono text-gray-900">${formatCrypto(trade.exit_price)}</div>
                    </div>
                  )}
                  
                  {trade.exit_reason && (
                    <div>
                      <span className="text-gray-600">Причина выхода:</span>
                      <div className="font-medium text-gray-900">{trade.exit_reason}</div>
                    </div>
                  )}
                  
                  {trade.order_id && (
                    <div>
                      <span className="text-gray-600">ID ордера:</span>
                      <div className="font-mono text-xs text-gray-900 truncate">{trade.order_id}</div>
                    </div>
                  )}
                </div>
                
                {trade.notes && (
                  <div className="mt-3 pt-3 border-t border-gray-200">
                    <span className="text-gray-600 text-sm">Заметки:</span>
                    <div className="text-sm text-gray-900 mt-1">{trade.notes}</div>
                  </div>
                )}
                
                <div className="mt-3 pt-3 border-t border-gray-200 text-xs text-gray-500 flex justify-between">
                  <div>Открыта: {formatTime(trade.opened_at_ms, timeZone)}</div>
                  {trade.closed_at_ms && (
                    <div>Закрыта: {formatTime(trade.closed_at_ms, timeZone)}</div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Модальное окно закрытия сделки */}
      {selectedTradeId !== null && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-md">
            <h3 className="text-lg font-medium text-gray-900 mb-4">Закрытие сделки</h3>
            
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Цена выхода *
                </label>
                <input
                  type="number"
                  step="0.00000001"
                  value={exitPrice || ''}
                  onChange={(e) => setExitPrice(parseFloat(e.target.value))}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  placeholder="Цена выхода"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Причина выхода
                </label>
                <select
                  value={exitReason}
                  onChange={(e) => setExitReason(e.target.value)}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                >
                  <option value="MANUAL">Ручное закрытие</option>
                  <option value="STOP_LOSS">Стоп-лосс</option>
                  <option value="TAKE_PROFIT">Тейк-профит</option>
                  <option value="TRAILING_STOP">Трейлинг-стоп</option>
                  <option value="SIGNAL">Сигнал</option>
                </select>
              </div>
              
              <div className="flex space-x-3 pt-3">
                <button
                  onClick={() => {
                    setSelectedTradeId(null);
                    setConfirmTradeClose(false);
                  }}
                  className="flex-1 py-2 px-4 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition-colors"
                >
                  Отмена
                </button>
                <button
                  onClick={() => handleCloseTrade(selectedTradeId)}
                  disabled={loading || !exitPrice}
                  className="flex-1 py-2 px-4 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 text-white rounded-lg transition-colors"
                >
                  {confirmTradeClose ? 'Подтвердить закрытие' : 'Закрыть сделку'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Модальное окно подтверждения открытия сделки */}
      {confirmTradeOpen && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-md">
            <h3 className="text-lg font-medium text-gray-900 mb-4">Подтверждение сделки</h3>
            
            <div className="bg-yellow-50 p-4 rounded-lg mb-4">
              <div className="flex items-start space-x-3">
                <AlertTriangle className="w-5 h-5 text-yellow-600 mt-0.5" />
                <div>
                  <h5 className="font-medium text-yellow-900">Внимание! Реальная торговля</h5>
                  <p className="text-sm text-yellow-700 mt-1">
                    Вы собираетесь открыть реальную сделку с использованием средств вашего аккаунта.
                    Пожалуйста, проверьте все параметры сделки перед подтверждением.
                  </p>
                </div>
              </div>
            </div>
            
            <div className="space-y-3 mb-4">
              <div className="flex justify-between">
                <span className="text-gray-600">Символ:</span>
                <span className="font-medium text-gray-900">{symbolInput}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Тип:</span>
                <span className={`font-medium ${tradeType === 'LONG' ? 'text-green-600' : 'text-red-600'}`}>
                  {tradeType}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Цена входа:</span>
                <span className="font-medium text-gray-900">${formatCrypto(entryPrice)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Количество:</span>
                <span className="font-medium text-gray-900">{formatCrypto(quantity || 0)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Размер позиции:</span>
                <span className="font-medium text-gray-900">{formatCurrency((quantity || 0) * entryPrice)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Плечо:</span>
                <span className="font-medium text-orange-600">{leverage}x</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Риск:</span>
                <span className="font-medium text-red-600">{formatCurrency(riskAmount)} ({formatPercentage(riskPercentage)})</span>
              </div>
              {stopLoss && (
                <div className="flex justify-between">
                  <span className="text-gray-600">Стоп-лосс:</span>
                  <span className="font-medium text-red-600">${formatCrypto(stopLoss)}</span>
                </div>
              )}
              {takeProfit && (
                <div className="flex justify-between">
                  <span className="text-gray-600">Тейк-профит:</span>
                  <span className="font-medium text-green-600">${formatCrypto(takeProfit)}</span>
                </div>
              )}
            </div>
            
            <div className="flex space-x-3 pt-3">
              <button
                onClick={() => setConfirmTradeOpen(false)}
                className="flex-1 py-2 px-4 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition-colors"
              >
                Отмена
              </button>
              <button
                onClick={handleCreateTrade}
                disabled={loading}
                className="flex-1 py-2 px-4 bg-green-600 hover:bg-green-700 disabled:bg-green-300 text-white rounded-lg transition-colors"
              >
                Подтвердить открытие
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );

  const renderPositionsTab = () => (
    <div className="space-y-6">
      <div className="bg-blue-50 p-4 rounded-lg">
        <h3 className="font-medium text-blue-900 mb-2 flex items-center">
          <Target className="w-5 h-5 mr-2" />
          Открытые позиции
        </h3>
        <p className="text-sm text-blue-700">
          Просмотр и управление вашими текущими открытыми позициями на бирже
        </p>
      </div>

      {/* Обновление данных */}
      <div className="flex justify-end">
        <button
          onClick={checkApiConnection}
          disabled={apiCheckLoading}
          className="flex items-center space-x-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 text-white px-4 py-2 rounded-lg transition-colors"
        >
          {apiCheckLoading ? (
            <RefreshCw className="w-4 h-4 animate-spin" />
          ) : (
            <RefreshCw className="w-4 h-4" />
          )}
          <span>Обновить данные</span>
        </button>
      </div>

      {/* Информация об аккаунте */}
      {accountInfo && (
        <div className="bg-white rounded-lg shadow border border-gray-200 p-4">
          <h3 className="font-medium text-gray-900 mb-3">Информация об аккаунте</h3>
          
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div>
              <span className="text-gray-600">Баланс:</span>
              <div className="font-medium text-gray-900">{formatCurrency(accountInfo.balance)}</div>
            </div>
            
            <div>
              <span className="text-gray-600">Доступно:</span>
              <div className="font-medium text-gray-900">{formatCurrency(accountInfo.available_balance)}</div>
            </div>
            
            <div>
              <span className="text-gray-600">Используемая маржа:</span>
              <div className="font-medium text-gray-900">{formatCurrency(accountInfo.used_margin)}</div>
            </div>
            
            <div>
              <span className="text-gray-600">Нереализованный P&L:</span>
              <div className={`font-medium ${accountInfo.unrealized_pnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                {formatCurrency(accountInfo.unrealized_pnl)}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Список открытых позиций */}
      <div>
        <h3 className="font-medium text-gray-900 mb-3">Открытые позиции</h3>
        
        {!apiConnected ? (
          <div className="text-center py-8 bg-gray-50 rounded-lg">
            <AlertTriangle className="w-12 h-12 mx-auto mb-3 text-yellow-500" />
            <p className="text-gray-500">API не подключено</p>
            <p className="text-sm text-gray-400 mt-1">Настройте API ключи в настройках системы</p>
          </div>
        ) : trades.filter(t => t.status === 'OPEN').length === 0 ? (
          <div className="text-center py-8 bg-gray-50 rounded-lg">
            <Target className="w-12 h-12 mx-auto mb-3 text-gray-300" />
            <p className="text-gray-500">У вас нет открытых позиций</p>
            <button
              onClick={() => setActiveTab('calculator')}
              className="mt-3 text-blue-600 hover:text-blue-800"
            >
              Открыть новую сделку
            </button>
          </div>
        ) : (
          <div className="space-y-4">
            {trades
              .filter(t => t.status === 'OPEN')
              .map(trade => (
                <div key={trade.id} className="bg-white rounded-lg shadow border border-gray-200 p-4">
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex items-center space-x-3">
                      <div className={`w-3 h-3 rounded-full ${
                        trade.trade_type === 'LONG' ? 'bg-green-500' : 'bg-red-500'
                      }`}></div>
                      <span className="font-bold text-lg text-gray-900">{trade.symbol}</span>
                      {getTradeStatusBadge(trade.status)}
                    </div>
                    
                    <div className="flex items-center space-x-2">
                      <button
                        onClick={() => setSelectedTradeId(trade.id)}
                        className="text-blue-600 hover:text-blue-800 px-3 py-1 rounded border border-blue-600 hover:border-blue-800 text-sm"
                      >
                        Закрыть
                      </button>
                    </div>
                  </div>
                  
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                    <div>
                      <span className="text-gray-600">Тип:</span>
                      <div className={`font-medium ${
                        trade.trade_type === 'LONG' ? 'text-green-600' : 'text-red-600'
                      }`}>
                        {trade.trade_type}
                      </div>
                    </div>
                    
                    <div>
                      <span className="text-gray-600">Цена входа:</span>
                      <div className="font-mono text-gray-900">${formatCrypto(trade.entry_price)}</div>
                    </div>
                    
                    <div>
                      <span className="text-gray-600">Количество:</span>
                      <div className="font-mono text-gray-900">{formatCrypto(trade.quantity)}</div>
                    </div>
                    
                    <div>
                      <span className="text-gray-600">Размер позиции:</span>
                      <div className="font-medium text-gray-900">{formatCurrency(trade.entry_price * trade.quantity)}</div>
                    </div>
                    
                    <div>
                      <span className="text-gray-600">Плечо:</span>
                      <div className="font-medium text-orange-600">{trade.leverage}x</div>
                    </div>
                    
                    <div>
                      <span className="text-gray-600">Тип маржи:</span>
                      <div className="font-medium text-gray-900">{trade.margin_type === 'isolated' ? 'Изолированная' : 'Кросс'}</div>
                    </div>
                    
                    {trade.stop_loss && (
                      <div>
                        <span className="text-gray-600">Стоп-лосс:</span>
                        <div className="font-mono text-red-600">${formatCrypto(trade.stop_loss)}</div>
                      </div>
                    )}
                    
                    {trade.take_profit && (
                      <div>
                        <span className="text-gray-600">Тейк-профит:</span>
                        <div className="font-mono text-green-600">${formatCrypto(trade.take_profit)}</div>
                      </div>
                    )}
                  </div>
                  
                  {trade.notes && (
                    <div className="mt-3 pt-3 border-t border-gray-200">
                      <span className="text-gray-600 text-sm">Заметки:</span>
                      <div className="text-sm text-gray-900 mt-1">{trade.notes}</div>
                    </div>
                  )}
                  
                  <div className="mt-3 pt-3 border-t border-gray-200 text-xs text-gray-500">
                    <div>Открыта: {formatTime(trade.opened_at_ms, timeZone)}</div>
                  </div>
                </div>
              ))}
          </div>
        )}
      </div>
    </div>
  );

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-lg w-full max-w-4xl max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200">
          <div>
            <h2 className="text-2xl font-bold text-gray-900">Реальная торговля</h2>
            <p className="text-gray-600">
              {symbol ? `Торговля ${symbol}` : 'Калькулятор риска и реальные сделки'}
            </p>
            {apiConnected ? (
              <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                API подключено
              </span>
            ) : (
              <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800">
                API не подключено
              </span>
            )}
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 p-2"
          >
            <X className="w-6 h-6" />
          </button>
        </div>

        {/* Tabs */}
        <div className="border-b border-gray-200">
          <nav className="flex space-x-8 px-6">
            {[
              { id: 'calculator', label: 'Калькулятор', icon: Calculator },
              { id: 'trades', label: 'Сделки', icon: BarChart3 },
              { id: 'positions', label: 'Позиции', icon: Target }
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={`flex items-center space-x-2 py-4 px-1 border-b-2 font-medium text-sm transition-colors ${
                  activeTab === tab.id
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                <tab.icon className="w-4 h-4" />
                <span>{tab.label}</span>
              </button>
            ))}
          </nav>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {activeTab === 'calculator' && renderCalculatorTab()}
          {activeTab === 'trades' && renderTradesTab()}
          {activeTab === 'positions' && renderPositionsTab()}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-gray-200 bg-gray-50">
          <div className="flex justify-between items-center text-sm text-gray-600">
            <div className="flex items-center space-x-2">
              <Shield className="w-4 h-4 text-gray-500" />
              <span>Реальная торговля - будьте осторожны с рисками</span>
            </div>
            {accountInfo && (
              <div>
                Баланс: <span className="font-medium">{formatCurrency(accountInfo.balance)}</span>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default RealTradingModal;