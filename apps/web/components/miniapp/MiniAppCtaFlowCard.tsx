"use client";

import { ROUTES, contractAIEntryHref, contractAIEntryIsExternal, readerBotDeepLink } from "@/lib/links";
import MiniTrackedLink from "@/components/miniapp/MiniTrackedLink";
import { MINIAPP_ACTIONS, MINIAPP_EVENT_SOURCES, MINIAPP_EVENT_TYPES } from "@/lib/reader-events";

type MiniAppCtaFlowCardProps = {
  leadStart?: string;
  sourceScreen: string;
  title?: string;
};

export default function MiniAppCtaFlowCard({
  sourceScreen,
  title = "Маршрут: Узнать -> Проверить -> Обсудить пилот",
}: MiniAppCtaFlowCardProps) {
  const contractAIHref = contractAIEntryHref("demo");
  const contractAIExternal = contractAIEntryIsExternal();
  return (
    <article className="rounded-xl border border-amber-500/35 bg-slate-800/70 p-4">
      <h2 className="text-sm font-semibold text-amber-300">{title}</h2>
      <div className="mt-3 grid grid-cols-1 gap-2">
        <MiniTrackedLink
          href={readerBotDeepLink("discover")}
          action={MINIAPP_ACTIONS.flowDiscover}
          meta={{
            eventType: MINIAPP_EVENT_TYPES.ctaClick,
            source: MINIAPP_EVENT_SOURCES.flow,
            screen: sourceScreen,
            payload: { cta: "discover" },
          }}
          target="_blank"
          rel="noopener noreferrer"
          variant="secondary"
        >
          🧠 Узнать в Reader
        </MiniTrackedLink>

        <MiniTrackedLink
          href={contractAIHref}
          action={MINIAPP_ACTIONS.flowValidate}
          meta={{
            eventType: MINIAPP_EVENT_TYPES.ctaClick,
            source: MINIAPP_EVENT_SOURCES.flow,
            screen: sourceScreen,
            payload: { cta: "validate" },
          }}
          target={contractAIExternal ? "_blank" : undefined}
          rel={contractAIExternal ? "noopener noreferrer" : undefined}
          variant="primary"
        >
          🧪 Проверить в Contract_AI_System
        </MiniTrackedLink>

        <MiniTrackedLink
          href={ROUTES.miniAppLead}
          action={MINIAPP_ACTIONS.flowImplement}
          meta={{
            eventType: MINIAPP_EVENT_TYPES.ctaClick,
            source: MINIAPP_EVENT_SOURCES.flow,
            screen: sourceScreen,
            payload: { cta: "implement" },
          }}
          variant="info"
        >
          🛠 Обсудить пилот
        </MiniTrackedLink>
      </div>
    </article>
  );
}
