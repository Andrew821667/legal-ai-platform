import Link from "next/link";

import { guides } from "@/lib/guidesData";
import { createPageMetadata } from "@/lib/seo";
import HeroBackdrop from "@/components/HeroBackdrop";

export const metadata = createPageMetadata({
  title: "Legal AI и ИИ для юристов: практические руководства",
  description:
    "Материалы об ИИ в юридической сфере: выбор нейросети для юриста, юридические документы, договоры, внедрение Legal AI и безопасность данных.",
  path: "/guides",
  keywords: ["Legal AI", "ИИ для юристов", "нейросеть для юриста", "ИИ для юридических документов"],
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
            Без обещаний заменить юриста: разбираем выбор инструмента, процессы, метрики пилота, контроль качества и требования к данным.
          </p>
          <Link href="/legal-ai" className="mt-6 inline-flex font-semibold text-slate-700 underline decoration-amber-600 underline-offset-4 hover:text-amber-800">
            Начать с обзора ИИ в юридической сфере →
          </Link>
        </div>
      </section>

      <section className="border-b border-slate-700 bg-slate-900/70">
        <div className="mx-auto grid max-w-6xl gap-5 px-4 py-9 sm:px-6 md:grid-cols-[1fr_auto] md:items-center lg:px-8">
          <div>
            <p className="text-sm font-semibold uppercase text-sky-300">Новое в AI law</p>
            <h2 className="mt-2 text-2xl font-semibold text-white">
              Комментарии новых норм об искусственном интеллекте
            </h2>
            <p className="mt-3 max-w-3xl leading-7 text-slate-300">
              Отдельный раздел с датами вступления в силу, официальными источниками и
              практическими действиями для бизнеса.
            </p>
          </div>
          <Link
            href="/ai-law"
            className="inline-flex items-center justify-center rounded-lg border border-sky-400 px-5 py-3 font-semibold text-sky-200 hover:bg-sky-400/10"
          >
            Открыть комментарии →
          </Link>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-14 sm:px-6 lg:px-8">
        <div className="mt-12 grid gap-6 md:grid-cols-2 xl:grid-cols-4">
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
