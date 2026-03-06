import type { Metadata } from "next";
import Link from "next/link";
import { EXTERNAL_LINKS, ROUTES, leadBotDeepLink } from "@/lib/links";

export const metadata: Metadata = {
  title: "Контент и кейсы",
  description:
    "Экспертный контент и практические кейсы по автоматизации юридической функции, внедрению AI и управлению юридическими рисками.",
  alternates: { canonical: "/content-cases" },
};

const caseBlocks = [
  {
    title: "Кейсы внедрения",
    description: "Реальные сценарии: что автоматизировали, как измеряли эффект и какие ограничения учитывали.",
  },
  {
    title: "Экспертные обзоры",
    description: "Разборы новых AI-инструментов и правовых изменений через призму практического применения.",
  },
  {
    title: "Методология",
    description: "Подход Legal AI PRO к запуску пилота, контролю рисков и масштабированию решений.",
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
    title: "3. Внедрить",
    description: "Запустить пилот и поэтапно встроить рабочий сценарий в юридическую функцию.",
  },
];

export default function ContentCasesPage() {
  return (
    <main className="bg-slate-950 text-slate-100 min-h-screen">
      <section className="border-b border-slate-800">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 pt-28 pb-14">
          <span className="inline-flex rounded-full border border-amber-500/40 bg-amber-500/10 px-4 py-1 text-sm text-amber-300">
            Контент и практические материалы
          </span>
          <h1 className="mt-5 text-4xl md:text-5xl font-semibold text-white leading-tight">Контент / Кейсы</h1>
          <p className="mt-5 max-w-3xl text-slate-300 text-lg leading-relaxed">
            Разбираем автоматизацию юридической работы на живых примерах: от новостей и трендов до прикладных кейсов,
            которые можно адаптировать в вашей команде.
          </p>
          <div className="mt-8 grid grid-cols-1 md:grid-cols-3 gap-3">
            <a
              href={EXTERNAL_LINKS.channel}
              target="_blank"
              rel="noopener noreferrer"
              className="rounded-lg border border-slate-700 px-5 py-3 font-semibold text-slate-200 hover:border-slate-500 transition-colors text-center"
            >
              Читать контент
            </a>
            <Link
              href={ROUTES.contractAI}
              className="rounded-lg bg-amber-500 px-5 py-3 font-semibold text-slate-950 hover:bg-amber-400 transition-colors text-center"
            >
              Проверить договор
            </Link>
            <Link
              href={ROUTES.solutions}
              className="rounded-lg border border-sky-500/60 px-5 py-3 font-semibold text-sky-200 hover:border-sky-300 transition-colors text-center"
            >
              Перейти к внедрению
            </Link>
          </div>
        </div>
      </section>

      <section id="practical" className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-14">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          {caseBlocks.map((item) => (
            <article key={item.title} className="rounded-xl border border-slate-800 bg-slate-900/60 p-6">
              <h2 className="text-xl font-semibold text-amber-300">{item.title}</h2>
              <p className="mt-3 text-sm text-slate-300 leading-relaxed">{item.description}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="border-y border-slate-800 bg-slate-900/40">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-14">
          <h2 className="text-3xl font-semibold text-white">Как конвертировать контент в результат</h2>
          <div className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-4 text-slate-200">
            {conversionFlow.map((item) => (
              <article key={item.title} className="rounded-xl border border-slate-800 bg-slate-950/60 p-6">
                <h3 className="font-semibold text-amber-300">{item.title}</h3>
                <p className="mt-3 text-sm text-slate-300 leading-relaxed">{item.description}</p>
              </article>
            ))}
          </div>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link
              href={ROUTES.contractAI}
              className="rounded-lg bg-amber-500 px-5 py-3 font-semibold text-slate-950 hover:bg-amber-400 transition-colors"
            >
              Перейти к продукту
            </Link>
            <a
              href={leadBotDeepLink("web_cases_discuss")}
              target="_blank"
              rel="noopener noreferrer"
              className="rounded-lg border border-slate-700 px-5 py-3 font-semibold text-slate-200 hover:border-sky-400 hover:text-sky-300 transition-colors"
            >
              Обсудить кейс
            </a>
            <Link
              href={ROUTES.miniAppContent}
              className="rounded-lg border border-slate-700 px-5 py-3 font-semibold text-slate-200 hover:border-amber-500 hover:text-amber-300 transition-colors"
            >
              Открыть mini-app
            </Link>
          </div>
        </div>
      </section>
    </main>
  );
}
