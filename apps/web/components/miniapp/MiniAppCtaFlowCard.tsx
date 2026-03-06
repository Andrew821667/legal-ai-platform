"use client";

import { leadBotDeepLink, readerBotDeepLink, ROUTES } from "@/lib/links";
import MiniTrackedLink from "@/components/miniapp/MiniTrackedLink";

type MiniAppCtaFlowCardProps = {
  leadStart: string;
  sourceScreen: string;
  title?: string;
};

export default function MiniAppCtaFlowCard({
  leadStart,
  sourceScreen,
  title = "Маршрут: Узнать -> Проверить -> Внедрить",
}: MiniAppCtaFlowCardProps) {
  return (
    <article className="rounded-xl border border-amber-500/35 bg-slate-900/70 p-4">
      <h2 className="text-sm font-semibold text-amber-300">{title}</h2>
      <div className="mt-3 grid grid-cols-1 gap-2">
        <MiniTrackedLink
          href={readerBotDeepLink("discover")}
          action="miniapp_flow_open_reader_discover"
          meta={{ eventType: "cta_click", source: "miniapp_flow", screen: sourceScreen, payload: { cta: "discover" } }}
          target="_blank"
          rel="noopener noreferrer"
          className="rounded-lg border border-slate-700 px-3 py-2 text-sm font-medium text-slate-200 hover:border-amber-500 hover:text-amber-300 transition-colors"
        >
          🧠 Узнать в Reader
        </MiniTrackedLink>

        <MiniTrackedLink
          href={ROUTES.contractAI}
          action="miniapp_flow_open_contract_ai"
          meta={{ eventType: "cta_click", source: "miniapp_flow", screen: sourceScreen, payload: { cta: "validate" } }}
          className="rounded-lg bg-amber-500 px-3 py-2 text-sm font-semibold text-slate-950 hover:bg-amber-400 transition-colors"
        >
          🧪 Проверить в Contract_AI_System
        </MiniTrackedLink>

        <MiniTrackedLink
          href={leadBotDeepLink(leadStart)}
          action="miniapp_flow_open_lead_bot"
          meta={{ eventType: "cta_click", source: "miniapp_flow", screen: sourceScreen, payload: { cta: "implement" } }}
          target="_blank"
          rel="noopener noreferrer"
          className="rounded-lg border border-sky-500/60 px-3 py-2 text-sm font-medium text-sky-200 hover:border-sky-300 transition-colors"
        >
          🛠 Внедрить через Ассистент Legal AI Pro
        </MiniTrackedLink>
      </div>
    </article>
  );
}
