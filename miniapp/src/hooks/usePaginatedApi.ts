import { useState, useCallback, useMemo } from "react";
import { apiFetch } from "../api/client";
import { useApi } from "./useApi";

const PAGE_SIZE = 20;

type UsePaginatedApiResult<T> = {
  data: T[] | null;
  loading: boolean;
  error: string | null;
  page: number;
  hasMore: boolean;
  nextPage: () => void;
  prevPage: () => void;
  resetPage: () => void;
  refetch: () => void;
};

export function usePaginatedApi<T>(
  buildUrl: (limit: number, offset: number) => string,
  deps: unknown[] = [],
): UsePaginatedApiResult<T> {
  const [page, setPage] = useState(0);

  const limit = PAGE_SIZE + 1;
  const offset = page * PAGE_SIZE;

  const fetcher = useCallback(
    () => apiFetch<T[]>(buildUrl(limit, offset)),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [page, ...deps],
  );

  const { data: raw, loading, error, refetch } = useApi(fetcher, [page, ...deps]);

  const hasMore = (raw?.length ?? 0) > PAGE_SIZE;

  const data = useMemo(() => {
    if (!raw) return null;
    return hasMore ? raw.slice(0, PAGE_SIZE) : raw;
  }, [raw, hasMore]);

  const nextPage = useCallback(() => {
    if (hasMore) setPage((p) => p + 1);
  }, [hasMore]);

  const prevPage = useCallback(() => {
    setPage((p) => Math.max(0, p - 1));
  }, []);

  const resetPage = useCallback(() => {
    setPage(0);
  }, []);

  return { data, loading, error, page, hasMore, nextPage, prevPage, resetPage, refetch };
}
