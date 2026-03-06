"use client";

import { useMemo, useState } from "react";
import { ROUTES } from "@/lib/links";
import MiniAppGuideCard from "@/components/miniapp/MiniAppGuideCard";
import MiniTrackedLink from "@/components/miniapp/MiniTrackedLink";

type FeedItem = {
  title: string;
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

const feed: FeedItem[] = [
  {
    title: "Как сократить цикл согласования договора без потери юридического контроля",
    topic: "AI в договорах",
    href: ROUTES.contentCases,
  },
  {
    title: "Новые AI-инструменты: что реально применимо в юрдепартаменте",
    topic: "Общий AI",
    href: `${ROUTES.contentCases}#practical`,
  },
  {
    title: "Регуляторные тренды AI law и их влияние на договорные оговорки",
    topic: "AI law",
    href: ROUTES.contentCases,
  },
  {
    title: "Практика legal ops: где автоматизация снимает перегруз команды",
    topic: "Legal ops",
    href: `${ROUTES.contentCases}#practical`,
  },
];

export default function MiniAppContentPage() {
  const [activeTopic, setActiveTopic] = useState<(typeof topics)[number]>("Все");
  const [query, setQuery] = useState("");

  const filteredFeed = useMemo(() => {
    return feed.filter((item) => {
      const topicMatch = activeTopic === "Все" || item.topic === activeTopic;
      const queryMatch = query.trim().length === 0 || item.title.toLowerCase().includes(query.toLowerCase().trim());
      return topicMatch && queryMatch;
    });
  }, [activeTopic, query]);

  return (
    <section className="space-y-4">
      <MiniAppGuideCard
        title="Как использовать экран"
        description="Выберите тематику, при необходимости добавьте поиск по заголовкам и откройте релевантный материал."
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
              key={item.title}
              href={item.href}
              action={`miniapp_content_open:${item.title}`}
              meta={{
                eventType: "content_open",
                source: "miniapp_content",
                screen: "/miniapp/content",
                payload: { topic: item.topic },
              }}
              className="block rounded-lg border border-slate-800 bg-slate-950/70 px-3 py-3 text-sm text-slate-200 hover:border-amber-500 hover:text-amber-300 transition-colors"
            >
              <span className="block text-xs text-slate-500">{item.topic}</span>
              <span className="mt-1 block">{item.title}</span>
            </MiniTrackedLink>
          ))}

          {filteredFeed.length === 0 && (
            <p className="rounded-lg border border-slate-800 bg-slate-950/70 px-3 py-3 text-sm text-slate-400">
              По текущему фильтру ничего не найдено. Снимите фильтр или измените запрос.
            </p>
          )}
        </div>
      </article>

      <MiniTrackedLink
        href={ROUTES.contractAI}
        action="miniapp_content_open_contract_ai"
        meta={{ eventType: "nav_click", source: "miniapp_content", screen: "/miniapp/content" }}
        className="inline-flex rounded-lg border border-sky-500/60 px-4 py-2 text-sm font-semibold text-sky-200 hover:border-sky-300 transition-colors"
      >
        Перейти к проверке договора
      </MiniTrackedLink>
    </section>
  );
}
