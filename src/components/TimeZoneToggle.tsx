import React from 'react';
import { Clock, Globe } from 'lucide-react';
import { useTimeZone } from '../contexts/TimeZoneContext';

const TimeZoneToggle: React.FC = () => {
  const { timeZone, setTimeZone } = useTimeZone();

  return (
    <div className="flex items-center space-x-2 bg-gray-100 rounded-lg p-2">
      <Clock className="w-4 h-4 text-gray-600" />
      <button
        onClick={() => setTimeZone('UTC')}
        className={`px-3 py-1 rounded text-sm font-medium transition-colors ${
          timeZone === 'UTC' 
            ? 'bg-blue-600 text-white' 
            : 'bg-white text-gray-700 hover:bg-gray-50'
        }`}
      >
        UTC
      </button>
      <button
        onClick={() => setTimeZone('local')}
        className={`px-3 py-1 rounded text-sm font-medium transition-colors ${
          timeZone === 'local' 
            ? 'bg-blue-600 text-white' 
            : 'bg-white text-gray-700 hover:bg-gray-50'
        }`}
      >
        <Globe className="w-3 h-3 inline mr-1" />
        Локальное
      </button>
    </div>
  );
};

export default TimeZoneToggle;