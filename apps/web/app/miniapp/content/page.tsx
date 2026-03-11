"use client";

import { useEffect, useMemo, useState } from "react";

import MiniAppCtaFlowCard from "@/components/miniapp/MiniAppCtaFlowCard";
import MiniAppGuideCard from "@/components/miniapp/MiniAppGuideCard";
import { useMiniAppState } from "@/components/miniapp/MiniAppStateProvider";
import MiniTrackedLink from "@/components/miniapp/MiniTrackedLink";
import { MINIAPP_ACTIONS, MINIAPP_EVENT_SOURCES, MINIAPP_EVENT_TYPES, MINIAPP_SCREENS } from "@/lib/reader-events";
import { ROUTES } from "@/lib/links";

type FeedItem = {
  id: string;
  title: string;
  summary: string;
  topic: string;
  href: string;
};

const topics = [
  "Все",
  "AI в договорах",
  "AI law",
  "Legal ops",
  "Общий AI",
] as const;

const fallbackFeed: FeedItem[] = [
  {
    id: "contracts_cycle_control",
    title: "Как сократить цикл согласования договора без потери юридического контроля",
    summary: "Разбираем конкретный процесс: вход документа, ревью, эскалации и финальный SLA.",
    topic: "AI в договорах",
    href: ROUTES.contentCases,
  },
  {
    id: "tools_practical_legal",
    title: "Новые AI-инструменты: что реально применимо в юрдепартаменте",
    summary: "Сравниваем инструменты по скорости запуска, точности и стоимости сопровождения.",
    topic: "Общий AI",
    href: `${ROUTES.contentCases}#practical`,
  },
  {
    id: "regulation_ai_law",
    title: "Регуляторные тренды AI law и их влияние на договорные оговорки",
    summary: "Какие изменения учитывать в формулировках ответственности, privacy и governance.",
    topic: "AI law",
    href: ROUTES.contentCases,
  },
  {
    id: "legal_ops_overload",
    title: "Практика legal ops: где автоматизация снимает перегруз команды",
    summary: "Карта зон рутинной нагрузки и приоритетов внедрения без просадки качества.",
    topic: "Legal ops",
    href: `${ROUTES.contentCases}#practical`,
  },
];

function classifyTopic(title: string, rubric: string): (typeof topics)[number] {
  const haystack = `${title} ${rubric}`.toLowerCase();
  if (haystack.includes("договор") || haystack.includes("contract") || haystack.includes("redline")) {
    return "AI в договорах";
  }
  if (
    haystack.includes("law")
    || haystack.includes("регули")
    || haystack.includes("privacy")
    || haystack.includes("compliance")
    || haystack.includes("пдн")
  ) {
    return "AI law";
  }
  if (
    haystack.includes("ops")
    || haystack.includes("процесс")
    || haystack.includes("внедрен")
    || haystack.includes("sla")
  ) {
    return "Legal ops";
  }
  return "Общий AI";
}

