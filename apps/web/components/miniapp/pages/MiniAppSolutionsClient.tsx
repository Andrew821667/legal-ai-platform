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
    description: "Скорость согласований, контроль рисков, управляемая загрузка юркоманды, SLA и связь с операционными системами.",
    href: ROUTES.forBusiness,
    action: MINIAPP_ACTIONS.openSolutionsForBusiness,
  },
  {
    title: "Сквозная автоматизация",
    description: "CRM, ERP, 1C, ЭДО, Telegram-боты, сайты, Mini App, личные кабинеты и внутренние сервисы вокруг юридического процесса.",
    href: "/services/custom-ai",
    action: MINIAPP_ACTIONS.openSolutionsRoadmap,
  },
  {
    title: "Юридическая помощь",
    description: "Быстро передать юристу договорный, судебный, корпоративный или личный правовой вопрос без регистрации и загрузки документов.",
    href: ROUTES.miniAppLegalHelp,
    action: MINIAPP_ACTIONS.openLegalHelp,
  },
  {
    title: "Формат внедрения",
    description: "Пилот, этапное расширение, разработка недостающих инструментов и сопровождение с фокусом на измеримый результат.",
    href: ROUTES.solutions,
    action: MINIAPP_ACTIONS.openSolutionsRoadmap,
  },
];

export default function MiniAppSolutionsPage() {
  return (
    <section className="space-y-4">
      <MiniAppGuideCard
        title="Как использовать экран"
        description="Выберите ваш контур: юридический процесс, бизнес-связку или разработку недостающего инструмента. К пилоту переходим после проверки гипотезы."
      />

      {blocks.map((block) => (
        <article key={block.title} className="rounded-xl border border-slate-800 bg-slate-800/70 p-4">
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
            className="mt-4"
            variant="secondary"
          >
            Открыть маршрут
          </MiniTrackedLink>
        </article>
      ))}

      <MiniAppCtaFlowCard
        leadStart="web_miniapp_solutions"
        sourceScreen="/miniapp/solutions"
        title="Маршрут решений: Узнать -> Проверить -> Обсудить пилот"
      />
    </section>
  );
}
