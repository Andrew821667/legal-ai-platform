import type { Metadata } from "next";
import Link from "next/link";
import { createPageMetadata } from "@/lib/seo";
import HeroBackdrop from "@/components/HeroBackdrop";

export const metadata: Metadata = createPageMetadata({
  title: "Автоматизация юридических процессов: решения",
  description:
    "Решения для автоматизации юридических процессов: договоры, legal intake, комплаенс, legal ops, интеграции с CRM, ERP, 1С, ЭДО и внутренними системами.",
  path: "/solutions",
  socialImage: "/solutions/opengraph-image",
  keywords: ["автоматизация юридических процессов", "автоматизация юридической функции", "legal ops", "Legal AI"],
});

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
  "Интеграции с CRM, ERP, 1С, ЭДО, Google Sheets и внутренними базами",
  "Telegram-боты, сайты, mini app, личные кабинеты и внутренние панели",
  "Отдельные сервисы для заявок, документов, уведомлений, отчетов и аналитики",
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
    details: "Последовательно подключаем связанные процессы без слома текущих рабочих контуров.",
  },
  {
    title: "Сопровождение команды",
    details: "Регламенты, обучение, контроль качества и корректировка сценариев по фактической нагрузке.",
  },
];

export default function SolutionsPage() {
  return (
    <main className="bg-slate-900 text-slate-100 min-h-screen">
      <section className="relative overflow-hidden border-b border-slate-700">
        <HeroBackdrop variant="home" tone="light" priority />
        <div className="relative mx-auto flex min-h-[570px] max-w-6xl items-center px-4 pb-14 pt-24 sm:min-h-[500px] sm:px-6 sm:py-28 lg:px-8">
          <div>
          <span className="inline-flex rounded-full border border-amber-500/40 bg-amber-500/10 px-4 py-1 text-sm text-amber-300">
            Решения и услуги
          </span>
          <h1 className="mt-5 text-3xl font-semibold leading-tight text-white sm:text-4xl md:text-5xl">
            Автоматизация юридических процессов: решения для компании
          </h1>
          <p className="mt-5 max-w-3xl text-base leading-7 text-slate-300 sm:text-lg sm:leading-relaxed">
            Выстраиваем дорожную карту от одного пилота к рабочему legal-контуру: договоры, юридические заявки,
            комплаенс, база знаний и контроль сроков связываются с процессными правилами, интеграциями и ролями команды.
          </p>
          <div className="mt-8 flex flex-col items-start gap-4 sm:flex-row sm:items-center">
            <Link href="/#lead-form" className="w-full rounded-lg bg-amber-500 px-6 py-3 text-center font-semibold text-slate-950 hover:bg-amber-400 sm:w-auto">
              Обсудить процесс
            </Link>
            <Link href="/services" className="font-semibold text-slate-700 underline decoration-amber-500/60 underline-offset-4 hover:text-amber-700">
              Посмотреть все услуги →
            </Link>
          </div>
          </div>
        </div>
      </section>

      <section id="automation" className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-14">
        <h2 className="text-3xl font-semibold text-white">Автоматизация юрфункции</h2>
        <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-4">
          {automationCases.map((item) => (
            <article key={item} className="rounded-xl border border-slate-800 bg-slate-800/60 p-5 text-slate-200">
              {item}
            </article>
          ))}
        </div>
      </section>

      <section id="legal-ops" className="border-y border-slate-800 bg-slate-800/40">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-14">
          <h2 className="text-3xl font-semibold text-white">Внедрение AI в legal ops</h2>
          <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-4">
            {legalOpsCases.map((item) => (
              <article key={item} className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 text-slate-200">
                {item}
              </article>
            ))}
          </div>
        </div>
      </section>

      <section id="integrations" className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-14">
        <h2 className="text-3xl font-semibold text-white">Интеграции, архитектура и разработка</h2>
        <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-4">
          {integrationCases.map((item) => (
            <article key={item} className="rounded-xl border border-slate-800 bg-slate-800/60 p-5 text-slate-200">
              {item}
            </article>
          ))}
        </div>
      </section>

      <section className="border-y border-slate-800 bg-slate-800/40">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-14">
          <h2 className="text-3xl font-semibold text-white">Форматы запуска</h2>
          <div className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-4">
            {launchFormats.map((format) => (
              <article key={format.title} className="rounded-xl border border-slate-800 bg-slate-900/60 p-6">
                <h3 className="text-lg font-semibold text-amber-300">{format.title}</h3>
                <p className="mt-3 text-sm text-slate-300 leading-relaxed">{format.details}</p>
              </article>
            ))}
          </div>
          <div className="mt-8 rounded-2xl border border-amber-500/40 bg-slate-950 p-7 md:flex md:items-center md:justify-between md:gap-8">
            <div>
              <h3 className="text-xl font-semibold text-white">Начать с одного измеримого процесса</h3>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-300">
                Зафиксируем исходные метрики, границы пилота и критерии перехода к рабочему контуру.
              </p>
            </div>
            <Link href="/#lead-form" className="mt-5 inline-flex rounded-lg bg-amber-500 px-6 py-3 font-semibold text-slate-950 hover:bg-amber-400 md:mt-0">
              Обсудить пилот
            </Link>
          </div>
        </div>
      </section>
    </main>
  );
}
