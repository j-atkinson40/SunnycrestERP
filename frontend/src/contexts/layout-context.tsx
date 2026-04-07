import { createContext, useContext, useState, type ReactNode } from "react";

interface LayoutContextValue {
  hideTabBar: boolean;
  setHideTabBar: (hide: boolean) => void;
}

const LayoutContext = createContext<LayoutContextValue>({
  hideTabBar: false,
  setHideTabBar: () => {},
});

export function LayoutProvider({ children }: { children: ReactNode }) {
  const [hideTabBar, setHideTabBar] = useState(false);

  return (
    <LayoutContext.Provider value={{ hideTabBar, setHideTabBar }}>
      {children}
    </LayoutContext.Provider>
  );
}

export function useLayout() {
  return useContext(LayoutContext);
}
