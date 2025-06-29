/**
 * Утилиты для работы с временем
 * Все данные от сервера приходят в UTC timestamp (миллисекунды)
 */

export interface FormatTimeOptions {
  includeDate?: boolean;
  includeSeconds?: boolean;
  includeMilliseconds?: boolean;
}

/**
 * Форматирование времени с учетом часового пояса
 * @param timestamp - UTC timestamp в миллисекундах или ISO строка
 * @param timeZone - 'UTC' или 'local'
 * @param options - опции форматирования
 */
export const formatTime = (
  timestamp: number | string, 
  timeZone: 'UTC' | 'local' = 'local',
  options: FormatTimeOptions = {}
): string => {
  try {
    let date: Date;
    
    // Обрабатываем разные форматы входных данных
    if (typeof timestamp === 'number') {
      // UTC timestamp в миллисекундах
      date = new Date(timestamp);
    } else if (typeof timestamp === 'string') {
      // ISO строка или другой формат
      date = new Date(timestamp);
    } else {
      return 'Некорректное время';
    }
    
    if (isNaN(date.getTime())) {
      console.error('Некорректная временная метка:', timestamp);
      return 'Некорректное время';
    }

    const {
      includeDate = true,
      includeSeconds = true,
      includeMilliseconds = false
    } = options;

    // Настройки форматирования
    const formatOptions: Intl.DateTimeFormatOptions = {
      hour12: false
    };

    // Устанавливаем часовой пояс
    if (timeZone === 'UTC') {
      formatOptions.timeZone = 'UTC';
    }

    // Добавляем компоненты времени
    if (includeDate) {
      formatOptions.year = 'numeric';
      formatOptions.month = '2-digit';
      formatOptions.day = '2-digit';
    }

    formatOptions.hour = '2-digit';
    formatOptions.minute = '2-digit';

    if (includeSeconds) {
      formatOptions.second = '2-digit';
    }

    let formattedTime = date.toLocaleString('ru-RU', formatOptions);

    // Добавляем миллисекунды вручную, если нужно
    if (includeMilliseconds) {
      const ms = date.getMilliseconds().toString().padStart(3, '0');
      formattedTime += `.${ms}`;
    }

    // Добавляем индикатор часового пояса
    if (timeZone === 'UTC') {
      formattedTime += ' UTC';
    } else {
      // Получаем смещение локального часового пояса
      const offset = date.getTimezoneOffset();
      const offsetHours = Math.abs(Math.floor(offset / 60));
      const offsetMinutes = Math.abs(offset % 60);
      const offsetSign = offset <= 0 ? '+' : '-';
      const offsetString = `${offsetSign}${offsetHours.toString().padStart(2, '0')}:${offsetMinutes.toString().padStart(2, '0')}`;
      
      // Получаем название часового пояса
      const timezoneName = Intl.DateTimeFormat().resolvedOptions().timeZone.split('/').pop() || 'Local';
      formattedTime += ` (${offsetString})`;
    }

    return formattedTime;

  } catch (error) {
    console.error('Ошибка форматирования времени:', error, timestamp);
    return 'Ошибка времени';
  }
};

/**
 * Получение информации о локальном часовом поясе
 */
export const getTimezoneInfo = () => {
  const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  const offset = new Date().getTimezoneOffset();
  const offsetHours = Math.abs(Math.floor(offset / 60));
  const offsetMinutes = Math.abs(offset % 60);
  const offsetSign = offset <= 0 ? '+' : '-';

  return {
    timezone,
    offsetString: `UTC${offsetSign}${offsetHours.toString().padStart(2, '0')}:${offsetMinutes.toString().padStart(2, '0')}`,
    offsetMinutes: -offset // Инвертируем для правильного отображения
  };
};

/**
 * Преобразование UTC timestamp в локальное время
 */
export const utcToLocal = (utcTimestamp: number): Date => {
  return new Date(utcTimestamp);
};

/**
 * Преобразование локального времени в UTC timestamp
 */
export const localToUtc = (localDate: Date): number => {
  return localDate.getTime();
};

/**
 * Проверка, является ли timestamp корректным
 */
export const isValidTimestamp = (timestamp: number | string): boolean => {
  try {
    const date = new Date(timestamp);
    return !isNaN(date.getTime());
  } catch {
    return false;
  }
};

/**
 * Форматирование времени для отображения в интерфейсе
 */
export const formatDisplayTime = (timestamp: number | string, timeZone: 'UTC' | 'local' = 'local'): string => {
  return formatTime(timestamp, timeZone, {
    includeDate: true,
    includeSeconds: true,
    includeMilliseconds: false
  });
};

/**
 * Краткое форматирование времени (только время без даты)
 */
export const formatShortTime = (timestamp: number | string, timeZone: 'UTC' | 'local' = 'local'): string => {
  return formatTime(timestamp, timeZone, {
    includeDate: false,
    includeSeconds: true,
    includeMilliseconds: false
  });
};

/**
 * Получение текущего UTC timestamp в миллисекундах
 */
export const getCurrentUtcTimestamp = (): number => {
  return Date.now();
};