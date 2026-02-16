import { useRef } from "react";
import { Text } from "@telegram-tools/ui-kit";
import type { MediaFileId } from "../types";

const TYPE_LABELS: Record<string, string> = {
  photo: "Photo",
  video: "Video",
  animation: "GIF",
  document: "Document",
};

type FileUploadButtonProps = {
  files: MediaFileId[];
  onChange: (files: MediaFileId[]) => void;
  onUpload: (file: File) => void;
  uploading?: boolean;
  accept?: string;
};

export function FileUploadButton({
  files,
  onChange,
  onUpload,
  uploading = false,
  accept = "image/*,video/*,.gif,.pdf,.doc,.docx,.txt",
}: FileUploadButtonProps) {
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0] ?? null;
    if (file) onUpload(file);
    if (inputRef.current) inputRef.current.value = "";
  };

  const handleRemove = (index: number) => {
    onChange(files.filter((_, i) => i !== index));
  };

  return (
    <div className="flex flex-col gap-2">
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        className="hidden"
        onChange={handleFileChange}
      />
      <button
        type="button"
        className="flex items-center gap-2 rounded-xl border border-dashed px-4 py-2.5 text-sm transition-colors"
        style={{
          borderColor: "var(--tg-theme-hint-color, #ccc)",
          color: "var(--tg-theme-link-color, #3b82f6)",
        }}
        onClick={() => inputRef.current?.click()}
        disabled={uploading}
      >
        <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
          <path
            d="M15.75 8.49L9.24 15a4.13 4.13 0 01-5.84-5.84l6.51-6.51a2.75 2.75 0 013.89 3.89l-6.52 6.5a1.38 1.38 0 01-1.94-1.94l6.01-6.01"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
        {uploading ? "Uploading..." : "Attach file"}
      </button>

      {files.length > 0 && (
        <div className="flex flex-col gap-1.5">
          {files.map((item, index) => (
            <div
              key={`${item.type}-${item.file_id}-${index}`}
              className="flex items-center justify-between rounded-lg px-3 py-1.5"
              style={{ backgroundColor: "var(--tg-theme-secondary-bg-color, #2c2c2e)" }}
            >
              <Text type="caption1" color="secondary">
                {TYPE_LABELS[item.type] ?? item.type} &middot; {item.file_id.slice(0, 12)}...
              </Text>
              <button
                type="button"
                className="ml-2 shrink-0 p-0.5"
                style={{ color: "var(--tg-theme-hint-color, #999)" }}
                onClick={() => handleRemove(index)}
              >
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <path
                    d="M10.5 3.5L3.5 10.5M3.5 3.5l7 7"
                    stroke="currentColor"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                  />
                </svg>
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
