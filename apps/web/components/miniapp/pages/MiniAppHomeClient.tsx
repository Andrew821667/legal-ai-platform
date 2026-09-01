"use client";

import { useEffect, useMemo, useState } from "react";
import { ROUTES, contractAIEntryHref, leadBotDeepLink } from "@/lib/links";
import MiniAppGuideCard from "@/components/miniapp/MiniAppGuideCard";
import MiniAppCtaFlowCard from "@/components/miniapp/MiniAppCtaFlowCard";
import MiniTrackedLink from "@/components/miniapp/MiniTrackedLink";
import PlatformMap from "@/components/PlatformMap";
import { useMiniAppState } from "@/components/miniapp/MiniAppStateProvider";
import { MINIAPP_ACTIONS, MINIAPP_EVENT_SOURCES, MINIAPP_EVENT_TYPES, MINIAPP_SCREENS } from "@/lib/reader-events";

const audienceHints = {
  lawyer: "Фокус на договорной и претензионной работе.",
  business: "Фокус на сроках согласования, рисках, SLA и связке с операционными системами.",
  mixed: "Фокус на процессе целиком: юридические правила, данные и интеграции.",
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

const quickActions = [
  {
    title: "Проверить договор",
    description: "Открыть Contract AI и быстро проверить документ.",
    href: contractAIEntryHref("demo"),
    action: MINIAPP_ACTIONS.openContractAI,
    variant: "primary" as const,
    external: true,
  },
  {
    title: "Автоматизировать юрфункцию",
    description: "Описать legal-процесс, AI-сценарий или интеграцию с системами компании.",
    href: ROUTES.miniAppLead,
    action: MINIAPP_ACTIONS.openAssistant,
    variant: "info" as const,
    external: false,
  },
  {
    title: "Юридическая практика",
    description: "Кратко описать правовую ситуацию и передать ее профильному юристу.",
    href: ROUTES.miniAppLegalHelp,
    action: MINIAPP_ACTIONS.openLegalHelp,
    variant: "info" as const,
    external: false,
  },
  {
    title: "Инженерная практика",
    description: "Обсудить разработку: бот, сайт, Mini App, сервис, AI-модуль или интеграцию.",
    href: ROUTES.miniAppLead,
    action: MINIAPP_ACTIONS.openAssistant,
    variant: "secondary" as const,
    external: false,
  },
  {
    title: "Описать задачу в чат",
    description: "Передать свободное описание ассистенту без формы.",
    href: leadBotDeepLink("miniapp_home_task"),
    action: MINIAPP_ACTIONS.openAssistant,
    variant: "secondary" as const,
    external: true,
  },
  {
    title: "Выбрать сценарий",
    description: "Посмотреть типовые маршруты автоматизации.",
    href: ROUTES.miniAppSolutions,
    action: MINIAPP_ACTIONS.openSolutions,
    variant: "secondary" as const,
    external: false,
  },
];

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
        title="С чего хотите начать?"
        description="Можно проверить договор, описать юридическую задачу или обсудить автоматизацию и разработку."
      />

      <article className="rounded-xl border border-slate-800 bg-slate-800/70 p-4">
        <h2 className="text-base font-semibold text-white">Что сделать сейчас</h2>
        <div className="mt-4 grid grid-cols-1 gap-3">
          {quickActions.map((action) => (
            <div key={action.title} className="rounded-lg border border-slate-700 bg-slate-900/70 p-3">
              <p className="text-sm font-semibold text-white">{action.title}</p>
              <p className="mt-1 text-xs text-slate-400">{action.description}</p>
              <MiniTrackedLink
                href={action.href}
                action={action.action}
                meta={{ eventType: MINIAPP_EVENT_TYPES.ctaClick, source: MINIAPP_EVENT_SOURCES.home, screen: MINIAPP_SCREENS.home }}
                target={action.external ? "_blank" : undefined}
                rel={action.external ? "noopener noreferrer" : undefined}
                className="mt-3"
                variant={action.variant}
              >
                Открыть
              </MiniTrackedLink>
            </div>
          ))}
        </div>
      </article>

      <article className="rounded-xl border border-slate-800 bg-slate-800/70 p-4">
        <h2 className="text-base font-semibold text-white">Маршрут под вашу задачу</h2>
        <p className="mt-2 text-sm text-slate-300">
          {ready ? audienceHints[state.audience] : "Подбираем маршрут под ваш профиль..."}
        </p>
        <div className="mt-4 grid grid-cols-1 gap-2">
          <MiniTrackedLink
            href={ROUTES.miniAppContent}
            action={MINIAPP_ACTIONS.openContent}
            meta={{ eventType: MINIAPP_EVENT_TYPES.navClick, source: MINIAPP_EVENT_SOURCES.home, screen: MINIAPP_SCREENS.home }}
            variant="secondary"
          >
            Открыть контент
          </MiniTrackedLink>
          <MiniTrackedLink
            href={ROUTES.miniAppTools}
            action={MINIAPP_ACTIONS.openMiniAppTools}
            meta={{ eventType: MINIAPP_EVENT_TYPES.navClick, source: MINIAPP_EVENT_SOURCES.home, screen: MINIAPP_SCREENS.home }}
            variant="secondary"
          >
            Открыть инструменты
          </MiniTrackedLink>
          <MiniTrackedLink
            href={ROUTES.miniAppSolutions}
            action={MINIAPP_ACTIONS.openSolutions}
            meta={{ eventType: MINIAPP_EVENT_TYPES.navClick, source: MINIAPP_EVENT_SOURCES.home, screen: MINIAPP_SCREENS.home }}
            variant="secondary"
          >
            Сценарии внедрения
          </MiniTrackedLink>
          <MiniTrackedLink
            href={ROUTES.miniAppLegalHelp}
            action={MINIAPP_ACTIONS.openLegalHelp}
            meta={{ eventType: MINIAPP_EVENT_TYPES.navClick, source: MINIAPP_EVENT_SOURCES.home, screen: MINIAPP_SCREENS.home }}
            variant="info"
          >
            Юридическая практика
          </MiniTrackedLink>
          <MiniTrackedLink
            href={ROUTES.engineering}
            action={MINIAPP_ACTIONS.openSolutions}
            meta={{ eventType: MINIAPP_EVENT_TYPES.navClick, source: MINIAPP_EVENT_SOURCES.home, screen: MINIAPP_SCREENS.home }}
            variant="secondary"
          >
            Инженерная практика
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

      <article className="rounded-xl border border-slate-800 bg-slate-800/70 p-4">
        <h2 className="text-base font-semibold text-white">Сигналы и материалы</h2>
        <ul className="mt-3 space-y-3 text-sm text-slate-300">
          {highlights.map((item) => (
            <li key={item.id}>
              <p>• {item.title}</p>
              {item.summary ? <p className="mt-1 text-xs text-slate-400">{item.summary}</p> : null}
            </li>
          ))}
        </ul>
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
          className="mt-3"
          variant="info"
        >
          Открыть рекомендованный шаг
        </MiniTrackedLink>
      </article>

      <MiniAppCtaFlowCard
        leadStart="web_miniapp_home"
        sourceScreen="/miniapp"
        title="Выберите материал, проверьте идею и переходите к обсуждению, когда будете готовы"
      />

      <PlatformMap variant="compact" highlightId="miniapp" />
    </section>
  );
}
