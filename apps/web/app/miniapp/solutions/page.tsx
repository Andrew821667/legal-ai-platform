"use client";

import { ROUTES } from "@/lib/links";
import MiniAppGuideCard from "@/components/miniapp/MiniAppGuideCard";
import MiniTrackedLink from "@/components/miniapp/MiniTrackedLink";

const blocks = [
  {
    title: "Для юристов",
    description: "Договорная работа, претензионные контуры, шаблоны и контроль юридического качества.",
    href: ROUTES.forLawyers,
    action: "miniapp_solutions_open_for_lawyers",
  },
  {
    title: "Для бизнеса",
    description: "Скорость согласований, контроль рисков, управляемая загрузка юркоманды и SLA.",
    href: ROUTES.forBusiness,
    action: "miniapp_solutions_open_for_business",
  },
  {
    title: "Формат внедрения",
    description: "Пилот, этапное расширение и сопровождение с фокусом на измеримый результат.",
    href: ROUTES.solutions,
    action: "miniapp_solutions_open_roadmap",
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
            meta={{ eventType: "solution_open", source: "miniapp_solutions", screen: "/miniapp/solutions" }}
            className="mt-4 inline-flex rounded-lg border border-slate-700 px-3 py-2 text-sm font-medium text-slate-200 hover:border-amber-500 hover:text-amber-300 transition-colors"
          >
            Открыть маршрут
          </MiniTrackedLink>
        </article>
      ))}
    </section>
  );
}
