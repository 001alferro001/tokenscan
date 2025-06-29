import React, { useState } from 'react';
import { X, Save, Trash2, Edit, Heart, HeartOff, GripVertical, ExternalLink } from 'lucide-react';
import { formatTime } from '../utils/timeUtils';

interface FavoriteItem {
  id: number;
  symbol: string;
  is_active: boolean;
  price_drop_percentage?: number;
  current_price?: number;
  historical_price?: number;
  notes?: string;
  color?: string;
  sort_order?: number;
  favorite_added_at?: string;
}

interface FavoritesModalProps {
  favorites: FavoriteItem[];
  onClose: () => void;
  onUpdate: () => void;
}

const FavoritesModal: React.FC<FavoritesModalProps> = ({ favorites, onClose, onUpdate }) => {
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editingNotes, setEditingNotes] = useState('');
  const [editingColor, setEditingColor] = useState('#FFD700');
  const [loading, setLoading] = useState(false);
  const [draggedItem, setDraggedItem] = useState<FavoriteItem | null>(null);
  const [localFavorites, setLocalFavorites] = useState<FavoriteItem[]>(favorites);

  // Цвета для выбора
  const colorOptions = [
    { name: 'Золотой', value: '#FFD700' },
    { name: 'Красный', value: '#EF4444' },
    { name: 'Зеленый', value: '#10B981' },
    { name: 'Синий', value: '#3B82F6' },
    { name: 'Фиолетовый', value: '#8B5CF6' },
    { name: 'Розовый', value: '#EC4899' },
    { name: 'Оранжевый', value: '#F97316' },
    { name: 'Голубой', value: '#06B6D4' }
  ];

  // Обновляем локальный список при изменении props
  React.useEffect(() => {
    setLocalFavorites(favorites);
  }, [favorites]);

  const startEdit = (item: FavoriteItem) => {
    setEditingId(item.id);
    setEditingNotes(item.notes || '');
    setEditingColor(item.color || '#FFD700');
  };

  const saveEdit = async () => {
    if (editingId === null) return;

    setLoading(true);
    try {
      const item = localFavorites.find(f => f.id === editingId);
      if (!item) return;

      const response = await fetch(`/api/favorites/${item.symbol}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          notes: editingNotes,
          color: editingColor
        }),
      });

      if (response.ok) {
        // Обновляем локальный список
        setLocalFavorites(prev => 
          prev.map(f => f.id === editingId ? { ...f, notes: editingNotes, color: editingColor } : f)
        );
        setEditingId(null);
        onUpdate();
      } else {
        alert('Ошибка обновления избранного');
      }
    } catch (error) {
      console.error('Ошибка обновления избранного:', error);
      alert('Ошибка обновления избранного');
    } finally {
      setLoading(false);
    }
  };

  const cancelEdit = () => {
    setEditingId(null);
  };

  const removeFromFavorites = async (symbol: string) => {
    if (!confirm(`Удалить ${symbol} из избранного?`)) return;

    setLoading(true);
    try {
      const response = await fetch(`/api/favorites/${symbol}`, {
        method: 'DELETE'
      });

      if (response.ok) {
        // Обновляем локальный список
        setLocalFavorites(prev => prev.filter(f => f.symbol !== symbol));
        onUpdate();
      } else {
        alert('Ошибка удаления из избранного');
      }
    } catch (error) {
      console.error('Ошибка удаления из избранного:', error);
      alert('Ошибка удаления из избранного');
    } finally {
      setLoading(false);
    }
  };

  const handleDragStart = (e: React.DragEvent, item: FavoriteItem) => {
    setDraggedItem(item);
    e.dataTransfer.effectAllowed = 'move';
    // Для Firefox
    e.dataTransfer.setData('text/plain', item.symbol);
  };

  const handleDragOver = (e: React.DragEvent, item: FavoriteItem) => {
    e.preventDefault();
    if (!draggedItem || draggedItem.id === item.id) return;
    
    // Перемещаем элемент в списке
    const newFavorites = [...localFavorites];
    const draggedIndex = newFavorites.findIndex(f => f.id === draggedItem.id);
    const targetIndex = newFavorites.findIndex(f => f.id === item.id);
    
    if (draggedIndex !== -1 && targetIndex !== -1) {
      newFavorites.splice(draggedIndex, 1);
      newFavorites.splice(targetIndex, 0, draggedItem);
      setLocalFavorites(newFavorites);
    }
  };

  const handleDragEnd = async () => {
    if (!draggedItem) return;
    setDraggedItem(null);
    
    // Сохраняем новый порядок
    try {
      const symbolOrder = localFavorites.map(f => f.symbol);
      const response = await fetch('/api/favorites/reorder', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ symbol_order: symbolOrder }),
      });
      
      if (response.ok) {
        onUpdate();
      } else {
        alert('Ошибка сохранения порядка избранного');
        // Восстанавливаем исходный порядок
        setLocalFavorites(favorites);
      }
    } catch (error) {
      console.error('Ошибка сохранения порядка избранного:', error);
      alert('Ошибка сохранения порядка избранного');
      setLocalFavorites(favorites);
    }
  };

  const openTradingView = (symbol: string) => {
    const cleanSymbol = symbol.replace('USDT', '');
    const url = `https://www.tradingview.com/chart/?symbol=BYBIT:${cleanSymbol}USDT.P&interval=1`;
    window.open(url, '_blank');
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-lg w-full max-w-4xl max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200 bg-yellow-50">
          <div>
            <h2 className="text-2xl font-bold text-gray-900">Управление избранным</h2>
            <p className="text-gray-600">Настройте свой список избранных торговых пар</p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 p-2"
          >
            <X className="w-6 h-6" />
          </button>
        </div>

        {/* Instructions */}
        <div className="p-4 bg-blue-50 border-b border-gray-200">
          <div className="flex items-start space-x-4">
            <div className="text-blue-600 mt-1">
              <GripVertical className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-medium text-blue-900">Инструкция по использованию</h3>
              <ul className="text-sm text-blue-700 mt-1 space-y-1">
                <li>• Перетаскивайте элементы для изменения порядка</li>
                <li>• Нажмите на иконку карандаша для редактирования заметок и цвета</li>
                <li>• Нажмите на иконку сердца для удаления из избранного</li>
                <li>• Цвет будет использоваться для выделения пары в списке избранного</li>
              </ul>
            </div>
          </div>
        </div>

        {/* Favorites List */}
        <div className="flex-1 overflow-y-auto p-6">
          {localFavorites.length === 0 ? (
            <div className="text-center py-12 text-gray-500">
              <Heart className="w-12 h-12 mx-auto mb-4 text-gray-300" />
              <p>У вас пока нет избранных торговых пар</p>
              <p className="mt-2 text-sm">Добавьте пары в избранное, нажав на иконку сердечка в списке торговых пар</p>
            </div>
          ) : (
            <div className="space-y-4">
              {localFavorites.map((item) => (
                <div 
                  key={item.id} 
                  className={`bg-white rounded-lg shadow border-l-4 p-4 ${
                    draggedItem?.id === item.id ? 'opacity-50' : ''
                  }`}
                  style={{ borderLeftColor: item.color || '#FFD700' }}
                  draggable
                  onDragStart={(e) => handleDragStart(e, item)}
                  onDragOver={(e) => handleDragOver(e, item)}
                  onDragEnd={handleDragEnd}
                >
                  {editingId === item.id ? (
                    // Режим редактирования
                    <div>
                      <div className="flex items-center justify-between mb-3">
                        <div className="flex items-center space-x-3">
                          <GripVertical className="w-5 h-5 text-gray-400 cursor-move" />
                          <span className="font-bold text-lg text-gray-900">{item.symbol}</span>
                        </div>
                        
                        <div className="flex items-center space-x-2">
                          <button
                            onClick={saveEdit}
                            disabled={loading}
                            className="text-green-600 hover:text-green-700 p-1"
                            title="Сохранить"
                          >
                            <Save className="w-5 h-5" />
                          </button>
                          <button
                            onClick={cancelEdit}
                            disabled={loading}
                            className="text-gray-500 hover:text-gray-600 p-1"
                            title="Отменить"
                          >
                            <X className="w-5 h-5" />
                          </button>
                        </div>
                      </div>
                      
                      <div className="mb-4">
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                          Заметки
                        </label>
                        <textarea
                          value={editingNotes}
                          onChange={(e) => setEditingNotes(e.target.value)}
                          className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                          rows={3}
                          placeholder="Добавьте заметки о торговой паре..."
                        />
                      </div>
                      
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                          Цвет
                        </label>
                        <div className="flex flex-wrap gap-2">
                          {colorOptions.map(color => (
                            <button
                              key={color.value}
                              onClick={() => setEditingColor(color.value)}
                              className={`w-8 h-8 rounded-full border-2 ${
                                editingColor === color.value ? 'border-gray-900' : 'border-gray-200'
                              }`}
                              style={{ backgroundColor: color.value }}
                              title={color.name}
                            />
                          ))}
                        </div>
                      </div>
                    </div>
                  ) : (
                    // Режим просмотра
                    <div>
                      <div className="flex items-center justify-between mb-3">
                        <div className="flex items-center space-x-3">
                          <GripVertical className="w-5 h-5 text-gray-400 cursor-move" />
                          <div className={`w-3 h-3 rounded-full ${item.is_active ? 'bg-green-500' : 'bg-red-500'}`}></div>
                          <span className="font-bold text-lg text-gray-900">{item.symbol}</span>
                        </div>
                        
                        <div className="flex items-center space-x-2">
                          <button
                            onClick={() => startEdit(item)}
                            disabled={loading}
                            className="text-blue-600 hover:text-blue-700 p-1"
                            title="Редактировать"
                          >
                            <Edit className="w-5 h-5" />
                          </button>
                          <button
                            onClick={() => removeFromFavorites(item.symbol)}
                            disabled={loading}
                            className="text-red-600 hover:text-red-700 p-1"
                            title="Удалить из избранного"
                          >
                            <HeartOff className="w-5 h-5" />
                          </button>
                          <button
                            onClick={() => openTradingView(item.symbol)}
                            className="text-blue-600 hover:text-blue-800 p-1"
                            title="Открыть в TradingView"
                          >
                            <ExternalLink className="w-5 h-5" />
                          </button>
                        </div>
                      </div>
                      
                      <div className="grid grid-cols-2 gap-4 text-sm">
                        {item.price_drop_percentage && (
                          <div>
                            <span className="text-gray-600">Падение цены:</span>
                            <div className="font-semibold text-red-600">{item.price_drop_percentage.toFixed(2)}%</div>
                          </div>
                        )}
                        
                        {item.current_price && (
                          <div>
                            <span className="text-gray-600">Текущая цена:</span>
                            <div className="font-mono text-gray-900">${item.current_price.toFixed(8)}</div>
                          </div>
                        )}
                      </div>
                      
                      {item.notes && (
                        <div className="mt-3 p-3 bg-gray-50 rounded-lg text-sm text-gray-700">
                          {item.notes}
                        </div>
                      )}
                      
                      <div className="mt-3 pt-3 border-t border-gray-200 text-xs text-gray-500">
                        <div className="flex justify-between">
                          <span>Добавлено в избранное: {formatTime(item.favorite_added_at || '', 'local')}</span>
                          <span>Порядок: {item.sort_order !== undefined ? item.sort_order + 1 : 'Не задан'}</span>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-6 border-t border-gray-200 bg-gray-50">
          <div className="flex justify-between items-center">
            <div className="text-sm text-gray-600">
              Всего избранных пар: {localFavorites.length}
            </div>
            <button
              onClick={onClose}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
            >
              Закрыть
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default FavoritesModal;