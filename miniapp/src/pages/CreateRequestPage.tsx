import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button, Group, Input, Text, useToast } from "@telegram-tools/ui-kit";
import { apiFetch } from "../api/client";
import { useBackButton } from "../hooks/useBackButton";

export function CreateRequestPage() {
  useBackButton();
  const navigate = useNavigate();
  const { showToast } = useToast();
  const [budget, setBudget] = useState("");
  const [niche, setNiche] = useState("");
  const [languages, setLanguages] = useState("");
  const [minSubs, setMinSubs] = useState("");
  const [minViews, setMinViews] = useState("");
  const [dates, setDates] = useState("");
  const [brief, setBrief] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const submit = async () => {
    let datesValue: Record<string, unknown> | null = null;
    if (dates.trim()) {
      try {
        datesValue = JSON.parse(dates);
      } catch {
        showToast("Поле dates должно быть JSON", { type: "error" });
        return;
      }
    }
    const payload = {
      budget: budget.trim() ? Number(budget) : null,
      niche: niche.trim() || null,
      languages: languages
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean),
      min_subs: minSubs.trim() ? Number(minSubs) : null,
      min_views: minViews.trim() ? Number(minViews) : null,
      dates: datesValue,
      brief: brief.trim() || null,
    };
    if (
      (budget.trim() && Number.isNaN(payload.budget as number)) ||
      (minSubs.trim() && Number.isNaN(payload.min_subs as number)) ||
      (minViews.trim() && Number.isNaN(payload.min_views as number))
    ) {
      showToast("Числовые поля заполнены неверно", { type: "error" });
      return;
    }
    setSubmitting(true);
    try {
      await apiFetch("/requests", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      showToast("Заявка создана", { type: "success" });
      navigate("/requests");
    } catch (e) {
      showToast(e instanceof Error ? e.message : "Ошибка", { type: "error" });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <Text type="title2" weight="bold">
        Создать заявку
      </Text>

      <Group header="Параметры">
        <div className="flex flex-col gap-3 px-4 py-3">
          <Input
            placeholder="Бюджет USD"
            type="text"
            value={budget}
            onChange={(v) => setBudget(v)}
            numeric
          />
          <Input
            placeholder="Ниша"
            type="text"
            value={niche}
            onChange={(v) => setNiche(v)}
          />
          <Input
            placeholder="Языки через запятую"
            type="text"
            value={languages}
            onChange={(v) => setLanguages(v)}
          />
          <Input
            placeholder="Минимум подписчиков"
            type="text"
            value={minSubs}
            onChange={(v) => setMinSubs(v)}
            numeric
          />
          <Input
            placeholder="Минимум просмотров"
            type="text"
            value={minViews}
            onChange={(v) => setMinViews(v)}
            numeric
          />
          <textarea
            className="w-full rounded-xl border border-[var(--tg-theme-hint-color,#ccc)] bg-transparent px-3 py-2 text-sm"
            rows={3}
            placeholder='dates JSON, например {"from":"2026-02-10","to":"2026-02-20"}'
            value={dates}
            onChange={(e) => setDates(e.target.value)}
          />
          <textarea
            className="w-full rounded-xl border border-[var(--tg-theme-hint-color,#ccc)] bg-transparent px-3 py-2 text-sm"
            rows={4}
            placeholder="Бриф"
            value={brief}
            onChange={(e) => setBrief(e.target.value)}
          />
        </div>
      </Group>

      <div className="flex flex-col gap-2">
        <Button text="Создать" type="primary" loading={submitting} onClick={submit} />
        <Button text="Назад" type="secondary" onClick={() => navigate(-1)} />
      </div>
    </div>
  );
}
