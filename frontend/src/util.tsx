import { useCallback, useEffect, useRef } from "react";

function genRandomStr32(): string {
  return Math.random().toString(16).substring(2, 10);
}
export function genRandomStr64(): string {
  return genRandomStr32() + genRandomStr32();
}

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

type useRAFCallback = (elapsedTime: number) => void;
export function useRAF(callback: useRAFCallback) {
  const frameId = useRef<number | null>(null);
  const startTime = useRef<number | null>(null);
  const savedCallback = useRef<useRAFCallback>(callback);

  // Update the saved callback when it changes
  useEffect(() => {
    savedCallback.current = callback;
  }, [callback]);

  // Function to wrap requestAnimationFrame
  const requestFrame = useCallback((time: number) => {
    if (startTime.current === null) {
      startTime.current = time; // Record the start time on the first frame
    }
    const elapsedTime = time - startTime.current;

    savedCallback.current(0.001*elapsedTime);

    frameId.current = requestAnimationFrame(requestFrame); // Schedule the next frame
  }, []);

  // Start the animation frame loop
  useEffect(() => {
    frameId.current = requestAnimationFrame(requestFrame); // Start the animation

    return () => {
      if (frameId.current !== null) {
        cancelAnimationFrame(frameId.current); // Cleanup on unmount
      }
    };
  }, [requestFrame]);
}
