import { useEffect, useState, useCallback, useRef } from "react";
import { NetworkError } from "../api/client";

type UseApiResult<T> = {
  data: T | null;
  loading: boolean;
  error: string | null;
  isOffline: boolean;
  refetch: () => void;
};

export function useApi<T>(
  fetcher: () => Promise<T>,
  deps: unknown[] = [],
): UseApiResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isOffline, setIsOffline] = useState(false);
  const mountedRef = useRef(true);
  const hadNetworkErrorRef = useRef(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    setIsOffline(false);
    try {
      const result = await fetcher();
      if (mountedRef.current) {
        setData(result);
        hadNetworkErrorRef.current = false;
      }
    } catch (e) {
      if (mountedRef.current) {
        if (e instanceof NetworkError) {
          setIsOffline(true);
          hadNetworkErrorRef.current = true;
        }
        setError(e instanceof Error ? e.message : String(e));
      }
    } finally {
      if (mountedRef.current) {
        setLoading(false);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    mountedRef.current = true;
    load();
    return () => {
      mountedRef.current = false;
    };
  }, [load]);

  useEffect(() => {
    const onOnline = () => {
      if (hadNetworkErrorRef.current && mountedRef.current) {
        load();
      }
    };
    window.addEventListener("online", onOnline);
    return () => window.removeEventListener("online", onOnline);
  }, [load]);

  return { data, loading, error, isOffline, refetch: load };
}
