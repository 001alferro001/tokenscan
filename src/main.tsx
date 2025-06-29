import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App.tsx';
import './index.css';
import { TimeZoneProvider } from './contexts/TimeZoneContext';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <TimeZoneProvider>
      <App />
    </TimeZoneProvider>
  </StrictMode>
);