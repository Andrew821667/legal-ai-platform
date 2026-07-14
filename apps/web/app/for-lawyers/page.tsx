import type { Metadata } from "next";
import Link from "next/link";
import { ROUTES } from "@/lib/links";
import { createPageMetadata, SEO_SITE_URL } from "@/lib/seo";
import CtaFrameworkPanel from "@/components/CtaFrameworkPanel";
import HeroBackdrop from "@/components/HeroBackdrop";

export const metadata: Metadata = createPageMetadata({
  title: "ИИ для юристов: сервисы и сценарии применения",
  description:
    "ИИ для юристов и юридических отделов: проверка договоров, претензионная работа, legal intake, поиск по базе знаний и безопасный запуск пилота.",
  path: "/for-lawyers",
  keywords: ["ИИ для юристов", "ИИ помощник для юриста", "AI для юристов", "автоматизация работы юриста"],
});

const tracks = [
  {
    title: "Договорный поток",
    description: "Предпроверка рисков, чек-листы, согласование правок и единый стандарт комментариев.",
  },
  {
    title: "Претензионная и судебная подготовка",
    description: "Сбор позиции, структурирование фактов, подготовка проектной документации.",
  },
  {
    title: "Legal ops",
    description: "SLA, шаблоны, маршрутизация задач, контроль нагрузки и качество юридических ответов.",
  },
];

const scenarios = [
  {
    title: "Проверка договоров с помощью ИИ",
    description: "Первичный разбор условий, матрица рисков, комментарии к спорным пунктам и подготовка правок для проверки юристом.",
    href: "/services/contracts-ai",
  },
  {
    title: "Претензионная и судебная работа",
    description: "Структурирование фактов и документов, черновая подготовка позиции, контроль событий и процессуальных сроков.",
    href: "/services/litigation-ai",
  },
  {
    title: "Комплаенс и проверяемые сигналы",
    description: "Мониторинг изменений, маршрутизация факторов риска, назначение ответственных и подтверждение закрывающих действий.",
    href: "/services/compliance-ai",
  },
  {
    title: "Legal intake и внутренняя база знаний",
    description: "Классификация обращений, поиск по утвержденным материалам и передача задачи нужному специалисту с понятным контекстом.",
    href: "/services/custom-ai",
  },
];

const selectionCriteria = [
  "Есть ссылки на исходный документ, правило или другой проверяемый источник.",
  "Можно ограничить доступ, сроки хранения и передачу данных внешним провайдерам.",
  "Неуверенные выводы маркируются, а критичное решение остается за юристом.",
  "Качество можно проверить на контрольном наборе и измерить до масштабирования.",
];

const faq = [
  {
    question: "Какой ИИ подходит для работы юриста?",
    answer: "Выбор зависит от задачи. Для договоров важны работа с файлами, ссылки на пункты и матрица рисков; для базы знаний — подтвержденные источники; для legal intake — точная классификация и интеграция с рабочей системой.",
  },
  {
    question: "Может ли ИИ заменить юридическую проверку?",
    answer: "Нет. ИИ ускоряет поиск, первичный анализ и подготовку черновика, но юридическую позицию, критичные риски и итоговый документ подтверждает ответственный специалист.",
  },
  {
    question: "Как безопасно передавать договоры и другие документы?",
    answer: "До запуска определяют допустимый контур обработки, роли доступа, сроки хранения, правила удаления и перечень данных, которые нельзя передавать внешней модели. Для чувствительных сценариев нужен отдельный или локальный контур.",
  },
  {
    question: "С чего начать внедрение ИИ в юридическом отделе?",
    answer: "С одного повторяемого процесса, понятной исходной метрики и контрольного набора. Пилот должен иметь владельца, ручной резервный маршрут и заранее согласованные критерии качества.",
  },
];

