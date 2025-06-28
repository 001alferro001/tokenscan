import React, { createContext, useContext, useState, ReactNode } from 'react';

export type TimeZoneType = 'UTC' | 'local';

interface TimeZoneContextType {
  timeZone: TimeZoneType;
  setTimeZone: (timeZone: TimeZoneType) => void;
  serverTimeOffset: number;
  setServerTimeOffset: (offset: number) => void;
  isTimeSynced: boolean;
  setIsTimeSynced: (synced: boolean) => void;
}

const TimeZoneContext = createContext<TimeZoneContextType | undefined>(undefined);

interface TimeZoneProviderProps {
  children: ReactNode;
}

export const TimeZoneProvider: React.FC<TimeZoneProviderProps> = ({ children }) => {
  const [timeZone, setTimeZone] = useState<TimeZoneType>('local');
  const [serverTimeOffset, setServerTimeOffset] = useState<number>(0);
  const [isTimeSynced, setIsTimeSynced] = useState<boolean>(false);

  return (
    <TimeZoneContext.Provider value={{
      timeZone,
      setTimeZone,
      serverTimeOffset,
      setServerTimeOffset,
      isTimeSynced,
      setIsTimeSynced
    }}>
      {children}
    </TimeZoneContext.Provider>
  );
};

export const useTimeZone = (): TimeZoneContextType => {
  const context = useContext(TimeZoneContext);
  if (context === undefined) {
    throw new Error('useTimeZone must be used within a TimeZoneProvider');
  }
  return context;
};