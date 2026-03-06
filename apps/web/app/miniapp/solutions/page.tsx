"use client";

import { ROUTES } from "@/lib/links";
import MiniAppCtaFlowCard from "@/components/miniapp/MiniAppCtaFlowCard";
import MiniAppGuideCard from "@/components/miniapp/MiniAppGuideCard";
import MiniTrackedLink from "@/components/miniapp/MiniTrackedLink";
import { MINIAPP_ACTIONS, MINIAPP_EVENT_SOURCES, MINIAPP_EVENT_TYPES, MINIAPP_SCREENS } from "@/lib/reader-events";

const blocks = [
  {
    title: "Для юристов",
    description: "Договорная работа, претензионные контуры, шаблоны и контроль юридического качества.",
    href: ROUTES.forLawyers,
    action: MINIAPP_ACTIONS.openSolutionsForLawyers,
  },
  {
    title: "Для бизнеса",
    description: "Скорость согласований, контроль рисков, управляемая загрузка юркоманды и SLA.",
    href: ROUTES.forBusiness,
    action: MINIAPP_ACTIONS.openSolutionsForBusiness,
  },
  {
    title: "Формат внедрения",
    description: "Пилот, этапное расширение и сопровождение с фокусом на измеримый результат.",
    href: ROUTES.solutions,
    action: MINIAPP_ACTIONS.openSolutionsRoadmap,
  },
];

export default function MiniAppSolutionsPage() {
  return (
    <section className="space-y-4">
      <MiniAppGuideCard
        title="Как использовать экран"
        description="Выберите ваш контур, откройте соответствующий маршрут и переходите к внедрению только после проверки гипотезы в продукте."
      />

      {blocks.map((block) => (
        <article key={block.title} className="rounded-xl border border-slate-800 bg-slate-900/70 p-4">
          <h2 className="text-base font-semibold text-white">{block.title}</h2>
          <p className="mt-2 text-sm text-slate-300 leading-relaxed">{block.description}</p>
          <MiniTrackedLink
            href={block.href}
            action={block.action}
            meta={{
              eventType: MINIAPP_EVENT_TYPES.solutionOpen,
              source: MINIAPP_EVENT_SOURCES.solutions,
              screen: MINIAPP_SCREENS.solutions,
            }}
            className="mt-4 inline-flex rounded-lg border border-slate-700 px-3 py-2 text-sm font-medium text-slate-200 hover:border-amber-500 hover:text-amber-300 transition-colors"
          >
            Открыть маршрут
          </MiniTrackedLink>
        </article>
      ))}

      <MiniAppCtaFlowCard
        leadStart="web_miniapp_solutions"
        sourceScreen="/miniapp/solutions"
        title="Маршрут решений: Узнать -> Проверить -> Внедрить"
      />
    </section>
  );
}
