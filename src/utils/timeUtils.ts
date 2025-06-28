/**
 * Утилиты для работы с временными метками и часовыми поясами
 */

export type TimeZoneType = 'UTC' | 'local';

/**
 * Нормализация временной метки в UNIX миллисекунды
 */
export function normalizeTimestamp(timestamp: string | number): number {
  if (typeof timestamp === 'number') {
    // Уже UNIX миллисекунды
    return timestamp;
  }
  
  if (typeof timestamp === 'string') {
    // ISO строка или другой формат
    const date = new Date(timestamp);
    if (isNaN(date.getTime())) {
      console.error('Некорректная временная метка:', timestamp);
      return Date.now();
    }
    return date.getTime();
  }
  
  console.error('Неподдерживаемый тип временной метки:', timestamp);
  return Date.now();
}

/**
 * Форматирование времени с поддержкой часовых поясов
 */
export function formatTime(
  timestamp: string | number, 
  timeZone: TimeZoneType = 'local',
  options: {
    includeDate?: boolean;
    includeSeconds?: boolean;
    includeMilliseconds?: boolean;
  } = {}
): string {
  const {
    includeDate = true,
    includeSeconds = true,
    includeMilliseconds = false
  } = options;

  try {
    const normalizedTimestamp = normalizeTimestamp(timestamp);
    const date = new Date(normalizedTimestamp);
    
    if (isNaN(date.getTime())) {
      console.error('Некорректная дата после нормализации:', timestamp);
      return 'Некорректное время';
    }

    const formatOptions: Intl.DateTimeFormatOptions = {
      timeZone: timeZone === 'UTC' ? 'UTC' : undefined,
      year: includeDate ? 'numeric' : undefined,
      month: includeDate ? '2-digit' : undefined,
      day: includeDate ? '2-digit' : undefined,
      hour: '2-digit',
      minute: '2-digit',
      second: includeSeconds ? '2-digit' : undefined,
      hour12: false
    };

    let formatted = date.toLocaleString('ru-RU', formatOptions);
    
    // Добавляем миллисекунды если нужно
    if (includeMilliseconds) {
      const ms = date.getMilliseconds().toString().padStart(3, '0');
      formatted += `.${ms}`;
    }
    
    // Добавляем индикатор часового пояса
    if (timeZone === 'UTC') {
      formatted += ' UTC';
    } else {
      const offset = getTimezoneOffset();
      formatted += ` ${offset}`;
    }
    
    return formatted;
  } catch (error) {
    console.error('Ошибка форматирования времени:', error, timestamp);
    return 'Ошибка времени';
  }
}

/**
 * Получение смещения часового пояса
 */
export function getTimezoneOffset(): string {
  const offset = new Date().getTimezoneOffset();
  const hours = Math.abs(Math.floor(offset / 60));
  const minutes = Math.abs(offset % 60);
  const sign = offset <= 0 ? '+' : '-';
  return `UTC${sign}${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}`;
}

/**
 * Получение информации о часовом поясе
 */
export function getTimezoneInfo() {
  const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  const offsetString = getTimezoneOffset();
  
  return {
    timezone,
    offsetString,
    name: timezone.split('/').pop() || 'Unknown'
  };
}

/**
 * Форматирование времени для графиков Chart.js
 */
export function formatChartTime(timestamp: number, timeZone: TimeZoneType): string {
  try {
    const date = new Date(timestamp);
    
    if (timeZone === 'UTC') {
      return date.toLocaleTimeString('ru-RU', { 
        timeZone: 'UTC',
        hour: '2-digit', 
        minute: '2-digit',
        hour12: false
      });
    } else {
      return date.toLocaleTimeString('ru-RU', { 
        hour: '2-digit', 
        minute: '2-digit',
        hour12: false
      });
    }
  } catch (error) {
    console.error('Ошибка форматирования времени для графика:', error);
    return '00:00';
  }
}

/**
 * Создание читаемой временной метки
 */
export function createReadableTimestamp(timestamp: number): string {
  try {
    const date = new Date(timestamp);
    return date.toLocaleString('ru-RU', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false
    });
  } catch (error) {
    console.error('Ошибка создания читаемой временной метки:', error);
    return '';
  }
}

/**
 * Проверка валидности временной метки
 */
export function isValidTimestamp(timestamp: string | number): boolean {
  try {
    const normalized = normalizeTimestamp(timestamp);
    const date = new Date(normalized);
    return !isNaN(date.getTime()) && date.getTime() > 0;
  } catch {
    return false;
  }
}