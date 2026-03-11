"use client";

import { useEffect, useMemo, useState } from "react";
import { ROUTES, contractAIEntryHref } from "@/lib/links";
import MiniAppGuideCard from "@/components/miniapp/MiniAppGuideCard";
import MiniAppCtaFlowCard from "@/components/miniapp/MiniAppCtaFlowCard";
import MiniTrackedLink from "@/components/miniapp/MiniTrackedLink";
import { useMiniAppState } from "@/components/miniapp/MiniAppStateProvider";
import { MINIAPP_ACTIONS, MINIAPP_EVENT_SOURCES, MINIAPP_EVENT_TYPES, MINIAPP_SCREENS } from "@/lib/reader-events";

const audienceHints = {
  lawyer: "Фокус на договорной и претензионной работе.",
  business: "Фокус на сроках согласования, рисках и SLA.",
  mixed: "Фокус на стыке юридической и бизнес-функции.",
} as const;

type HighlightCard = {
  id: string;
  title: string;
  summary: string;
  rubric: string;
  kind: string;
  postedAt: string;
};

const fallbackHighlights: Record<keyof typeof audienceHints, HighlightCard[]> = {
  lawyer: [
    { id: "fallback-lawyer-1", title: "2 сценария ускорения первичной проверки договора", summary: "", rubric: "", kind: "daily", postedAt: "" },
    { id: "fallback-lawyer-2", title: "Чек-лист рисков для переговорной версии договора", summary: "", rubric: "", kind: "daily", postedAt: "" },
    { id: "fallback-lawyer-3", title: "Шаблон маршрута согласования правок", summary: "", rubric: "", kind: "daily", postedAt: "" },
  ],
  business: [
    { id: "fallback-business-1", title: "Как сократить цикл согласования без потери контроля", summary: "", rubric: "", kind: "daily", postedAt: "" },
    { id: "fallback-business-2", title: "Матрица эскалации юридических рисков для руководителей", summary: "", rubric: "", kind: "daily", postedAt: "" },
    { id: "fallback-business-3", title: "Быстрый запуск пилота с измеримым KPI", summary: "", rubric: "", kind: "daily", postedAt: "" },
  ],
  mixed: [
    { id: "fallback-mixed-1", title: "Новые AI-обновления с практическим юридическим эффектом", summary: "", rubric: "", kind: "daily", postedAt: "" },
    { id: "fallback-mixed-2", title: "2 сценария для ускорения договорного потока", summary: "", rubric: "", kind: "daily", postedAt: "" },
    { id: "fallback-mixed-3", title: "1 готовый шаблон для пилота legal ops", summary: "", rubric: "", kind: "daily", postedAt: "" },
  ],
};

const sectionLabel: Record<string, string> = {
  discover: "🧠 Узнать",
  validate: "🧪 Проверить",
  solutions: "🛠 Обсудить пилот",
  profile: "👤 Профиль",
};

