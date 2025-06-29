import React, { createContext, useContext, useState, ReactNode } from 'react';

type TimeZone = 'UTC' | 'local';

interface TimeZoneContextType {
  timeZone: TimeZone;
  setTimeZone: (tz: TimeZone) => void;
}

const TimeZoneContext = createContext<TimeZoneContextType | undefined>(undefined);

export const useTimeZone = () => {
  const context = useContext(TimeZoneContext);
  if (!context) {
    throw new Error('useTimeZone must be used within a TimeZoneProvider');
  }
  return context;
};

interface TimeZoneProviderProps {
  children: ReactNode;
}

export const TimeZoneProvider: React.FC<TimeZoneProviderProps> = ({ children }) => {
  const [timeZone, setTimeZone] = useState<TimeZone>('local');

  return (
    <TimeZoneContext.Provider value={{ timeZone, setTimeZone }}>
      {children}
    </TimeZoneContext.Provider>
  );
};