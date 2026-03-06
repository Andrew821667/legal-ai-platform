import type { Metadata } from "next";
import Link from "next/link";
import { ROUTES, leadBotDeepLink } from "@/lib/links";

export const metadata: Metadata = {
  title: "Платформа Legal AI PRO",
  description:
    "Платформа для автоматизации юридической функции: отдельные сценарии для юристов и бизнеса, флагманский Contract_AI_System и прикладные решения внедрения.",
  alternates: {
    canonical: "/",
  },
};

const audienceCards = [
  {
    title: "Для юристов",
    description:
      "Ускоряем договорную и претензионную работу, снижаем рутину, стандартизируем контроль качества без потери юридической точности.",
    href: ROUTES.forLawyers,
    cta: "Сценарии для юристов",
  },
  {
    title: "Для бизнеса",
    description:
      "Выстраиваем управляемую юридическую функцию: быстрее согласования, прозрачные SLA, контроль рисков и прогнозируемая нагрузка команды.",
    href: ROUTES.forBusiness,
    cta: "Сценарии для бизнеса",
  },
];

const platformLayers = [
  {
    title: "Контент и аналитика",
    description: "Канал и редакционный контур: подбор тем, драфты, модерация, управляемая публикация.",
  },
  {
    title: "Contract_AI_System",
    description: "Центральный продукт: проверка договора, выявление рисков, комментарии и рекомендации по правкам.",
  },
  {
    title: "Внедрение и сопровождение",
    description: "Пилот, настройка процессов, обучение команды и развитие roadmap автоматизации.",
  },
];

const cases = [
  "Автоматизация входящих заявок и квалификации обращений",
  "Сокращение цикла согласования договоров за счет AI-проверки",
  "Единый контур юридического контента и экспертных разборов",
  "Поддержка legal ops: регламенты, шаблоны, контроль качества",
];

export default function Home() {
  return (
    <main className="bg-slate-950 text-slate-100">
      <section className="relative overflow-hidden border-b border-slate-800">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,_rgba(245,158,11,0.16),_transparent_52%)]" />
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_bottom_left,_rgba(59,130,246,0.14),_transparent_45%)]" />
        <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-28 pb-18">
          <span className="inline-flex items-center rounded-full border border-amber-500/40 bg-amber-500/10 px-4 py-1 text-sm text-amber-300">
            Платформа автоматизации юридической работы
          </span>
          <h1 className="mt-6 max-w-4xl text-4xl md:text-5xl font-semibold leading-tight text-white">
            Legal AI PRO: единая система для юридической функции, контента и внедрения AI-решений
          </h1>
          <p className="mt-6 max-w-3xl text-lg text-slate-300 leading-relaxed">
            Помогаем перейти от разрозненных AI-экспериментов к управляемой практике: выделяем приоритетные процессы,
            внедряем Contract_AI_System и фиксируем бизнес-эффект на уровне KPI.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
              <Link
              href={ROUTES.contractAI}
              className="rounded-lg bg-amber-500 px-6 py-3 font-semibold text-slate-950 hover:bg-amber-400 transition-colors"
            >
              Попробовать Contract_AI_System
            </Link>
            <Link
              href={ROUTES.solutions}
              className="rounded-lg border border-slate-700 px-6 py-3 font-semibold text-slate-200 hover:border-amber-500 hover:text-amber-300 transition-colors"
            >
              Посмотреть решения
            </Link>
            <a
              href={leadBotDeepLink("web_home_intro")}
              target="_blank"
              rel="noopener noreferrer"
              className="rounded-lg border border-slate-700 px-6 py-3 font-semibold text-slate-200 hover:border-sky-400 hover:text-sky-300 transition-colors"
            >
              Написать в Ассистент Legal AI Pro
            </a>
          </div>
        </div>
      </section>

      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {audienceCards.map((card) => (
            <article key={card.title} className="rounded-2xl border border-slate-800 bg-slate-900/60 p-7">
              <h2 className="text-2xl font-semibold text-white">{card.title}</h2>
              <p className="mt-4 text-slate-300 leading-relaxed">{card.description}</p>
              <Link href={card.href} className="mt-6 inline-flex text-amber-300 hover:text-amber-200 font-semibold">
                {card.cta} →
              </Link>
            </article>
          ))}
        </div>
      </section>

      <section className="border-y border-slate-800 bg-slate-900/40" id="product-entry">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
          <div className="max-w-3xl">
            <h2 className="text-3xl md:text-4xl font-semibold text-white">Флагманский вход: Contract_AI_System</h2>
            <p className="mt-4 text-slate-300">
              Вся архитектура платформы сходится в продукте проверки договоров. Сначала выявляем риски и зоны контроля,
              затем масштабируем подход на смежные юридические процессы.
            </p>
          </div>
          <div className="mt-8 grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="rounded-xl bg-slate-950/60 border border-slate-800 p-5">
              <h3 className="font-semibold text-white">Проверить</h3>
              <p className="mt-2 text-sm text-slate-400">Быстрый анализ договора и подсветка рискованных условий.</p>
            </div>
            <div className="rounded-xl bg-slate-950/60 border border-slate-800 p-5">
              <h3 className="font-semibold text-white">Уточнить</h3>
              <p className="mt-2 text-sm text-slate-400">Комментарий по нормам, альтернативные формулировки и план правок.</p>
            </div>
            <div className="rounded-xl bg-slate-950/60 border border-slate-800 p-5">
              <h3 className="font-semibold text-white">Внедрить</h3>
              <p className="mt-2 text-sm text-slate-400">Интеграция в процесс согласования и матрицу юридического контроля.</p>
            </div>
          </div>
        </div>
      </section>

      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        <h2 className="text-3xl font-semibold text-white">Карта платформы</h2>
        <div className="mt-8 grid grid-cols-1 md:grid-cols-3 gap-5">
          {platformLayers.map((layer) => (
            <article key={layer.title} className="rounded-xl border border-slate-800 bg-slate-900/50 p-6">
              <h3 className="text-lg font-semibold text-amber-300">{layer.title}</h3>
              <p className="mt-3 text-sm text-slate-300 leading-relaxed">{layer.description}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="border-y border-slate-800 bg-slate-900/40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
          <h2 className="text-3xl font-semibold text-white">Сценарии, которые запускаем первыми</h2>
          <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-4">
            {cases.map((item) => (
              <div key={item} className="rounded-xl border border-slate-800 bg-slate-950/60 px-5 py-4 text-slate-200">
                {item}
              </div>
            ))}
          </div>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link
              href={ROUTES.contentCases}
              className="rounded-lg border border-slate-700 px-5 py-3 font-semibold text-slate-100 hover:border-amber-500 hover:text-amber-300 transition-colors"
            >
              Контент и кейсы
            </Link>
            <Link
              href={ROUTES.about}
              className="rounded-lg border border-slate-700 px-5 py-3 font-semibold text-slate-100 hover:border-amber-500 hover:text-amber-300 transition-colors"
            >
              О платформе
            </Link>
          </div>
        </div>
      </section>
    </main>
  );
}
