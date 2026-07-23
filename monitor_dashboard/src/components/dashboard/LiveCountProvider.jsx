import { createContext, useContext, useEffect, useState } from 'react';
import { useLocation } from 'react-router-dom';

const LiveCountContext = createContext({
  enabled: false,
  setEnabled: () => {},
});

export function LiveCountProvider({ children }) {
  const [enabled, setEnabled] = useState(false);
  const { pathname } = useLocation();

  useEffect(() => {
    setEnabled(false);
  }, [pathname]);

  return (
    <LiveCountContext.Provider value={{ enabled, setEnabled }}>
      {children}
    </LiveCountContext.Provider>
  );
}

export function useLiveCount() {
  return useContext(LiveCountContext);
}
