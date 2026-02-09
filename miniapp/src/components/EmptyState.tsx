import { Text } from "@telegram-tools/ui-kit";

type EmptyStateProps = {
  icon?: string;
  title: string;
  description?: string;
};

export function EmptyState({ icon = "📭", title, description }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center gap-2 py-12">
      <span className="text-4xl">{icon}</span>
      <Text type="body" weight="medium" color="secondary" align="center">
        {title}
      </Text>
      {description && (
        <Text type="caption1" color="tertiary" align="center">
          {description}
        </Text>
      )}
    </div>
  );
}
