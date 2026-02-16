import { Text } from "@telegram-tools/ui-kit";

export function toLocalInputValue(date: Date): string {
  const pad = (value: number) => String(value).padStart(2, "0");
  const year = date.getFullYear();
  const month = pad(date.getMonth() + 1);
  const day = pad(date.getDate());
  const hours = pad(date.getHours());
  const minutes = pad(date.getMinutes());
  return `${year}-${month}-${day}T${hours}:${minutes}`;
}

export function isoToLocalInput(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return toLocalInputValue(d);
}

export function localInputToIso(value: string): string | null {
  const raw = value.trim();
  if (!raw) return null;
  const date = new Date(raw);
  if (Number.isNaN(date.getTime())) return null;
  return date.toISOString();
}

function formatSelectedDate(value: string): string | null {
  if (!value.trim()) return null;
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

type DateTimePickerFieldProps = {
  value: string;
  onChange: (value: string) => void;
  allowEmpty?: boolean;
};

export function DateTimePickerField({ value, onChange, allowEmpty = true }: DateTimePickerFieldProps) {
  const applyPreset = (nextDate: Date) => {
    onChange(toLocalInputValue(nextDate));
  };

  const now = new Date();
  const tomorrow = new Date(now);
  tomorrow.setDate(now.getDate() + 1);

  const tomorrowAt = (hours: number, minutes: number) => {
    const date = new Date(tomorrow);
    date.setHours(hours, minutes, 0, 0);
    return date;
  };

  const inHours = (hours: number) => {
    const date = new Date(now);
    date.setHours(now.getHours() + hours, now.getMinutes(), 0, 0);
    return date;
  };

  const selectedLabel = formatSelectedDate(value);

  return (
    <div className="flex flex-col gap-2">
      <input
        type="datetime-local"
        className="w-full text-sm"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          className="rounded-lg border border-[var(--tg-theme-hint-color,#ccc)] px-3 py-1.5 text-xs"
          onClick={() => applyPreset(inHours(1))}
        >
          In 1h
        </button>
        <button
          type="button"
          className="rounded-lg border border-[var(--tg-theme-hint-color,#ccc)] px-3 py-1.5 text-xs"
          onClick={() => applyPreset(inHours(3))}
        >
          In 3h
        </button>
        <button
          type="button"
          className="rounded-lg border border-[var(--tg-theme-hint-color,#ccc)] px-3 py-1.5 text-xs"
          onClick={() => applyPreset(inHours(6))}
        >
          In 6h
        </button>
        <button
          type="button"
          className="rounded-lg border border-[var(--tg-theme-hint-color,#ccc)] px-3 py-1.5 text-xs"
          onClick={() => applyPreset(tomorrowAt(12, 0))}
        >
          Tomorrow 12:00
        </button>
        <button
          type="button"
          className="rounded-lg border border-[var(--tg-theme-hint-color,#ccc)] px-3 py-1.5 text-xs"
          onClick={() => applyPreset(tomorrowAt(18, 0))}
        >
          Tomorrow 18:00
        </button>
        {allowEmpty && (
          <button
            type="button"
            className="rounded-lg border border-[var(--tg-theme-hint-color,#ccc)] px-3 py-1.5 text-xs"
            onClick={() => onChange("")}
          >
            Clear
          </button>
        )}
      </div>
    </div>
  );
}