export default function MiniAppHomePage() {
  const { state, ready } = useMiniAppState();
  const [liveHighlights, setLiveHighlights] = useState<HighlightCard[]>([]);

  useEffect(() => {
    if (!ready) {
      return;
    }

    let cancelled = false;
    const fetchHighlights = async () => {
      try {
        const response = await fetch(
          `/api/reader/highlights?audience=${encodeURIComponent(state.audience)}&limit=3`,
          { cache: "no-store" },
        );
        if (!response.ok) {
          throw new Error(`Failed with ${response.status}`);
        }
        const payload = await response.json();
        const rows = Array.isArray(payload?.highlights) ? payload.highlights : [];
        if (!cancelled) {
          setLiveHighlights(
            rows
              .map((row: any) => ({
                id: String(row?.id || ""),
                title: String(row?.title || "").trim(),
                summary: String(row?.summary || "").trim(),
                rubric: String(row?.rubric || "").trim(),
                kind: String(row?.kind || "").trim(),
                postedAt: String(row?.postedAt || "").trim(),
              }))
              .filter((item: HighlightCard) => item.title.length > 0),
          );
        }
      } catch {
        if (!cancelled) {
          setLiveHighlights([]);
        }
      }
    };

    void fetchHighlights();
    return () => {
      cancelled = true;
    };
  }, [ready, state.audience]);

  const highlights = useMemo<HighlightCard[]>(
    () => (liveHighlights.length ? liveHighlights : fallbackHighlights[state.audience]),
    [liveHighlights, state.audience],
  );

  const recommendedHref = useMemo(() => {
    if (state.recommendedSection === "validate") {
      return contractAIEntryHref("demo");
    }
    if (state.recommendedSection === "solutions") {
      return ROUTES.miniAppSolutions;
    }
    if (state.recommendedSection === "profile") {
      return ROUTES.miniAppProfile;
    }
    return ROUTES.miniAppContent;
  }, [state.recommendedSection]);

  return (
    <section className="space-y-4">
      <MiniAppGuideCard
        title="Как использовать экран"
        description="Начните с блока «Для вас», затем переходите в Contract_AI_System или в решения. Последнее действие сохраняется, чтобы вы продолжали с нужного шага."
      />

      <article className="rounded-xl border border-slate-800 bg-slate-900/70 p-4">
        <h2 className="text-base font-semibold text-white">Важное сегодня</h2>
        <ul className="mt-3 space-y-3 text-sm text-slate-300">
          {highlights.map((item) => (
            <li key={item.id}>
              <p>• {item.title}</p>
              {item.summary ? <p className="mt-1 text-xs text-slate-400">{item.summary}</p> : null}
            </li>
          ))}
        </ul>
      </article>

      <article className="rounded-xl border border-slate-800 bg-slate-900/70 p-4">
        <h2 className="text-base font-semibold text-white">Для вас</h2>
        <p className="mt-2 text-sm text-slate-300">
          {ready ? audienceHints[state.audience] : "Подбираем маршрут под ваш профиль..."}
        </p>
        <div className="mt-4 grid grid-cols-1 gap-2">
          <MiniTrackedLink
            href={ROUTES.miniAppContent}
            action={MINIAPP_ACTIONS.openContent}
            meta={{ eventType: MINIAPP_EVENT_TYPES.navClick, source: MINIAPP_EVENT_SOURCES.home, screen: MINIAPP_SCREENS.home }}
            className="rounded-lg border border-slate-700 px-3 py-2 text-sm font-medium text-slate-200 hover:border-amber-500 hover:text-amber-300 transition-colors"
          >
            Открыть контент
          </MiniTrackedLink>
          <MiniTrackedLink
            href={ROUTES.miniAppTools}
            action={MINIAPP_ACTIONS.openMiniAppTools}
            meta={{ eventType: MINIAPP_EVENT_TYPES.navClick, source: MINIAPP_EVENT_SOURCES.home, screen: MINIAPP_SCREENS.home }}
            className="rounded-lg border border-slate-700 px-3 py-2 text-sm font-medium text-slate-200 hover:border-amber-500 hover:text-amber-300 transition-colors"
          >
            Открыть инструменты
          </MiniTrackedLink>
          <MiniTrackedLink
            href={ROUTES.miniAppSolutions}
            action={MINIAPP_ACTIONS.openSolutions}
            meta={{ eventType: MINIAPP_EVENT_TYPES.navClick, source: MINIAPP_EVENT_SOURCES.home, screen: MINIAPP_SCREENS.home }}
            className="rounded-lg border border-slate-700 px-3 py-2 text-sm font-medium text-slate-200 hover:border-amber-500 hover:text-amber-300 transition-colors"
          >
            Сценарии внедрения
          </MiniTrackedLink>
        </div>
      </article>

      <article className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-4">
        <h2 className="text-base font-semibold text-white">Продолжить с места</h2>
        <p className="mt-2 text-sm text-slate-200">
          {state.lastAction
            ? `Последнее действие: ${state.lastAction}.`
            : "Пока нет действий — начните с контента или с проверки договора."}
        </p>
        <p className="mt-2 text-xs text-slate-300">
          Сохранено: {state.savedCount} • Событий за 24ч: {state.recentEvents24h} • Лид-интентов за 30д:{" "}
          {state.leadIntents30d}
        </p>
      </article>

      <article className="rounded-xl border border-sky-500/30 bg-sky-500/10 p-4">
        <h2 className="text-base font-semibold text-white">Рекомендованный следующий шаг</h2>
        <p className="mt-2 text-sm text-slate-200">
          {sectionLabel[state.recommendedSection] || "🧠 Узнать"}
          {state.recommendedReason ? ` — ${state.recommendedReason}` : ""}
        </p>
        <MiniTrackedLink
          href={recommendedHref}
          action={MINIAPP_ACTIONS.openRecommendedStep}
          meta={{
            eventType: MINIAPP_EVENT_TYPES.ctaClick,
            source: MINIAPP_EVENT_SOURCES.home,
            screen: MINIAPP_SCREENS.home,
            payload: { section: state.recommendedSection, screen: state.recommendedScreen },
          }}
          className="mt-3 inline-flex rounded-lg border border-sky-500/60 px-3 py-2 text-sm font-semibold text-sky-200 hover:border-sky-300 transition-colors"
        >
          Открыть рекомендованный шаг
        </MiniTrackedLink>
      </article>

      <MiniAppCtaFlowCard
        leadStart="web_miniapp_home"
        sourceScreen="/miniapp"
        title="Единый маршрут в mini-app: Узнать -> Проверить -> Обсудить пилот"
      />
    </section>
  );
}
