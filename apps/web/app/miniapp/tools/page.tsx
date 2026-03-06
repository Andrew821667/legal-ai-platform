"use client";

import { ROUTES } from "@/lib/links";
import MiniAppCtaFlowCard from "@/components/miniapp/MiniAppCtaFlowCard";
import MiniAppGuideCard from "@/components/miniapp/MiniAppGuideCard";
import MiniTrackedLink from "@/components/miniapp/MiniTrackedLink";

const tools = [
  {
    title: "Contract_AI_System",
    description: "Анализ договора, подсветка рисков, рекомендации по правкам и подготовке согласования.",
    href: ROUTES.contractAI,
    action: "miniapp_tools_open_contract_ai",
  },
  {
    title: "История анализов",
    description: "Продолжение предыдущих проверок и контроль результата пилота.",
    href: ROUTES.miniAppProfile,
    action: "miniapp_tools_open_history",
  },
  {
    title: "Будущие инструменты",
    description: "Сценарии для претензионной, комплаенса и внутренних legal ops процессов.",
    href: ROUTES.solutions,
    action: "miniapp_tools_open_future_tools",
  },
];

export default function MiniAppToolsPage() {
  return (
    <section className="space-y-4">
      <MiniAppGuideCard
        title="Как использовать экран"
        description="Здесь собраны практические инструменты. Начните с Contract_AI_System, затем возвращайтесь к истории и расширяйте контур внедрения."
      />

      {tools.map((tool) => (
        <article key={tool.title} className="rounded-xl border border-slate-800 bg-slate-900/70 p-4">
          <h2 className="text-base font-semibold text-white">{tool.title}</h2>
          <p className="mt-2 text-sm text-slate-300 leading-relaxed">{tool.description}</p>
          <MiniTrackedLink
            href={tool.href}
            action={tool.action}
            meta={{ eventType: "tool_open", source: "miniapp_tools", screen: "/miniapp/tools" }}
            className="mt-4 inline-flex rounded-lg border border-slate-700 px-3 py-2 text-sm font-medium text-slate-200 hover:border-amber-500 hover:text-amber-300 transition-colors"
          >
            Открыть
          </MiniTrackedLink>
        </article>
      ))}

      <MiniAppCtaFlowCard
        leadStart="web_miniapp_tools"
        sourceScreen="/miniapp/tools"
        title="Маршрут инструментов: Узнать -> Проверить -> Внедрить"
      />
    </section>
  );
}
