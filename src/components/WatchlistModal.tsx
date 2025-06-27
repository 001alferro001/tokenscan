import React, { useState } from 'react';
import { X, Plus, Trash2, Edit, Save, Cancel } from 'lucide-react';

interface WatchlistItem {
  id: number;
  symbol: string;
  is_active: boolean;
  price_drop_percentage?: number;
  current_price?: number;
  historical_price?: number;
  created_at: string;
  updated_at: string;
}

interface WatchlistModalProps {
  watchlist: WatchlistItem[];
  onClose: () => void;
  onUpdate: () => void;
}

const WatchlistModal: React.FC<WatchlistModalProps> = ({ watchlist, onClose, onUpdate }) => {
  const [newSymbol, setNewSymbol] = useState('');
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editingSymbol, setEditingSymbol] = useState('');
  const [loading, setLoading] = useState(false);

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

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
      <div className="bg-gray-800 rounded-lg w-full max-w-4xl max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-700">
          <h2 className="text-2xl font-bold text-white">Управление торговыми парами</h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white p-2"
          >
            <X className="w-6 h-6" />
          </button>
        </div>

        {/* Add new symbol */}
        <div className="p-6 border-b border-gray-700">
          <div className="flex space-x-3">
            <input
              type="text"
              value={newSymbol}
              onChange={(e) => setNewSymbol(e.target.value.toUpperCase())}
              placeholder="Введите символ (например, BTCUSDT)"
              className="flex-1 bg-gray-700 border border-gray-600 rounded-lg px-4 py-2 text-white placeholder-gray-400"
              onKeyPress={(e) => e.key === 'Enter' && addSymbol()}
            />
            <button
              onClick={addSymbol}
              disabled={loading || !newSymbol.trim()}
              className="flex items-center space-x-2 bg-green-600 hover:bg-green-700 disabled:bg-gray-600 px-4 py-2 rounded-lg transition-colors"
            >
              <Plus className="w-4 h-4" />
              <span>Добавить</span>
            </button>
          </div>
        </div>

        {/* Watchlist */}
        <div className="flex-1 overflow-y-auto p-6">
          {watchlist.length === 0 ? (
            <div className="text-center py-12 text-gray-400">
              <p>Нет торговых пар в списке</p>
            </div>
          ) : (
            <div className="space-y-3">
              {watchlist.map((item) => (
                <div key={item.id} className="bg-gray-700 rounded-lg p-4 flex items-center justify-between">
                  <div className="flex items-center space-x-4">
                    <button
                      onClick={() => toggleActive(item)}
                      disabled={loading}
                      className={`w-4 h-4 rounded-full ${
                        item.is_active ? 'bg-green-400' : 'bg-red-400'
                      } transition-colors`}
                    />
                    
                    {editingId === item.id ? (
                      <input
                        type="text"
                        value={editingSymbol}
                        onChange={(e) => setEditingSymbol(e.target.value.toUpperCase())}
                        className="bg-gray-600 border border-gray-500 rounded px-3 py-1 text-white"
                        onKeyPress={(e) => e.key === 'Enter' && saveEdit()}
                      />
                    ) : (
                      <div>
                        <span className="font-semibold text-white">{item.symbol}</span>
                        <span className="ml-2 text-sm text-gray-400">
                          {item.is_active ? 'Активна' : 'Неактивна'}
                        </span>
                      </div>
                    )}
                  </div>

                  <div className="flex items-center space-x-4">
                    {item.price_drop_percentage && (
                      <div className="text-right text-sm">
                        <div className="text-red-400">
                          Падение: {item.price_drop_percentage.toFixed(2)}%
                        </div>
                        {item.current_price && (
                          <div className="text-gray-400">
                            ${item.current_price.toFixed(8)}
                          </div>
                        )}
                      </div>
                    )}

                    <div className="flex items-center space-x-2">
                      {editingId === item.id ? (
                        <>
                          <button
                            onClick={saveEdit}
                            disabled={loading}
                            className="text-green-400 hover:text-green-300 p-1"
                          >
                            <Save className="w-4 h-4" />
                          </button>
                          <button
                            onClick={cancelEdit}
                            disabled={loading}
                            className="text-gray-400 hover:text-gray-300 p-1"
                          >
                            <Cancel className="w-4 h-4" />
                          </button>
                        </>
                      ) : (
                        <>
                          <button
                            onClick={() => startEdit(item)}
                            disabled={loading}
                            className="text-blue-400 hover:text-blue-300 p-1"
                          >
                            <Edit className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => deleteItem(item.id)}
                            disabled={loading}
                            className="text-red-400 hover:text-red-300 p-1"
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
        <div className="p-6 border-t border-gray-700">
          <div className="flex justify-between items-center text-sm text-gray-400">
            <span>Всего пар: {watchlist.length}</span>
            <span>Активных: {watchlist.filter(w => w.is_active).length}</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default WatchlistModal;