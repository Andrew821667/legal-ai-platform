"use client";

import { ROUTES } from "@/lib/links";
import MiniAppCtaFlowCard from "@/components/miniapp/MiniAppCtaFlowCard";
import MiniAppGuideCard from "@/components/miniapp/MiniAppGuideCard";
import MiniTrackedLink from "@/components/miniapp/MiniTrackedLink";
import { MINIAPP_ACTIONS, MINIAPP_EVENT_SOURCES, MINIAPP_EVENT_TYPES, MINIAPP_SCREENS } from "@/lib/reader-events";

const blocks = [
  {
    label: "Основное направление",
    title: "Автоматизация юридической функции",
    description: "Договорная работа, legal intake, претензионные процессы, комплаенс, базы знаний и интеграции с действующими системами компании.",
    href: ROUTES.solutions,
    action: MINIAPP_ACTIONS.openSolutionsRoadmap,
  },
  {
    label: "Отдельное направление",
    title: "Юридическая практика",
    description: "Договорные, судебные, корпоративные и личные правовые вопросы принимает профильный юрист без смешения с проектом автоматизации.",
    href: ROUTES.miniAppLegalHelp,
    action: MINIAPP_ACTIONS.openLegalHelp,
  },
  {
    label: "Отдельное направление",
    title: "Инженерная практика",
    description: "Боты, сайты, Mini App, личные кабинеты, внутренние программы, AI-модули и интеграции рассматривает профильная команда разработки.",
    href: ROUTES.engineering,
    action: MINIAPP_ACTIONS.openSolutionsRoadmap,
  },
];

export default function MiniAppSolutionsPage() {
  return (
    <section className="space-y-4">
      <MiniAppGuideCard
        title="Выберите маршрут"
        description="Автоматизацию юридического процесса ведут юристы и инженеры вместе. Отдельную правовую или программную задачу передадим профильной команде."
      />

      {blocks.map((block) => (
        <article key={block.title} className="rounded-xl border border-slate-800 bg-slate-800/70 p-4">
          <p className="text-xs font-semibold uppercase text-amber-300">{block.label}</p>
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
        title="Посмотрите сценарии, проверьте идею и обсудите подходящий формат"
      />
    </section>
  );
}