export default function MiniAppContentPage() {
  const { ready, state } = useMiniAppState();
  const [activeTopic, setActiveTopic] = useState<(typeof topics)[number]>("Все");
  const [query, setQuery] = useState("");
  const [feed, setFeed] = useState<FeedItem[]>(fallbackFeed);

  useEffect(() => {
    if (!ready) {
      return;
    }

    let cancelled = false;
    const fetchFeed = async () => {
      try {
        const response = await fetch(
          `/api/reader/highlights?audience=${encodeURIComponent(state.audience)}&limit=12`,
          { cache: "no-store" },
        );
        if (!response.ok) {
          throw new Error(`Failed with ${response.status}`);
        }
        const payload = await response.json();
        const rows = Array.isArray(payload?.highlights) ? payload.highlights : [];
        const mapped: FeedItem[] = rows
          .map((row: any) => {
            const title = String(row?.title || "").trim();
            if (!title) {
              return null;
            }
            const summary = String(row?.summary || "").trim();
            const rubric = String(row?.rubric || "").trim();
            return {
              id: String(row?.id || ""),
              title,
              summary,
              topic: classifyTopic(title, rubric),
              href: ROUTES.contentCases,
            } satisfies FeedItem;
          })
          .filter((item: FeedItem | null): item is FeedItem => item !== null);

        if (!cancelled && mapped.length > 0) {
          setFeed(mapped);
        }
      } catch {
        if (!cancelled) {
          setFeed(fallbackFeed);
        }
      }
    };

    void fetchFeed();
    return () => {
      cancelled = true;
    };
  }, [ready, state.audience]);

  const filteredFeed = useMemo(() => {
    return feed.filter((item) => {
      const topicMatch = activeTopic === "Все" || item.topic === activeTopic;
      const queryMatch = query.trim().length === 0 || item.title.toLowerCase().includes(query.toLowerCase().trim());
      return topicMatch && queryMatch;
    });
  }, [activeTopic, feed, query]);

  return (
    <section className="space-y-4">
      <MiniAppGuideCard
        title="Как использовать экран"
        description="Здесь — живой поток материалов под ваш профиль. Используйте фильтр тем и поиск, чтобы быстро выйти на нужный материал."
      />

      <article className="rounded-xl border border-slate-800 bg-slate-900/70 p-4">
        <h2 className="text-base font-semibold text-white">Фильтры</h2>
        <div className="mt-3 flex flex-wrap gap-2">
          {topics.map((topic) => {
            const active = topic === activeTopic;
            return (
              <button
                key={topic}
                type="button"
                className={`rounded-full border px-3 py-1 text-xs transition-colors ${
                  active
                    ? "border-amber-500 bg-amber-500/15 text-amber-300"
                    : "border-slate-700 text-slate-300 hover:border-slate-500"
                }`}
                onClick={() => setActiveTopic(topic)}
              >
                {topic}
              </button>
            );
          })}
        </div>

        <label className="mt-3 block">
          <span className="sr-only">Поиск по материалам</span>
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Поиск по материалам"
            className="w-full rounded-lg border border-slate-700 bg-slate-950/70 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 outline-none focus:border-amber-500"
          />
        </label>
      </article>

      <article className="rounded-xl border border-slate-800 bg-slate-900/70 p-4">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-base font-semibold text-white">Лента</h2>
          <span className="text-xs text-slate-400">{filteredFeed.length} материалов</span>
        </div>

        <div className="mt-3 space-y-3">
          {filteredFeed.map((item) => (
            <MiniTrackedLink
              key={item.id}
              href={item.href}
              action={MINIAPP_ACTIONS.openContentItem}
              meta={{
                eventType: MINIAPP_EVENT_TYPES.contentOpen,
                source: MINIAPP_EVENT_SOURCES.content,
                screen: MINIAPP_SCREENS.content,
                payload: { topic: item.topic, item_id: item.id },
              }}
              className="block rounded-lg border border-slate-800 bg-slate-950/70 px-3 py-3 text-sm text-slate-200 hover:border-amber-500 hover:text-amber-300 transition-colors"
            >
              <span className="block text-xs text-slate-500">{item.topic}</span>
              <span className="mt-1 block">{item.title}</span>
              {item.summary ? (
                <span className="mt-2 block text-xs leading-relaxed text-slate-400">{item.summary}</span>
              ) : null}
            </MiniTrackedLink>
          ))}

          {filteredFeed.length === 0 && (
            <p className="rounded-lg border border-slate-800 bg-slate-950/70 px-3 py-3 text-sm text-slate-400">
              По текущему фильтру ничего не найдено. Снимите фильтр или измените запрос.
            </p>
          )}
        </div>
      </article>

      <MiniAppCtaFlowCard
        leadStart="web_miniapp_content"
        sourceScreen="/miniapp/content"
        title="Следующий шаг по контенту: Узнать -> Проверить -> Обсудить пилот"
      />
    </section>
  );
}
