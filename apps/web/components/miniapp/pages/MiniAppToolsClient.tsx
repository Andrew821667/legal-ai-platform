"use client";

import { ROUTES, contractAIEntryHref, contractAIEntryIsExternal } from "@/lib/links";
import MiniAppCtaFlowCard from "@/components/miniapp/MiniAppCtaFlowCard";
import MiniAppGuideCard from "@/components/miniapp/MiniAppGuideCard";
import MiniTrackedLink from "@/components/miniapp/MiniTrackedLink";
import { MINIAPP_ACTIONS, MINIAPP_EVENT_SOURCES, MINIAPP_EVENT_TYPES, MINIAPP_SCREENS } from "@/lib/reader-events";

const tools = [
  {
    title: "Проверка договора AI",
    description: "Анализ договора, подсветка рисков и рекомендации по правкам перед согласованием.",
    href: contractAIEntryHref("demo"),
    action: MINIAPP_ACTIONS.openContractAI,
    external: contractAIEntryIsExternal(),
  },
  {
    title: "История анализов",
    description: "Продолжение предыдущих проверок и контроль результата пилота.",
    href: ROUTES.miniAppProfile,
    action: MINIAPP_ACTIONS.openHistory,
    external: false,
  },
  {
    title: "Будущие инструменты",
    description: "Сценарии для претензионной, комплаенса, внутренних legal ops процессов и смежных интеграций.",
    href: ROUTES.solutions,
    action: MINIAPP_ACTIONS.openFutureTools,
    external: false,
  },
  {
    title: "Кастомная разработка",
    description: "Боты, сайты, Mini App, личные кабинеты, внутренние панели и программы, которые закрывают задачу вокруг юридического процесса.",
    href: "/services/custom-ai",
    action: MINIAPP_ACTIONS.openFutureTools,
    external: false,
  },
];

export default function MiniAppToolsPage() {
  return (
    <section className="space-y-4">
      <MiniAppGuideCard
        title="Как использовать экран"
        description="Здесь собраны практические инструменты. Начните с Contract_AI_System, затем возвращайтесь к истории и расширяйте контур внедрения через интеграции или разработку."
      />

      {tools.map((tool) => (
        <article key={tool.title} className="rounded-xl border border-slate-800 bg-slate-800/70 p-4">
          <h2 className="text-base font-semibold text-white">{tool.title}</h2>
          <p className="mt-2 text-sm text-slate-300 leading-relaxed">{tool.description}</p>
          <MiniTrackedLink
            href={tool.href}
            action={tool.action}
            meta={{ eventType: MINIAPP_EVENT_TYPES.toolOpen, source: MINIAPP_EVENT_SOURCES.tools, screen: MINIAPP_SCREENS.tools }}
            target={tool.external ? "_blank" : undefined}
            rel={tool.external ? "noopener noreferrer" : undefined}
            className="mt-4"
            variant="secondary"
          >
            Открыть
          </MiniTrackedLink>
        </article>
      ))}

      <MiniAppCtaFlowCard
        leadStart="web_miniapp_tools"
        sourceScreen="/miniapp/tools"
        title="Маршрут инструментов: Узнать -> Проверить -> Обсудить пилот"
      />
    </section>
  );
}
