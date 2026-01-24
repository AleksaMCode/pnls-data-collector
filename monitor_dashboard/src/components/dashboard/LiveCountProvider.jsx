import { createContext, useContext, useState } from 'react';

const LiveCountContext = createContext({
  enabled: false,
  setEnabled: () => {},
});

export function LiveCountProvider({ children }) {
  const [enabled, setEnabled] = useState(false);
  return (
    <LiveCountContext.Provider value={{ enabled, setEnabled }}>
      {children}
    </LiveCountContext.Provider>
  );
}

export function useLiveCount() {
  return useContext(LiveCountContext);
}
