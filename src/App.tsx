iv>
        </nav>

        {/* Main Content */}
        <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          {/* Volume Alerts */}
          {activeTab === 'volume' && (
            <div>
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-2xl font-bold text-gray-900">Алерты по объему</h2>
                <button
                  onClick={() => clearAlerts('volume_spike')}
                  className="bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded-lg transition-colors"
                >
                  Очистить
                </button>
              </div>

              <div className="space-y-4">
                {volumeAlerts.length === 0 ? (
                  <div className="text-center py-12 text-gray-500">
                    <TrendingUp className="w-12 h-12 mx-auto mb-4 text-gray-300" />
                    <p>Нет алертов по объему</p>
                  </div>
                ) : (
                  volumeAlerts.map(renderAlertCard)
                )}
              </div>
            </div>
          )}

          {/* Consecutive Alerts */}
          {activeTab === 'consecutive' && (
            <div>
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-2xl font-bold text-gray-900">LONG последовательности</h2>
                <button
                  onClick={() => clearAlerts('consecutive_long')}
                  className="bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded-lg transition-colors"
                >
                  Очистить
                </button>
              </div>

              <div className="space-y-4">
                {consecutiveAlerts.length === 0 ? (
                  <div className="text-center py-12 text-gray-500">
                    <BarChart3 className="w-12 h-12 mx-auto mb-4 text-gray-300" />
                    <p>Нет алертов по последовательностям</p>
                  </div>
                ) : (
                  consecutiveAlerts.map(renderAlertCard)
                )}
              </div>
            </div>
          )}

          {/* Priority Alerts */}
          {activeTab === 'priority' && (
            <div>
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-2xl font-bold text-gray-900">Приоритетные алерты</h2>
                <button
                  onClick={() => clearAlerts('priority')}
                  className="bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded-lg transition-colors"
                >
                  Очистить
                </button>
              </div>

              <div className="space-y-4">
                {priorityAlerts.length === 0 ? (
                  <div className="text-center py-12 text-gray-500">
                    <Star className="w-12 h-12 mx-auto mb-4 text-gray-300" />
                    <p>Нет приоритетных алертов</p>
                  </div>
                ) : (
                  priorityAlerts.map(renderAlertCard)
                )}
              </div>
            </div>
          )}

          {/* Smart Money Alerts */}
          {activeTab === 'smart_money' && (
            <div>
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-2xl font-bold text-gray-900">Smart Money Concepts</h2>
                <button
                  onClick={() => setSmartMoneyAlerts([])}
                  className="bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded-lg transition-colors"
                >
                  Очистить
                </button>
              </div>

              <div className="space-y-4">
                {smartMoneyAlerts.length === 0 ? (
                  <div className="text-center py-12 text-gray-500">
                    <Brain className="w-12 h-12 mx-auto mb-4 text-gray-300" />
                    <p>Нет сигналов Smart Money</p>
                  </div>
                ) : (
                  smartMoneyAlerts.map(renderSmartMoneyCard)
                )}
              </div>
            </div>
          )}

          {/* Watchlist */}
          {activeTab === 'watchlist' && (
            <div>
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-2xl font-bold text-gray-900">Список торговых пар</h2>
                <button
                  onClick={() => setShowWatchlistModal(true)}
                  className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg transition-colors"
                >
                  Управление
                </button>
              </div>

              <div className="space-y-4">
                {watchlist.length === 0 ? (
                  <div className="text-center py-12 text-gray-500">
                    <List className="w-12 h-12 mx-auto mb-4 text-gray-300" />
                    <p>Нет торговых пар в списке</p>
                  </div>
                ) : (
                  watchlist.map(renderWatchlistCard)
                )}
              </div>
            </div>
          )}

          {/* Stream Data */}
          {activeTab === 'stream' && (
            <div>
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-2xl font-bold text-gray-900">Потоковые данные</h2>
                <div className="flex items-center space-x-4">
                  <span className="text-sm text-gray-600">
                    Обновлений: {streamData.length} / Пар в watchlist: {watchlist.length} / Подписано: {connectionInfo.subscribedCount}
                  </span>
                  <button
                    onClick={() => connectWebSocket()}
                    className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg transition-colors"
                    disabled={connectionStatus === 'connecting'}
                  >
                    {connectionStatus === 'connecting' ? 'Подключение...' : 'Переподключить'}
                  </button>
                </div>
              </div>

              <div className="space-y-4">
                {streamData.slice(0, 200).map((item, index) => (
                  <div key={`${item.symbol}-${index}`} className="bg-white rounded-lg shadow-md border border-gray-200 p-4 w-full">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-4">
                        <div className={`w-4 h-4 rounded-full ${
                          item.is_long ? 'bg-green-500' : 'bg-red-500'
                        }`}></div>

                        <div>
                          <span className="font-semibold text-gray-900 text-lg">{item.symbol}</span>
                          <div className="flex items-center space-x-2 text-sm">
                            <span className={`px-2 py-1 rounded text-xs font-medium ${
                              item.is_long ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                            }`}>
                              {item.is_long ? 'LONG' : 'SHORT'}
                            </span>
                            {item.is_closed && (
                              <span className="px-2 py-1 bg-blue-100 text-blue-800 text-xs rounded-full">Закрыта</span>
                            )}
                          </div>
                        </div>
                      </div>

                      <div className="text-right">
                        <div className="text-xl font-bold text-gray-900">
                          ${item.price.toFixed(8)}
                        </div>
                        <div className="text-sm text-gray-600">
                          Vol: {formatVolume(item.volume_usdt)}
                        </div>
                      </div>

                      <div className="flex items-center space-x-2">
                        <div className="text-right text-sm text-gray-500">
                          <div>{formatTime(item.timestamp, 'local', { includeDate: false, includeSeconds: true })}</div>
                          <div className="text-xs">
                            {formatVolume(item.volume)} {item.symbol.replace('USDT', '')}
                          </div>
                        </div>

                        <button
                          onClick={() => openTradingView(item.symbol)}
                          className="text-blue-600 hover:text-blue-800 p-1"
                          title="Открыть в TradingView"
                        >
                          <ExternalLink className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </main>

        {/* Modals */}
        {selectedAlert && (
          <ChartSelector
            alert={selectedAlert}
            onClose={() => setSelectedAlert(null)}
          />
        )}

        {selectedSmartMoneyAlert && (
          <SmartMoneyChartModal
            alert={selectedSmartMoneyAlert}
            onClose={() => setSelectedSmartMoneyAlert(null)}
          />
        )}

        {showWatchlistModal && (
          <WatchlistModal
            watchlist={watchlist}
            onClose={() => setShowWatchlistModal(false)}
            onUpdate={loadWatchlist}
          />
        )}

        {showStreamModal && (
          <StreamDataModal
            streamData={streamData}
            connectionStatus={connectionStatus}
            onClose={() => setShowStreamModal(false)}
          />
        )}

        {showSettings && (
          <SettingsModal
            settings={settings}
            onClose={() => setShowSettings(false)}
            onSave={handleSettingsSave}
          />
        )}
      </div>
    </TimeZoneProvider>
  );
};

export default App;