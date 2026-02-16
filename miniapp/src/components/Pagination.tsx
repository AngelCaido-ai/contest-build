import { Button, Text } from "@telegram-tools/ui-kit";

type PaginationProps = {
  page: number;
  hasMore: boolean;
  onPrev: () => void;
  onNext: () => void;
};

export function Pagination({ page, hasMore, onPrev, onNext }: PaginationProps) {
  if (page === 0 && !hasMore) return null;

  return (
    <div className="flex items-center justify-center gap-3 py-2">
      {page > 0 && (
        <Button text="Previous" type="secondary" onClick={onPrev} />
      )}
      <Text type="caption1" color="secondary">
        Page {page + 1}
      </Text>
      {hasMore && (
        <Button text="Next" type="secondary" onClick={onNext} />
      )}
    </div>
  );
}
