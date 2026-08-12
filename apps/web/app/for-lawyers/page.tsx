import type { Metadata } from "next";
import Link from "next/link";
import { ROUTES } from "@/lib/links";
import { createPageMetadata, SEO_SITE_URL } from "@/lib/seo";
import CtaFrameworkPanel from "@/components/CtaFrameworkPanel";
import HeroBackdrop from "@/components/HeroBackdrop";

export const metadata: Metadata = createPageMetadata({
  title: "ИИ для юристов: нейросети, сервисы и сценарии",
  description:
    "ИИ и нейросети для юристов и юридических отделов: договоры, документы, претензионная работа, правовой поиск, Legal AI и безопасный запуск пилота.",
  path: "/for-lawyers",
  keywords: [
    "ИИ для юристов",
    "нейросеть для юриста",
    "юридическая нейросеть",
    "ИИ помощник для юриста",
    "AI для юристов",
    "AI для юриста",
    "Legal AI для юристов",
    "автоматизация работы юриста",
    "ИИ для юриста онлайн",
    "ИИ для юриста в России",
    "лучший ИИ для юриста",
    "бесплатная нейросеть для юриста",
    "ИИ ассистент для юриста",
    "ИИ инструменты для юриста",
  ],
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
    href: "/engineering",
  },
];

const practicalTopics = [
  { href: "/legal-ai/prompts-for-lawyers", title: "Промпты для юристов", text: "Шаблоны запросов с запретом на выдуманные факты и обязательной самопроверкой." },
  { href: "/legal-ai/legal-research", title: "Правовой поиск", text: "Работа с источниками, редакциями норм и подтверждающими фрагментами." },
  { href: "/legal-ai/court-practice-analysis", title: "Судебная практика", text: "Выборка актов, факторы дела и проверяемая матрица позиций." },
  { href: "/legal-ai/court-documents", title: "Процессуальные документы", text: "Факты, доказательства, структура и безопасная подготовка черновика." },
  { href: "/legal-ai/ai-legal-assistant", title: "ИИ-помощник юриста", text: "Вопросы, документы, источники и границы AI-консультанта." },
  { href: "/legal-ai/rag-knowledge-base", title: "RAG и база знаний", text: "Поиск по внутренним материалам с цитатами и учетом прав доступа." },
  { href: "/legal-ai/ai-agents", title: "AI-агенты для юристов", text: "Многошаговые задачи, инструменты и контролируемая автономность." },
  { href: "/legal-ai/law-firm", title: "ИИ для юридической фирмы", text: "Сценарии для адвоката, частного юриста и профессиональной практики." },
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
  {
    question: "Чем юридическая нейросеть отличается от универсального ИИ-чата?",
    answer: "Юридическая нейросеть должна работать с проверяемыми источниками, документами и правилами процесса. Универсальный чат удобен для идей и черновиков, но без источников, ролей и контроля не образует надежный Legal AI-контур.",
  },
  {
    question: "Можно ли использовать ИИ для подготовки юридических документов?",
    answer: "Да, как инструмент для структуры, извлечения фактов и черновой редакции. Неизвестные факты нельзя заполнять автоматически, а нормы, реквизиты, позицию и итоговый текст должен проверить ответственный юрист.",
  },
  {
    question: "Какой ИИ лучший для юриста?",
    answer: "Универсально лучшего решения нет. Для правового поиска важны актуальные источники, для документов — ссылки на фрагменты и работа с файлами, для юридического отдела — роли, журнал и интеграции. Сравнивать нужно на одном контрольном наборе.",
  },
  {
    question: "Подойдет ли бесплатный ИИ для юриста?",
    answer: "Бесплатный или публичный чат можно использовать для обезличенных черновых задач, если проверены условия обработки данных. Для рабочих документов и постоянного процесса обычно нужны управляемый доступ, источники и гарантии хранения.",
  },
  {
    question: "Можно ли пользоваться ИИ для юриста онлайн?",
    answer: "Да, но до загрузки материалов проверьте, какие данные передаются, где они обрабатываются, сохраняются ли запросы и используются ли они для обучения. Конфиденциальные документы требуют отдельного допустимого контура.",
  },
  {
    question: "Что учитывать при выборе ИИ для юриста в России?",
    answer: "Работу с российскими источниками и редакциями права, применимость к реальному процессу, условия обработки персональных и конфиденциальных данных, возможность проверить основания и наличие ответственного специалиста.",
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
          <Link href="/legal-ai" className="mt-6 inline-flex font-semibold text-slate-700 underline decoration-amber-600 underline-offset-4 hover:text-amber-800">
            Что такое ИИ в юридической сфере и как он применяется →
          </Link>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-14 sm:px-6 lg:px-8">
        <h2 className="text-3xl font-semibold text-white">ИИ-помощник, нейросеть и Legal AI для юриста</h2>
        <p className="mt-4 max-w-4xl leading-7 text-slate-300">
          Эти названия часто используют как синонимы, но для выбора решения важен не ярлык, а рабочий контур:
          источники, документы, правила проверки, права доступа и действие, которое следует после ответа системы.
        </p>
        <div className="mt-8 grid gap-5 md:grid-cols-3">
          <article className="rounded-xl border border-slate-800 bg-slate-900/70 p-6">
            <h3 className="text-lg font-semibold text-amber-300">ИИ-помощник юриста</h3>
            <p className="mt-3 text-sm leading-6 text-slate-300">Диалоговый интерфейс для поиска, анализа, резюме и подготовки рабочего черновика.</p>
          </article>
          <article className="rounded-xl border border-slate-800 bg-slate-900/70 p-6">
            <h3 className="text-lg font-semibold text-amber-300">Нейросеть для юриста</h3>
            <p className="mt-3 text-sm leading-6 text-slate-300">Модель, которая обрабатывает текст и документы; сама по себе не гарантирует актуальность источников и юридическую точность.</p>
          </article>
          <article className="rounded-xl border border-slate-800 bg-slate-900/70 p-6">
            <h3 className="text-lg font-semibold text-amber-300">Legal AI-система</h3>
            <p className="mt-3 text-sm leading-6 text-slate-300">Модель вместе с источниками, правилами, ролями, журналом, интеграциями и контролем человека.</p>
          </article>
        </div>
        <Link href="/guides/ai-legal-documents" className="mt-7 inline-flex font-semibold text-sky-300 hover:text-sky-200">
          ИИ для подготовки и проверки юридических документов →
        </Link>
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

      <section className="mx-auto max-w-6xl px-4 py-14 sm:px-6 lg:px-8">
        <h2 className="text-3xl font-semibold text-white">Практические материалы для юриста</h2>
        <div className="mt-8 grid gap-5 md:grid-cols-2 xl:grid-cols-4">
          {practicalTopics.map((item) => (
            <Link key={item.href} href={item.href} className="rounded-xl border border-slate-800 bg-slate-900/70 p-6 hover:border-amber-500">
              <h3 className="font-semibold text-amber-300">{item.title} →</h3>
              <p className="mt-3 text-sm leading-6 text-slate-300">{item.text}</p>
            </Link>
          ))}
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