export default function ForLawyersPage() {
  const structuredData = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    "@id": `${SEO_SITE_URL}/for-lawyers#faq`,
    mainEntity: faq.map((item) => ({
      "@type": "Question",
      name: item.question,
      acceptedAnswer: { "@type": "Answer", text: item.answer },
    })),
  };

  return (
    <main className="bg-slate-900 text-slate-100 min-h-screen">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(structuredData) }} />
      <section className="relative overflow-hidden border-b border-slate-700">
        <HeroBackdrop variant="solutions" tone="light" />
        <div className="relative max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 pt-28 pb-14">
          <span className="inline-flex rounded-full border border-amber-500/40 bg-amber-500/10 px-4 py-1 text-sm text-amber-300">
            Для юридических команд
          </span>
          <h1 className="mt-5 text-4xl md:text-5xl font-semibold text-white leading-tight">
            ИИ для юристов: практические инструменты и автоматизация работы
          </h1>
          <p className="mt-5 max-w-3xl text-slate-300 text-lg leading-relaxed">
            Встраиваем ИИ в повторяемые юридические процессы: проверку договоров, согласования, претензионную работу,
            legal intake и поиск по внутренней базе знаний. Система готовит проверяемый материал, а решение остается
            за юристом.
          </p>
        </div>
      </section>

      <section className="border-y border-slate-800 bg-slate-800/40">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-14">
          <h2 className="text-3xl font-semibold text-white">Где ИИ помогает юристу на практике</h2>
          <p className="mt-4 max-w-3xl text-slate-300 leading-relaxed">
            Полезный ИИ-инструмент решает конкретный участок работы и показывает основание результата. Для каждого
            сценария отдельно задаются данные, правила проверки, ответственный и измеримый результат.
          </p>
          <div className="mt-8 grid gap-5 md:grid-cols-2">
            {scenarios.map((item) => (
              <article key={item.title} className="rounded-xl border border-slate-700 bg-slate-900/60 p-6">
                <h3 className="text-xl font-semibold text-amber-300">{item.title}</h3>
                <p className="mt-3 text-sm leading-6 text-slate-300">{item.description}</p>
                <Link href={item.href} className="mt-5 inline-flex font-semibold text-sky-300 hover:text-sky-200">
                  Открыть сценарий →
                </Link>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-14">
        <div className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
          <div>
            <h2 className="text-3xl font-semibold text-white">Как выбрать ИИ для юридической работы</h2>
            <p className="mt-4 text-slate-300 leading-relaxed">
              Название модели и качество демонстрации недостаточны. Проверять нужно воспроизводимость результата,
              работу с источниками, защиту данных и возможность встроить инструмент в действующий процесс команды.
            </p>
            <Link href="/guides/ai-for-lawyers-selection" className="mt-6 inline-flex font-semibold text-amber-300 hover:text-amber-200">
              Руководство по выбору ИИ для юриста →
            </Link>
          </div>
          <ul className="space-y-3 rounded-2xl border border-slate-700 bg-slate-800/70 p-7">
            {selectionCriteria.map((item) => (
              <li key={item} className="flex gap-3 text-sm leading-6 text-slate-200">
                <span aria-hidden="true" className="text-emerald-300">✓</span>
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-14">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          {tracks.map((item) => (
            <article key={item.title} className="rounded-xl border border-slate-800 bg-slate-800/60 p-6">
              <h2 className="text-xl font-semibold text-amber-300">{item.title}</h2>
              <p className="mt-3 text-slate-300 text-sm leading-relaxed">{item.description}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="border-y border-slate-800 bg-slate-800/40">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-14">
          <h2 className="text-3xl font-semibold text-white">Как запускаем внедрение</h2>
          <ol className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-4">
            <li className="rounded-xl border border-slate-800 bg-slate-900/60 p-5">
              <p className="text-amber-300 font-semibold">1. Диагностика</p>
              <p className="mt-2 text-sm text-slate-300">Фиксируем процесс, риски, объем рутины и точки экономии времени.</p>
            </li>
            <li className="rounded-xl border border-slate-800 bg-slate-900/60 p-5">
              <p className="text-amber-300 font-semibold">2. Пилот</p>
              <p className="mt-2 text-sm text-slate-300">Запускаем ограниченный сценарий и измеряем фактический эффект на KPI.</p>
            </li>
            <li className="rounded-xl border border-slate-800 bg-slate-900/60 p-5">
              <p className="text-amber-300 font-semibold">3. Масштабирование</p>
              <p className="mt-2 text-sm text-slate-300">Закрепляем правила и переносим подход на соседние юридические процессы.</p>
            </li>
          </ol>
          <div className="mt-8">
            <CtaFrameworkPanel
              leadStart="web_for_lawyers"
              miniAppHref={ROUTES.miniAppTools}
              title="Единый маршрут для юристов: Узнать -> Проверить -> Обсудить пилот"
              variant="validate-first"
            />
          </div>
        </div>
      </section>

      <section className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-14">
        <h2 className="text-3xl font-semibold text-white">Частые вопросы об ИИ для юристов</h2>
        <div className="mt-8 grid gap-5 md:grid-cols-2">
          {faq.map((item) => (
            <article key={item.question} className="rounded-xl border border-slate-800 bg-slate-800/60 p-6">
              <h3 className="text-lg font-semibold text-amber-300">{item.question}</h3>
              <p className="mt-3 text-sm leading-6 text-slate-300">{item.answer}</p>
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}
