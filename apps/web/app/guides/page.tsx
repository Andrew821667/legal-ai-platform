import Link from "next/link";

import { guides } from "@/lib/guidesData";
import { createPageMetadata } from "@/lib/seo";
import HeroBackdrop from "@/components/HeroBackdrop";

export const metadata = createPageMetadata({
  title: "Практические руководства по Legal AI",
  description:
    "Практические материалы AI Verdict по проверке договоров, внедрению ИИ в юридический отдел и безопасности данных.",
  path: "/guides",
});

export default function GuidesPage() {
  return (
    <main className="min-h-screen bg-slate-950 text-slate-100">
      <section className="relative overflow-hidden border-b border-slate-700">
        <HeroBackdrop variant="insights" tone="light" />
        <div className="relative mx-auto max-w-6xl px-4 pb-20 pt-32 sm:px-6 lg:px-8">
          <p className="text-sm font-semibold uppercase tracking-wide text-amber-300">База знаний</p>
          <h1 className="mt-4 max-w-4xl text-4xl font-semibold text-white md:text-5xl">
            Практические руководства по Legal AI
          </h1>
          <p className="mt-5 max-w-3xl text-lg leading-relaxed text-slate-200">
            Без обещаний заменить юриста: разбираем процессы, метрики пилота, контроль качества и требования к данным.
          </p>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-14 sm:px-6 lg:px-8">
        <div className="mt-12 grid gap-6 lg:grid-cols-3">
          {guides.map((guide) => (
            <article key={guide.slug} className="flex h-full flex-col rounded-xl border border-slate-800 bg-slate-900 p-6">
              <p className="text-xs uppercase tracking-wide text-slate-400">{guide.readingTime}</p>
              <h2 className="mt-3 text-xl font-semibold text-white">{guide.title}</h2>
              <p className="mt-4 flex-1 text-sm leading-relaxed text-slate-300">{guide.excerpt}</p>
              <Link href={`/guides/${guide.slug}`} className="mt-6 font-semibold text-amber-400 hover:text-amber-300">
                Читать руководство →
              </Link>
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}
