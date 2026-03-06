import Link from "next/link";
import { ROUTES } from "@/lib/links";

const topics = [
  "AI в договорной работе",
  "Регуляторика и AI law",
  "Практика внедрения legal ops",
  "Инструменты генеративного AI",
];

const feed = [
  {
    title: "Как сократить цикл согласования договора без потери юридического контроля",
    href: ROUTES.contentCases,
  },
  {
    title: "Новые AI-инструменты: что реально применимо в юрдепартаменте",
    href: `${ROUTES.contentCases}#practical`,
  },
  {
    title: "Где проходит граница между автоматизацией и юридической экспертизой",
    href: ROUTES.contentCases,
  },
];

export default function MiniAppContentPage() {
  return (
    <section className="space-y-4">
      <article className="rounded-xl border border-slate-800 bg-slate-900/70 p-4">
        <h2 className="text-base font-semibold text-white">Тематики</h2>
        <div className="mt-3 flex flex-wrap gap-2">
          {topics.map((topic) => (
            <span key={topic} className="rounded-full border border-slate-700 px-3 py-1 text-xs text-slate-300">
              {topic}
            </span>
          ))}
        </div>
      </article>

      <article className="rounded-xl border border-slate-800 bg-slate-900/70 p-4">
        <h2 className="text-base font-semibold text-white">Лента</h2>
        <div className="mt-3 space-y-3">
          {feed.map((item) => (
            <Link
              key={item.title}
              href={item.href}
              className="block rounded-lg border border-slate-800 bg-slate-950/70 px-3 py-3 text-sm text-slate-200 hover:border-amber-500 hover:text-amber-300 transition-colors"
            >
              {item.title}
            </Link>
          ))}
        </div>
      </article>
    </section>
  );
}
