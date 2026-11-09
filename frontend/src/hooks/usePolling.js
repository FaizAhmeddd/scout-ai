import { useCallback, useEffect, useRef, useState } from "react";

import { errorStatus, isOffline } from "../services/apiClient.js";

const MAX_BACKOFF_MS = 15000;

/**
 * Loads data once, then keeps refreshing every `intervalMs` while `shouldPoll(data)` is true.
 *
 * Resilience: if a refresh fails because the server is unreachable while a job is still running, the last
 * data stays on screen and polling continues with backoff. 401/404 stop polling (handled by the caller).
 */
export function usePolling(load, { intervalMs = 2500, shouldPoll = () => false, deps = [] } = {}) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const loadRef = useRef(load);
  const pollRef = useRef(shouldPoll);
  const dataRef = useRef(null);
  const genRef = useRef(0); // bumps on every (re)subscription and on unmount, stopping stale loops
  loadRef.current = load;
  pollRef.current = shouldPoll;

  const safePoll = (value) => {
    try {
      return Boolean(value) && Boolean(pollRef.current(value));
    } catch {
      return false;
    }
  };

  const refresh = useCallback(async () => {
    try {
      const next = await loadRef.current();
      dataRef.current = next;
      setData(next);
      setError(null);
      return { ok: true, data: next };
    } catch (err) {
      setError(err);
      return { ok: false, error: err };
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    let timer;
    let failures = 0;
    const gen = ++genRef.current;
    dataRef.current = null;
    setData(null);
    setError(null);
    setLoading(true);

    const tick = async () => {
      if (cancelled || gen !== genRef.current) return;
      const result = await refresh();
      if (cancelled || gen !== genRef.current) return;
      if (result.ok) {
        failures = 0;
        if (safePoll(result.data)) timer = setTimeout(tick, intervalMs);
        return;
      }
      const status = errorStatus(result.error);
      // Keep trying through transient outages while something is still processing.
      if (status !== 401 && status !== 404 && isOffline(result.error) && safePoll(dataRef.current)) {
        failures += 1;
        timer = setTimeout(tick, Math.min(intervalMs * 2 ** failures, MAX_BACKOFF_MS));
      }
    };
    tick();
    return () => {
      cancelled = true;
      genRef.current += 1;
      clearTimeout(timer);
    };
  }, deps);

  const retry = useCallback(async () => {
    setLoading(true);
    const gen = ++genRef.current;
    const result = await refresh();
    // Restart polling if the reloaded item is still processing.
    const loop = async () => {
      if (gen !== genRef.current) return;
      const r = await refresh();
      if (gen === genRef.current && r.ok && safePoll(r.data)) setTimeout(loop, intervalMs);
    };
    if (result.ok && safePoll(result.data)) setTimeout(loop, intervalMs);
    return result;
  }, [refresh, intervalMs]);

  const update = useCallback((next) => {
    dataRef.current = next;
    setData(next);
  }, []);

  return { data, error, loading, refresh, retry, setData: update };
}
