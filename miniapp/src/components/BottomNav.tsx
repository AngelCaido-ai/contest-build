import { useLocation, useNavigate } from "react-router-dom";
import { Text } from "@telegram-tools/ui-kit";

const tabs = [
  { path: "/listings", label: "Каталог", icon: "📋" },
  { path: "/requests", label: "Заявки", icon: "📝" },
  { path: "/channels", label: "Каналы", icon: "📺" },
  { path: "/deals", label: "Сделки", icon: "🤝" },
];

export function BottomNav() {
  const location = useLocation();
  const navigate = useNavigate();

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-50 flex border-t bg-[var(--tg-theme-bg-color,#fff)] border-[var(--tg-theme-hint-color,#ccc)]">
      {tabs.map((tab) => {
        const active =
          location.pathname === tab.path ||
          location.pathname.startsWith(tab.path + "/");
        return (
          <button
            key={tab.path}
            onClick={() => navigate(tab.path)}
            className="flex flex-1 flex-col items-center gap-0.5 py-2"
          >
            <span className="text-lg">{tab.icon}</span>
            <Text
              type="caption2"
              weight={active ? "bold" : "regular"}
              color={active ? "accent" : "secondary"}
            >
              {tab.label}
            </Text>
          </button>
        );
      })}
    </nav>
  );
}
