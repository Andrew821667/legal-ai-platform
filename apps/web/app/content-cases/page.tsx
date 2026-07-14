import type { Metadata } from "next";
import Link from "next/link";
import { ROUTES } from "@/lib/links";
import { guides } from "@/lib/guidesData";
import { createPageMetadata } from "@/lib/seo";
import CtaFrameworkPanel from "@/components/CtaFrameworkPanel";
import HeroBackdrop from "@/components/HeroBackdrop";

export const metadata: Metadata = createPageMetadata({
  title: "Практические сценарии Legal AI",
  description:
    "Практические сценарии и руководства по автоматизации юридической функции, внедрению AI и управлению рисками без вымышленных кейсов.",
  path: "/content-cases",
  index: false,
});

const caseBlocks = [
  {
    title: "Сценарии внедрения",
    description: "Типовые процессы, метрики пилота и ограничения, которые стоит проверить на данных вашей команды.",
  },
  {
    title: "Экспертные обзоры",
    description: "Разборы новых AI-инструментов и правовых изменений через призму практического применения.",
  },
  {
    title: "Методология",
    description: "Подход AI Verdict к запуску пилота, контролю рисков и масштабированию решений.",
  },
];

const conversionFlow = [
  {
    title: "1. Узнать",
    description: "Получить прикладной контекст из обзоров и разборов, понять где именно есть точка эффекта.",
  },
  {
    title: "2. Проверить",
    description: "Протестировать гипотезу в Contract_AI_System на собственных документах и сценариях.",
  },
  {
    title: "3. Запустить пилот",
    description: "Запустить пилот и поэтапно встроить рабочий сценарий в юридическую функцию.",
  },
];

export default function ContentCasesPage() {
  return (
    <main className="bg-slate-900 text-slate-100 min-h-screen">
      <section className="relative overflow-hidden border-b border-slate-700">
        <HeroBackdrop variant="insights" tone="light" />
        <div className="relative max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 pt-28 pb-14">
          <span className="inline-flex rounded-full border border-amber-500/40 bg-amber-500/10 px-4 py-1 text-sm text-amber-300">
            Контент и практические материалы
          </span>
          <h1 className="mt-5 text-4xl md:text-5xl font-semibold text-white leading-tight">Контент / Кейсы</h1>
          <p className="mt-5 max-w-3xl text-slate-300 text-lg leading-relaxed">
            Разбираем автоматизацию юридической работы на типовых сценариях и в подробных руководствах.
            Мы явно отделяем методические примеры от подтвержденных клиентских результатов.
          </p>
          <div className="mt-8">
            <CtaFrameworkPanel
              leadStart="web_cases_intro"
              miniAppHref={ROUTES.miniAppContent}
              title="Маршрут по кейсам: Узнать -> Проверить -> Обсудить пилот"
              variant="discover-first"
            />
          </div>
        </div>
      </section>

      <section id="practical" className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-14">
        <div className="mb-8 rounded-xl border border-sky-500/30 bg-sky-500/10 p-5 text-sm leading-relaxed text-sky-100">
          На этой странице нет обезличенных «успешных кейсов» без проверяемых исходных данных.
          До публикации согласованных результатов мы показываем сценарии внедрения и методику оценки эффекта.
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          {caseBlocks.map((item) => (
            <article key={item.title} className="rounded-xl border border-slate-800 bg-slate-800/60 p-6">
              <h2 className="text-xl font-semibold text-amber-300">{item.title}</h2>
              <p className="mt-3 text-sm text-slate-300 leading-relaxed">{item.description}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="border-y border-slate-800 bg-slate-950/50">
        <div className="mx-auto max-w-6xl px-4 py-14 sm:px-6 lg:px-8">
          <h2 className="text-3xl font-semibold text-white">Подробные руководства</h2>
          <div className="mt-7 grid gap-5 md:grid-cols-3">
            {guides.map((guide) => (
              <article key={guide.slug} className="rounded-xl border border-slate-800 bg-slate-900 p-6">
                <p className="text-xs text-slate-400">{guide.readingTime}</p>
                <h3 className="mt-3 text-xl font-semibold text-white">
                  <Link href={`/guides/${guide.slug}`} className="hover:text-amber-300">
                    {guide.title}
                  </Link>
                </h3>
                <p className="mt-3 text-sm leading-relaxed text-slate-300">{guide.excerpt}</p>
                <Link href={`/guides/${guide.slug}`} className="mt-5 inline-flex text-sm font-semibold text-amber-300">
                  Читать руководство →
                </Link>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="border-y border-slate-800 bg-slate-800/40">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-14">
          <h2 className="text-3xl font-semibold text-white">Как конвертировать контент в результат</h2>
          <div className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-4 text-slate-200">
            {conversionFlow.map((item) => (
              <article key={item.title} className="rounded-xl border border-slate-800 bg-slate-900/60 p-6">
                <h3 className="font-semibold text-amber-300">{item.title}</h3>
                <p className="mt-3 text-sm text-slate-300 leading-relaxed">{item.description}</p>
              </article>
            ))}
          </div>
          <div className="mt-8">
            <CtaFrameworkPanel
              leadStart="web_cases_discuss"
              miniAppHref={ROUTES.miniAppContent}
              title="Следующий шаг после кейса: Узнать -> Проверить -> Обсудить пилот"
              variant="consult-first"
            />
          </div>
        </div>
      </section>
    </main>
  );
}
