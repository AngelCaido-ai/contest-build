import { useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
  Text,
  Input,
  Button,
  Group,
  GroupItem,
  SkeletonElement,
} from "@telegram-tools/ui-kit";
import { usePaginatedApi } from "../hooks/usePaginatedApi";
import { EmptyState } from "../components/EmptyState";
import { Pagination } from "../components/Pagination";
import type { Listing } from "../types";

export function ListingsPage() {
  const navigate = useNavigate();

  const [priceMin, setPriceMin] = useState("");
  const [priceMax, setPriceMax] = useState("");

  const buildUrl = useCallback(
    (limit: number, offset: number) => {
      const params = new URLSearchParams();
      if (priceMin) params.set("price_min", priceMin);
      if (priceMax) params.set("price_max", priceMax);
      params.set("active", "true");
      params.set("exclude_own", "true");
      params.set("limit", String(limit));
      params.set("offset", String(offset));
      return `/listings?${params.toString()}`;
    },
    [priceMin, priceMax],
  );

  const {
    data: listings,
    loading,
    error,
    page,
    hasMore,
    nextPage,
    prevPage,
    resetPage,
    refetch,
  } = usePaginatedApi<Listing>(buildUrl, [priceMin, priceMax]);

  const handleApply = () => {
    resetPage();
    refetch();
  };

  return (
    <div className="flex flex-col gap-4">
      <Text type="title2" weight="bold">
        Listings Catalog
      </Text>
      <Button text="Create Listing" type="primary" onClick={() => navigate("/listings/new")} />

      <Group header="Filters">
        <div className="flex gap-2 px-4 py-2">
          <div className="min-w-0 flex-1">
            <Input
              placeholder="Price from"
              type="text"
              numeric
              value={priceMin}
              onChange={(v) => setPriceMin(v)}
            />
          </div>
          <div className="min-w-0 flex-1">
            <Input
              placeholder="Price to"
              type="text"
              numeric
              value={priceMax}
              onChange={(v) => setPriceMax(v)}
            />
          </div>
        </div>
        <div className="px-4 pb-3">
          <Button text="Apply" type="secondary" onClick={handleApply} />
        </div>
      </Group>

      {loading && (
        <Group>
          {[1, 2, 3].map((i) => (
            <GroupItem
              key={i}
              text={<SkeletonElement style={{ width: "60%", height: 16 }} />}
              description={<SkeletonElement style={{ width: "40%", height: 12 }} />}
            />
          ))}
        </Group>
      )}

      {!loading && error && (
        <EmptyState
          icon="⚠️"
          title="Loading error"
          description={error}
        />
      )}

      {!loading && !error && (!listings || listings.length === 0) && (
        <EmptyState
          icon="📋"
          title="No listings"
          description="Try adjusting the filters"
        />
      )}

      {!loading && listings && listings.length > 0 && (
        <Group header="Listings">
          {listings.map((item) => (
            <GroupItem
              key={item.id}
              text={`Channel #${item.channel_id}`}
              description={`${item.price_usd != null ? `$${item.price_usd}` : "Price not specified"} · ${item.format}`}
              onClick={() => navigate(`/listings/${item.id}`)}
              chevron
            />
          ))}
        </Group>
      )}

      {!loading && <Pagination page={page} hasMore={hasMore} onPrev={prevPage} onNext={nextPage} />}
    </div>
  );
}
