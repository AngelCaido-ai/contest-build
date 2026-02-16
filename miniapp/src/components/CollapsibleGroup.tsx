import { useState, useRef, useEffect, type ReactNode } from "react";
import { Text } from "@telegram-tools/ui-kit";

type CollapsibleGroupProps = {
  header: string;
  defaultOpen?: boolean;
  children: ReactNode;
};

export function CollapsibleGroup({ header, defaultOpen = false, children }: CollapsibleGroupProps) {
  const [open, setOpen] = useState(defaultOpen);
  const contentRef = useRef<HTMLDivElement>(null);
  const [maxHeight, setMaxHeight] = useState<string>(defaultOpen ? "none" : "0px");

  useEffect(() => {
    if (!contentRef.current) return;
    if (open) {
      setMaxHeight(`${contentRef.current.scrollHeight}px`);
      const timer = setTimeout(() => setMaxHeight("none"), 300);
      return () => clearTimeout(timer);
    } else {
      setMaxHeight(`${contentRef.current.scrollHeight}px`);
      requestAnimationFrame(() => {
        requestAnimationFrame(() => setMaxHeight("0px"));
      });
    }
  }, [open]);

  return (
    <div className="flex flex-col">
      <button
        type="button"
        className="flex w-full items-center justify-between px-4 py-2.5"
        onClick={() => setOpen((prev) => !prev)}
      >
        <Text type="caption1" color="secondary">
          {header}
        </Text>
        <svg
          width="16"
          height="16"
          viewBox="0 0 16 16"
          fill="none"
          className="shrink-0 transition-transform duration-200"
          style={{
            transform: open ? "rotate(180deg)" : "rotate(0deg)",
            color: "var(--tg-theme-hint-color, #999)",
          }}
        >
          <path
            d="M4 6l4 4 4-4"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </button>
      <div
        ref={contentRef}
        className="overflow-hidden transition-[max-height] duration-300 ease-in-out"
        style={{ maxHeight }}
      >
        {children}
      </div>
    </div>
  );
}
