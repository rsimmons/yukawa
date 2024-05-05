import { useEffect, useRef } from "react";

export const useEffectOnce = (effect: () => void) => {
  const hasRun = useRef(false);
  useEffect(() => {
    if (!hasRun.current) {
      effect();
      hasRun.current = true;
    }
  }, []);
}

export const touchAvail = ('ontouchstart' in window);
