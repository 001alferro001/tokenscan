import React, { useState } from 'react';
import { X, Plus, Trash2, Edit, Save, Ambulance as Cancel, Heart, HeartOff, Search } from 'lucide-react';

interface WatchlistItem {
  id: number;
  symbol: string;
  is_active: boolean;
  is_favorite: boolean;
  price_drop_percentage?: number;
  current_price?: number;
  historical_price?: number;
  created_at: string;
  updated_at: string;
  notes?: string;
  color?: string;
}

interface WatchlistModalProps {
  watchlist: WatchlistItem[];
  onClose: () => void;
  onUpdate: () => void;
  onToggleFavorite: (symbol: string, isFavorite: boolean) => void;
}

const WatchlistModal: React.FC<WatchlistModalProps> = ({ 
  watchlist, 
  onClose, 
  onUpdate, 
  onToggleFavorite 
}) => {
  const [newSymbol, setNewSymbol] = useState('');
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editingSymbol, setEditingSymbol] = useState('');
  const [loading, setLoading] = useState(false);
  const [filter, setFilter] = useState<'all' | 'active' | 'inactive' | 'favorites'>('all');
  const [searchQuery, setSearchQuery] = useState('');

  const addSymbol = async () => {
    if (!newSymbol.trim()) return;

    setLoading(true);
    try {
      const response = await fetch('/api/watchlist', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ symbol: newSymbol.toUpperCase() }),
      });

      if (response.ok) {
        setNewSymbol('');
        onUpdate();
      } else {
        const error = await response.json();
        alert(`Ошибка: ${error.detail || 'Не удалось добавить пару'}`);
      }
    } catch (error) {
      console.error('Ошибка добавления пары:', error);
      alert('Ошибка добавления пары');
    } finally {
      setLoading(false);
    }
  };

  const deleteItem = async (id: number) => {
    if (!confirm('Удалить эту торговую пару?')) return;

    setLoading(true);
    try {
      const response = await fetch(`/api/watchlist/${id}`, {
        method: 'DELETE',
      });

      if (response.ok) {
        onUpdate();
      } else {
        alert('Ошибка удаления пары');
      }
    } catch (error) {
      console.error('Ошибка удаления пары:', error);
      alert('Ошибка удаления пары');
    } finally {
      setLoading(false);
    }
  };

  const startEdit = (item: WatchlistItem) => {
    setEditingId(item.id);
    setEditingSymbol(item.symbol);
  };

  const saveEdit = async () => {
    if (!editingSymbol.trim() || editingId === null) return;

    setLoading(true);
    try {
      const item = watchlist.find(w => w.id === editingId);
      if (!item) return;

      const response = await fetch(`/api/watchlist/${editingId}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          id: editingId,
          symbol: editingSymbol.toUpperCase(),
          is_active: item.is_active,
        }),
      });

      if (response.ok) {
        setEditingId(null);
        setEditingSymbol('');
        onUpdate();
      } else {
        alert('Ошибка обновления пары');
      }
    } catch (error) {
      console.error('Ошибка обновления пары:', error);
      alert('Ошибка обновления пары');
    } finally {
      setLoading(false);
    }
  };

  const cancelEdit = () => {
    setEditingId(null);
    setEditingSymbol('');
  };

  const toggleActive = async (item: WatchlistItem) => {
    setLoading(true);
    try {
      const response = await fetch(`/api/watchlist/${item.id}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          id: item.id,
          symbol: item.symbol,
          is_active: !item.is_active,
        }),
      });

      if (response.ok) {
        onUpdate();
      } else {
        alert('Ошибка обновления статуса пары');
      }
    } catch (error) {
      console.error('Ошибка обновления статуса пары:', error);
      alert('Ошибка обновления статуса пары');
    } finally {
      setLoading(false);
    }
  };

  const toggleFavorite = async (item: WatchlistItem) => {
    try {
      await onToggleFavorite(item.symbol, item.is_favorite);
    } catch (error) {
      console.error('Ошибка переключения избранного:', error);
      alert('Ошибка переключения избранного');
    }
  };

  // Фильтрация и поиск
  const filteredWatchlist = watchlist.filter(item => {
    // Фильтр по статусу
    let statusMatch = true;
    if (filter === 'active') statusMatch = item.is_active;
    if (filter === 'inactive') statusMatch = !item.is_active;
    if (filter === 'favorites') statusMatch = item.is_favorite;

    // Поиск по символу
    const searchMatch = searchQuery === '' || 
      item.symbol.toLowerCase().includes(searchQuery.toLowerCase());

    return statusMatch && searchMatch;
  });

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-lg w-full max-w-4xl max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200">
          <h2 className="text-2xl font-bold text-gray-900">Управление торговыми парами</h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 p-2"
          >
            <X className="w-6 h-6" />
          </button>
        </div>

        {/* Add new symbol */}
        <div className="p-6 border-b border-gray-200">
          <div className="flex space-x-3">
            <input
              type="text"
              value={newSymbol}
              onChange={(e) => setNewSymbol(e.target.value.toUpperCase())}
              placeholder="Введите символ (например, BTCUSDT)"
              className="flex-1 border border-gray-300 rounded-lg px-4 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              onKeyPress={(e) => e.key === 'Enter' && addSymbol()}
            />
            <button
              onClick={addSymbol}
              disabled={loading || !newSymbol.trim()}
              className="flex items-center space-x-2 bg-green-600 hover:bg-green-700 disabled:bg-gray-400 text-white px-4 py-2 rounded-lg transition-colors"
            >
              <Plus className="w-4 h-4" />
              <span>Добавить</span>
            </button>
          </div>
        </div>

        {/* Search and Filters */}
        <div className="p-4 border-b border-gray-200 bg-gray-50">
          {/* Search */}
          <div className="mb-4">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Поиск по символу..."
                className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
            </div>
          </div>

          {/* Filters */}
          <div className="flex space-x-2">
            <button
              onClick={() => setFilter('all')}
              className={`px-3 py-1 rounded-lg text-sm ${
                filter === 'all' 
                  ? 'bg-blue-600 text-white' 
                  : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
              }`}
            >
              Все ({watchlist.length})
            </button>
            <button
              onClick={() => setFilter('active')}
              className={`px-3 py-1 rounded-lg text-sm ${
                filter === 'active' 
                  ? 'bg-green-600 text-white' 
                  : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
              }`}
            >
              Активные ({watchlist.filter(w => w.is_active).length})
            </button>
            <button
              onClick={() => setFilter('inactive')}
              className={`px-3 py-1 rounded-lg text-sm ${
                filter === 'inactive' 
                  ? 'bg-red-600 text-white' 
                  : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
              }`}
            >
              Неактивные ({watchlist.filter(w => !w.is_active).length})
            </button>
            <button
              onClick={() => setFilter('favorites')}
              className={`px-3 py-1 rounded-lg text-sm ${
                filter === 'favorites' 
                  ? 'bg-yellow-600 text-white' 
                  : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
              }`}
            >
              Избранные ({watchlist.filter(w => w.is_favorite).length})
            </button>
          </div>
        </div>

        {/* Watchlist */}
        <div className="flex-1 overflow-y-auto p-6">
          {filteredWatchlist.length === 0 ? (
            <div className="text-center py-12 text-gray-500">
              {searchQuery ? (
                <div>
                  <Search className="w-12 h-12 mx-auto mb-4 text-gray-300" />
                  <p>Нет результатов по запросу "{searchQuery}"</p>
                  <button
                    onClick={() => setSearchQuery('')}
                    className="mt-2 text-blue-600 hover:text-blue-800"
                  >
                    Очистить поиск
                  </button>
                </div>
              ) : (
                <p>Нет торговых пар в списке</p>
              )}
            </div>
          ) : (
            <div className="space-y-3">
              {filteredWatchlist.map((item) => (
                <div key={item.id} className="bg-gray-50 rounded-lg p-4 flex items-center justify-between hover:bg-gray-100 transition-colors">
                  <div className="flex items-center space-x-4">
                    <button
                      onClick={() => toggleActive(item)}
                      disabled={loading}
                      className={`w-4 h-4 rounded-full ${
                        item.is_active ? 'bg-green-500' : 'bg-red-500'
                      } transition-colors`}
                      title={item.is_active ? 'Деактивировать' : 'Активировать'}
                    />
                    
                    {editingId === item.id ? (
                      <input
                        type="text"
                        value={editingSymbol}
                        onChange={(e) => setEditingSymbol(e.target.value.toUpperCase())}
                        className="bg-white border border-gray-300 rounded px-3 py-1 text-gray-900 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                        onKeyPress={(e) => e.key === 'Enter' && saveEdit()}
                      />
                    ) : (
                      <div className="flex items-center space-x-2">
                        <span className="font-semibold text-gray-900">{item.symbol}</span>
                        <span className="text-sm text-gray-500">
                          {item.is_active ? 'Активна' : 'Неактивна'}
                        </span>
                        {item.is_favorite && (
                          <Heart className="w-4 h-4 text-yellow-500 fill-yellow-500" />
                        )}
                      </div>
                    )}
                  </div>

                  <div className="flex items-center space-x-4">
                    {item.price_drop_percentage && (
                      <div className="text-right text-sm">
                        <div className="text-red-600">
                          Падение: {item.price_drop_percentage.toFixed(2)}%
                        </div>
                        {item.current_price && (
                          <div className="text-gray-500">
                            ${item.current_price.toFixed(8)}
                          </div>
                        )}
                      </div>
                    )}

                    <div className="flex items-center space-x-2">
                      {/* Кнопка избранного */}
                      <button
                        onClick={() => toggleFavorite(item)}
                        disabled={loading}
                        className={`p-1 ${
                          item.is_favorite 
                            ? 'text-yellow-500 hover:text-yellow-600' 
                            : 'text-gray-400 hover:text-yellow-500'
                        }`}
                        title={item.is_favorite ? "Удалить из избранного" : "Добавить в избранное"}
                      >
                        {item.is_favorite ? (
                          <Heart className="w-4 h-4 fill-current" />
                        ) : (
                          <Heart className="w-4 h-4" />
                        )}
                      </button>

                      {editingId === item.id ? (
                        <>
                          <button
                            onClick={saveEdit}
                            disabled={loading}
                            className="text-green-600 hover:text-green-700 p-1"
                            title="Сохранить"
                          >
                            <Save className="w-4 h-4" />
                          </button>
                          <button
                            onClick={cancelEdit}
                            disabled={loading}
                            className="text-gray-500 hover:text-gray-600 p-1"
                            title="Отменить"
                          >
                            <Cancel className="w-4 h-4" />
                          </button>
                        </>
                      ) : (
                        <>
                          <button
                            onClick={() => startEdit(item)}
                            disabled={loading}
                            className="text-blue-600 hover:text-blue-700 p-1"
                            title="Редактировать"
                          >
                            <Edit className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => deleteItem(item.id)}
                            disabled={loading}
                            className="text-red-600 hover:text-red-700 p-1"
                            title="Удалить"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-6 border-t border-gray-200 bg-gray-50">
          <div className="flex justify-between items-center text-sm text-gray-600">
            <span>
              Показано: {filteredWatchlist.length} из {watchlist.length} пар
              {searchQuery && ` (поиск: "${searchQuery}")`}
            </span>
            <div className="flex space-x-4">
              <span>Активных: {watchlist.filter(w => w.is_active).length}</span>
              <span>Избранных: {watchlist.filter(w => w.is_favorite).length}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default WatchlistModal;