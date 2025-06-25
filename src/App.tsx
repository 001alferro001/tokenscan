          min="1"
                      max="10"
                      step="0.1"
                      value={settings.volume_analyzer.volume_multiplier}
                      onChange={(e) => setSettings(prev => ({
                        ...prev,
                        volume_analyzer: {
                          ...prev.volume_analyzer,
                          volume_multiplier: parseFloat(e.target.value)
                        }
                      }))}
                      className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium mb-2">Мин. объем (USDT)</label>
                    <input
                      type="number"
                      min="100"
                      value={settings.volume_analyzer.min_volume_usdt}
                      onChange={(e) => setSettings(prev => ({
                        ...prev,
                        volume_analyzer: {
                          ...prev.volume_analyzer,
                          min_volume_usdt: parseInt(e.target.value)
                        }
                      }))}
                      className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white"
                    />
                  </div>

                  <div className="col-span-2">
                    <label className="block text-sm font-medium mb-2">Группировка алертов (минуты)</label>
                    <input
                      type="number"
                      min="1"
                      max="60"
                      value={settings.volume_analyzer.alert_grouping_minutes}
                      onChange={(e) => setSettings(prev => ({
                        ...prev,
                        volume_analyzer: {
                          ...prev.volume_analyzer,
                          alert_grouping_minutes: parseInt(e.target.value)
                        }
                      }))}
                      className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white"
                    />
                    <p className="text-xs text-gray-400 mt-1">
                      Алерты для одного актива в течение этого времени будут группироваться
                    </p>
                  </div>
                </div>
              </div>

              <div>
                <h4 className="text-lg font-semibold mb-4 text-green-400">Анализ подряд идущих LONG свечей</h4>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium mb-2">Количество подряд свечей</label>
                    <input
                      type="number"
                      min="3"
                      max="20"
                      value={settings.volume_analyzer.consecutive_long_count}
                      onChange={(e) => setSettings(prev => ({
                        ...prev,
                        volume_analyzer: {
                          ...prev.volume_analyzer,
                          consecutive_long_count: parseInt(e.target.value)
                        }
                      }))}
                      className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white"
                    />
                    <p className="text-xs text-gray-400 mt-1">
                      Минимальное количество подряд идущих LONG свечей для алерта
                    </p>
                  </div>

                  <div>
                    <label className="block text-sm font-medium mb-2">Макс. отношение теней к телу</label>
                    <input
                      type="number"
                      min="0.1"
                      max="5.0"
                      step="0.1"
                      value={settings.volume_analyzer.max_shadow_to_body_ratio}
                      onChange={(e) => setSettings(prev => ({
                        ...prev,
                        volume_analyzer: {
                          ...prev.volume_analyzer,
                          max_shadow_to_body_ratio: parseFloat(e.target.value)
                        }
                      }))}
                      className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white"
                    />
                    <p className="text-xs text-gray-400 mt-1">
                      Максимальное отношение суммы теней к телу свечи
                    </p>
                  </div>

                  <div className="col-span-2">
                    <label className="block text-sm font-medium mb-2">Мин. размер тела (%)</label>
                    <input
                      type="number"
                      min="0.01"
                      max="10"
                      step="0.01"
                      value={settings.volume_analyzer.min_body_percentage}
                      onChange={(e) => setSettings(prev => ({
                        ...prev,
                        volume_analyzer: {
                          ...prev.volume_analyzer,
                          min_body_percentage: parseFloat(e.target.value)
                        }
                      }))}
                      className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white"
                    />
                    <p className="text-xs text-gray-400 mt-1">
                      Минимальный размер тела свечи в процентах от общего диапазона
                    </p>
                  </div>
                </div>
              </div>

              <div>
                <h4 className="text-lg font-semibold mb-4 text-purple-400">Фильтр по цене</h4>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium mb-2">Интервал проверки (мин)</label>
                    <input
                      type="number"
                      min="1"
                      max="60"
                      value={settings.price_filter.price_check_interval_minutes}
                      onChange={(e) => setSettings(prev => ({
                        ...prev,
                        price_filter: {
                          ...prev.price_filter,
                          price_check_interval_minutes: parseInt(e.target.value)
                        }
                      }))}
                      className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white"
                    />
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium mb-2">Период истории (дни)</label>
                    <input
                      type="number"
                      min="1"
                      max="365"
                      value={settings.price_filter.price_history_days}
                      onChange={(e) => setSettings(prev => ({
                        ...prev,
                        price_filter: {
                          ...prev.price_filter,
                          price_history_days: parseInt(e.target.value)
                        }
                      }))}
                      className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white"
                    />
                  </div>
                  
                  <div className="col-span-2">
                    <label className="block text-sm font-medium mb-2">Падение цены (%)</label>
                    <input
                      type="number"
                      min="1"
                      max="90"
                      step="0.1"
                      value={settings.price_filter.price_drop_percentage}
                      onChange={(e) => setSettings(prev => ({
                        ...prev,
                        price_filter: {
                          ...prev.price_filter,
                          price_drop_percentage: parseFloat(e.target.value)
                        }
                      }))}
                      className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white"
                    />
                  </div>
                </div>
              </div>

              <div>
                <h4 className="text-lg font-semibold mb-4 text-green-400">Telegram уведомления</h4>
                <div className="bg-gray-700 rounded-lg p-4">
                  <div className="flex items-center space-x-2 mb-3">
                    <span className={`w-3 h-3 rounded-full ${settings.telegram.enabled ? 'bg-green-400' : 'bg-red-400'}`}></span>
                    <span className="text-sm">
                      {settings.telegram.enabled ? 'Подключено' : 'Не настроено'}
                    </span>
                  </div>
                  <p className="text-xs text-gray-400">
                    Для настройки Telegram уведомлений добавьте в .env файл:
                  </p>
                  <div className="bg-black bg-opacity-50 rounded p-2 mt-2 text-xs font-mono">
                    TELEGRAM_BOT_TOKEN=your_bot_token<br/>
                    TELEGRAM_CHAT_ID=your_chat_id
                  </div>
                </div>
              </div>
            </div>
            
            <div className="flex space-x-3 mt-8">
              <button
                onClick={saveSettings}
                className="flex-1 bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded-lg transition-colors"
              >
                Сохранить
              </button>
              <button
                onClick={() => setShowSettings(false)}
                className="flex-1 bg-gray-600 hover:bg-gray-700 px-4 py-2 rounded-lg transition-colors"
              >
                Отмена
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;