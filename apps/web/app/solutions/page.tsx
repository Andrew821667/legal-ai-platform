import type { Metadata } from "next";
import Link from "next/link";
import { ROUTES, leadBotDeepLink } from "@/lib/links";

export const metadata: Metadata = {
  title: "Решения",
  description:
    "Решения Legal AI PRO: автоматизация юридической функции, legal ops, интеграции и сценарии внедрения для юристов и бизнеса.",
  alternates: { canonical: "/solutions" },
};

const automationCases = [
  "Входящие юридические заявки и первичная квалификация",
  "Договорный цикл: проверка, согласование, контроль версий",
  "Шаблоны и стандарты юридических документов",
  "Контроль сроков и статусов юридических задач",
];

const legalOpsCases = [
  "Ролевые матрицы принятия юридических решений",
  "SLA и нормативы на типовые запросы",
  "Внутренние knowledge-базы и регламенты",
  "Метрики качества и загрузки юридической команды",
];

const integrationCases = [
  "API-контур с core-сервисами платформы",
  "Интеграция с Telegram-ботами и каналами",
  "Поэтапный rollout без остановки текущих процессов",
  "Аудит логов и контроль чувствительных данных",
];

const launchFormats = [
  {
    title: "Пилот 2-4 недели",
    details: "Подтверждаем эффект на одной приоритетной задаче и фиксируем метрики до/после.",
  },
  {
    title: "Этапное внедрение",
    details: "Последовательно подключаем смежные процессы без слома текущих рабочих контуров.",
  },
  {
    title: "Сопровождение команды",
    details: "Регламенты, обучение, контроль качества и корректировка сценариев по фактической нагрузке.",
  },
];

export default function SolutionsPage() {
  return (
    <main className="bg-slate-950 text-slate-100 min-h-screen">
      <section className="border-b border-slate-800">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 pt-28 pb-14">
          <span className="inline-flex rounded-full border border-amber-500/40 bg-amber-500/10 px-4 py-1 text-sm text-amber-300">
            Решения и услуги
          </span>
          <h1 className="mt-5 text-4xl md:text-5xl font-semibold text-white leading-tight">
            Конструктор внедрения под вашу юридическую функцию
          </h1>
          <p className="mt-5 max-w-3xl text-slate-300 text-lg leading-relaxed">
            Выстраиваем дорожную карту от пилота к системной трансформации: объединяем продуктовые модули,
            процессные настройки и сопровождение команды.
          </p>
          <div className="mt-8 grid grid-cols-1 md:grid-cols-3 gap-3">
            <Link
              href={ROUTES.contentCases}
              className="rounded-lg border border-slate-700 px-5 py-3 font-semibold text-slate-200 hover:border-slate-500 transition-colors text-center"
            >
              Узнать на кейсах
            </Link>
            <Link
              href={ROUTES.contractAI}
              className="rounded-lg bg-amber-500 px-5 py-3 font-semibold text-slate-950 hover:bg-amber-400 transition-colors text-center"
            >
              Проверить в продукте
            </Link>
            <a
              href={leadBotDeepLink("web_solutions_intro")}
              target="_blank"
              rel="noopener noreferrer"
              className="rounded-lg border border-sky-500/60 px-5 py-3 font-semibold text-sky-200 hover:border-sky-300 transition-colors text-center"
            >
              Внедрить с командой
            </a>
          </div>
        </div>
      </section>

      <section id="automation" className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-14">
        <h2 className="text-3xl font-semibold text-white">Автоматизация юрфункции</h2>
        <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-4">
          {automationCases.map((item) => (
            <article key={item} className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 text-slate-200">
              {item}
            </article>
          ))}
        </div>
      </section>

      <section id="legal-ops" className="border-y border-slate-800 bg-slate-900/40">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-14">
          <h2 className="text-3xl font-semibold text-white">Внедрение AI в legal ops</h2>
          <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-4">
            {legalOpsCases.map((item) => (
              <article key={item} className="rounded-xl border border-slate-800 bg-slate-950/60 p-5 text-slate-200">
                {item}
              </article>
            ))}
          </div>
        </div>
      </section>

      <section id="integrations" className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-14">
        <h2 className="text-3xl font-semibold text-white">Интеграции и архитектура</h2>
        <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-4">
          {integrationCases.map((item) => (
            <article key={item} className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 text-slate-200">
              {item}
            </article>
          ))}
        </div>
      </section>

      <section className="border-y border-slate-800 bg-slate-900/40">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-14">
          <h2 className="text-3xl font-semibold text-white">Форматы запуска</h2>
          <div className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-4">
            {launchFormats.map((format) => (
              <article key={format.title} className="rounded-xl border border-slate-800 bg-slate-950/60 p-6">
                <h3 className="text-lg font-semibold text-amber-300">{format.title}</h3>
                <p className="mt-3 text-sm text-slate-300 leading-relaxed">{format.details}</p>
              </article>
            ))}
          </div>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link
              href={ROUTES.contractAI}
              className="rounded-lg bg-amber-500 px-5 py-3 font-semibold text-slate-950 hover:bg-amber-400 transition-colors"
            >
              Перейти к Contract_AI_System
            </Link>
            <a
              href={leadBotDeepLink("web_solutions_discuss")}
              target="_blank"
              rel="noopener noreferrer"
              className="rounded-lg border border-slate-700 px-5 py-3 font-semibold text-slate-200 hover:border-sky-400 hover:text-sky-300 transition-colors"
            >
              Обсудить проект
            </a>
          </div>
        </div>
      </section>
    </main>
  );
}
