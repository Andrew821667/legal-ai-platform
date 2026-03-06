"use client";

import { useMemo } from "react";
import { ROUTES } from "@/lib/links";
import MiniAppGuideCard from "@/components/miniapp/MiniAppGuideCard";
import MiniAppCtaFlowCard from "@/components/miniapp/MiniAppCtaFlowCard";
import MiniTrackedLink from "@/components/miniapp/MiniTrackedLink";
import { useMiniAppState } from "@/components/miniapp/MiniAppStateProvider";

const audienceHints = {
  lawyer: "Фокус на договорной и претензионной работе.",
  business: "Фокус на сроках согласования, рисках и SLA.",
  mixed: "Фокус на стыке юридической и бизнес-функции.",
} as const;

const sectionLabel: Record<string, string> = {
  discover: "🧠 Узнать",
  validate: "🧪 Проверить",
  solutions: "🛠 Внедрить",
  profile: "👤 Профиль",
};

export default function MiniAppHomePage() {
  const { state, ready } = useMiniAppState();

  const highlights = useMemo(() => {
    if (state.audience === "lawyer") {
      return [
        "2 сценария ускорения первичной проверки договора",
        "Чек-лист рисков для переговорной версии договора",
        "Шаблон маршрута согласования правок",
      ];
    }

    if (state.audience === "business") {
      return [
        "Как сократить цикл согласования без потери контроля",
        "Матрица эскалации юридических рисков для руководителей",
        "Быстрый запуск пилота с измеримым KPI",
      ];
    }

    return [
      "Новые AI-обновления с практическим юридическим эффектом",
      "2 сценария для ускорения договорного потока",
      "1 готовый шаблон для пилота legal ops",
    ];
  }, [state.audience]);

  const recommendedHref = useMemo(() => {
    if (state.recommendedSection === "validate") {
      return `${ROUTES.contractAI}#demo`;
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
        <ul className="mt-3 space-y-2 text-sm text-slate-300">
          {highlights.map((item) => (
            <li key={item}>• {item}</li>
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
            action="miniapp_home_open_content"
            meta={{ eventType: "nav_click", source: "miniapp_home", screen: "/miniapp" }}
            className="rounded-lg border border-slate-700 px-3 py-2 text-sm font-medium text-slate-200 hover:border-amber-500 hover:text-amber-300 transition-colors"
          >
            Открыть контент
          </MiniTrackedLink>
          <MiniTrackedLink
            href={`${ROUTES.contractAI}#demo`}
            action="miniapp_home_open_contract_ai"
            meta={{ eventType: "nav_click", source: "miniapp_home", screen: "/miniapp" }}
            className="rounded-lg border border-slate-700 px-3 py-2 text-sm font-medium text-slate-200 hover:border-amber-500 hover:text-amber-300 transition-colors"
          >
            Проверить договор
          </MiniTrackedLink>
          <MiniTrackedLink
            href={ROUTES.miniAppSolutions}
            action="miniapp_home_open_solutions"
            meta={{ eventType: "nav_click", source: "miniapp_home", screen: "/miniapp" }}
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
          action="miniapp_home_open_recommended_step"
          meta={{
            eventType: "cta_click",
            source: "miniapp_home",
            screen: "/miniapp",
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
        title="Единый маршрут в mini-app: Узнать -> Проверить -> Внедрить"
      />
    </section>
  );
}
