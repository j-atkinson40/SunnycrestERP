import { useEffect } from "react";
import { useLayout } from "@/contexts/layout-context";

/** Hides the MobileTabBar while the calling component is mounted. */
export function useHideTabBar() {
  const { setHideTabBar } = useLayout();

  useEffect(() => {
    setHideTabBar(true);
    return () => setHideTabBar(false);
  }, [setHideTabBar]);
}
