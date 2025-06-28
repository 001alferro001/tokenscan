import { useEffect, useCallback } from 'react';
import { useTimeZone } from '../contexts/TimeZoneContext';

/**
 * Хук для синхронизации времени с сервером биржи
 */
export const useTimeSync = () => {
  const { setServerTimeOffset, setIsTimeSynced } = useTimeZone();

  const syncTime = useCallback(async () => {
    try {
      const startTime = Date.now();
      
      const response = await fetch('/api/time');
      if (!response.ok) {
        throw new Error('Ошибка получения времени сервера');
      }
      
      const endTime = Date.now();
      const networkDelay = (endTime - startTime) / 2;
      
      const data = await response.json();
      
      // Предполагаем, что сервер возвращает время в миллисекундах
      const serverTime = data.server_time || data.exchange_time || Date.now();
      const adjustedClientTime = startTime + networkDelay;
      
      const offset = serverTime - adjustedClientTime;
      
      setServerTimeOffset(offset);
      setIsTimeSynced(true);
      
      console.log('Время синхронизировано:', {
        serverTime: new Date(serverTime).toISOString(),
        clientTime: new Date(adjustedClientTime).toISOString(),
        offset: offset,
        networkDelay: networkDelay
      });
      
    } catch (error) {
      console.error('Ошибка синхронизации времени:', error);
      setIsTimeSynced(false);
    }
  }, [setServerTimeOffset, setIsTimeSynced]);

  useEffect(() => {
    // Первоначальная синхронизация
    syncTime();
    
    // Периодическая синхронизация каждые 5 минут
    const interval = setInterval(syncTime, 5 * 60 * 1000);
    
    return () => clearInterval(interval);
  }, [syncTime]);

  return { syncTime };
};