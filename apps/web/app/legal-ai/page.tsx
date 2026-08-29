import type { Metadata } from "next";
import Link from "next/link";

import HeroBackdrop from "@/components/HeroBackdrop";
import { legalAiTopics } from "@/lib/legalAiTopics";
import { LEGAL_OPERATOR_NAME } from "@/lib/legalProfile";
import { createPageMetadata, SEO_SITE_URL } from "@/lib/seo";

export const metadata: Metadata = createPageMetadata({
  title: "ИИ для юриспруденции: Legal AI в праве",
  description:
    "ИИ для юриспруденции и юридической сферы: Legal AI, нейросети и AI-инструменты для права, документов, поиска, юристов и юридических отделов.",
  path: "/legal-ai",
  type: "article",
  keywords: [
    "ИИ в юридической сфере",
    "ИИ для юриспруденции",
    "ИИ в юриспруденции",
    "искусственный интеллект в юридической сфере",
    "искусственный интеллект в юриспруденции",
    "применение ИИ в юриспруденции",
    "юридический ИИ",
    "правовой ИИ",
    "AI в юридической сфере",
    "Legal AI",
    "ИИ в праве",
    "искусственный интеллект и право",
    "ИИ в юридической деятельности",
  ],
  socialImage: "/solutions/opengraph-image",
});

const tasks = [
  {
    area: "Договорная работа",
    ai: "Извлекает условия, сравнивает редакции, отмечает отклонения от правил и формирует первый риск-профиль.",
    human: "Проверяет контекст сделки, применимое право, существенность риска и итоговую формулировку.",
    href: "/services/contracts-ai",
  },
  {
    area: "Претензии и судебные материалы",
    ai: "Собирает хронологию, связывает факты с документами, классифицирует материалы и готовит рабочий черновик.",
    human: "Определяет правовую позицию, доказательственную стратегию и подписывает процессуальный документ.",
    href: "/services/litigation-ai",
  },
  {
    area: "Legal intake",
    ai: "Распознает тему обращения, извлекает сроки и направляет задачу нужной роли по заданным правилам.",
    human: "Подтверждает приоритет, конфликт интересов, состав исполнителей и дальнейший маршрут.",
    href: "/services",
  },
  {
    area: "Комплаенс и внутренний контроль",
    ai: "Отслеживает сигналы, сопоставляет их с контрольными процедурами и напоминает о подтверждающих действиях.",
    human: "Оценивает применимость требования, выбирает меру реагирования и фиксирует ответственность.",
    href: "/services/compliance-ai",
  },
  {
    area: "База знаний и правовой поиск",
    ai: "Ищет по утвержденным документам, делает краткое резюме и показывает фрагменты, на которых основан ответ.",
    human: "Проверяет актуальность, полноту источников и допустимость использования вывода в конкретной ситуации.",
    href: "/guides/ai-for-lawyers-selection",
  },
  {
    area: "Юридическая аналитика",
    ai: "Классифицирует массив задач и документов, помогает увидеть сроки, типовые риски и повторяющиеся причины задержек.",
    human: "Определяет метрики, проверяет качество данных и принимает управленческие решения.",
    href: "/services/legal-analytics-ai",
  },
];

const terms = [
  {
    title: "Юридический ИИ / Legal AI",
    text: "Общее название технологий искусственного интеллекта, применяемых к юридическим данным, документам и рабочим процессам.",
  },
  {
    title: "ИИ-помощник юриста",
    text: "Интерфейс для поиска, анализа и подготовки материалов. Полезность зависит от источников, правил проверки и места в процессе, а не только от модели.",
  },
  {
    title: "Нейросеть для юридических документов",
    text: "Инструмент для извлечения, классификации, сравнения, проверки или подготовки текста. Результат требует юридической и фактической проверки.",
  },
  {
    title: "Автоматизация юридической функции",
    text: "Более широкий контур: AI, обычные правила, формы, роли, сроки, интеграции и журнал действий объединяются в управляемый процесс.",
  },
];

const queryGroups = [
  {
    title: "Общее название направления",
    text: "ИИ для юриспруденции, ИИ в юриспруденции, искусственный интеллект в юридической сфере, ИИ в праве, искусственный интеллект и право, AI в юридической деятельности.",
    href: "/legal-ai",
  },
  {
    title: "Инструмент для специалиста",
    text: "ИИ для юриста, AI для юристов, нейросеть для юриста, юридическая нейросеть, ИИ-помощник юриста, нейроюрист, юридический AI-ассистент.",
    href: "/for-lawyers",
  },
  {
    title: "Система и технология",
    text: "Legal AI, LegalTech, Legal Tech, LawTech, правовой ИИ, юридический искусственный интеллект, RAG для юристов, юридические AI-агенты.",
    href: "/legal-ai/legaltech",
  },
  {
    title: "Задача и документ",
    text: "ИИ для юридических документов, анализа договоров, составления исков, поиска законов, анализа судебной практики, комплаенса и корпоративной работы.",
    href: "/guides/ai-legal-documents",
  },
  {
    title: "Команда и рабочий процесс",
    text: "ИИ для юридического отдела, автоматизация работы юриста, Legal AI для бизнеса, ИИ для юридической фирмы, AI для адвоката и цифровизация юридической функции.",
    href: "/legal-ai/legal-department",
  },
  {
    title: "Диалоговый формат",
    text: "Юридический ИИ онлайн, юридический AI-консультант, виртуальный юрист, робот-юрист, юридический чат-бот и AI-чат для юридических вопросов.",
    href: "/legal-ai/ai-legal-assistant",
  },
];

const stages = [
  ["1", "Выбрать процесс", "Зафиксировать один повторяемый маршрут, его владельца, входные данные и проблемную точку."],
  ["2", "Подготовить контрольный набор", "Собрать реальные примеры и заранее определить правильные результаты и критичные ошибки."],
  ["3", "Ограничить пилот", "Задать роли, допустимые данные, ручной резервный маршрут и измеримые критерии качества."],
  ["4", "Проверить на новых данных", "Сравнить время, полноту, ложные сигналы и объём ручной доработки вне демонстрационного набора."],
  ["5", "Встроить в систему", "Добавить интеграции, права доступа, журналирование, хранение, удаление и порядок изменения правил."],
];

const faq = [
  {
    question: "Что такое ИИ в юридической сфере?",
    answer:
      "Это применение технологий искусственного интеллекта к юридическим документам, данным и процессам: поиску, классификации, анализу, сравнению, подготовке черновиков и маршрутизации задач. ИИ помогает обработать материал, но не получает профессиональную ответственность юриста.",
  },
  {
    question: "Что означает запрос «ИИ для юриспруденции»?",
    answer:
      "Обычно так ищут искусственный интеллект для юридической деятельности: правовой поиск, анализ и подготовку документов, судебные материалы, Legal AI для юристов и автоматизацию юридического отдела. Это широкий запрос, поэтому конкретные задачи раскрыты на отдельных связанных страницах.",
  },
  {
    question: "ИИ в праве, Legal AI и юридическая нейросеть — это одно и то же?",
    answer:
      "Формулировки пересекаются, но не полностью совпадают. ИИ в праве — широкая область применения и регулирования; Legal AI — класс юридических AI-решений; нейросеть — технология, которая может быть только одним компонентом системы.",
  },
  {
    question: "Как искусственный интеллект используется в юриспруденции?",
    answer:
      "На практике ИИ применяют для первичной проверки договоров, структурирования судебных материалов, поиска по внутренней базе знаний, классификации обращений, комплаенс-мониторинга и юридической аналитики. Для каждого сценария нужны свои источники и контроль качества.",
  },
  {
    question: "Чем юридический ИИ отличается от обычного чат-бота?",
    answer:
      "Юридический рабочий инструмент связан с источниками, правилами компании, ролями доступа и конкретным процессом. Обычный чат без проверяемых оснований может создать убедительный, но ошибочный текст и не обеспечивает управляемый результат.",
  },
  {
    question: "Можно ли передавать нейросети юридические документы?",
    answer:
      "Только после определения состава данных, основания обработки, допустимого контура, прав доступа, сроков хранения и условий провайдера. Персональные данные, коммерческая тайна и иная конфиденциальная информация требуют отдельной оценки до загрузки.",
  },
  {
    question: "Заменит ли искусственный интеллект юристов?",
    answer:
      "ИИ может забрать часть повторяемой обработки информации, но не заменяет оценку фактов, переговоры, профессиональное суждение и ответственность за правовую позицию. Рабочая модель — проверяемый результат ИИ и подтверждение человеком.",
  },
  {
    question: "С чего начать внедрение ИИ в юридическом отделе?",
    answer:
      "Начните с одного частого процесса, контрольного набора и исходной метрики. До пилота определите владельца, критичные ошибки, допустимые данные и ручной маршрут на случай неверного ответа или недоступности системы.",
  },
];

export default function LegalAiPage() {
  const url = `${SEO_SITE_URL}/legal-ai`;
  const structuredData = {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": ["WebPage", "TechArticle"],
        "@id": `${url}#article`,
        url,
        headline: "ИИ для юриспруденции и юридической сферы: Legal AI",
        description: metadata.description,
        datePublished: "2026-08-12",
        dateModified: "2026-08-13",
        inLanguage: "ru-RU",
        author: { "@type": "Person", "@id": `${SEO_SITE_URL}/#founder`, name: LEGAL_OPERATOR_NAME, url: `${SEO_SITE_URL}/team` },
        publisher: { "@type": "Organization", "@id": `${SEO_SITE_URL}/#organization`, name: "AI Verdict", url: SEO_SITE_URL },
        about: [
          { "@type": "Thing", name: "Искусственный интеллект в юридической сфере" },
          { "@type": "Thing", name: "Legal AI" },
          { "@type": "Thing", name: "Автоматизация юридической функции" },
        ],
      },
      {
        "@type": "FAQPage",
        "@id": `${url}#faq`,
        mainEntity: faq.map((item) => ({
          "@type": "Question",
          name: item.question,
          acceptedAnswer: { "@type": "Answer", text: item.answer },
        })),
      },
      {
        "@type": "BreadcrumbList",
        "@id": `${url}#breadcrumb`,
        itemListElement: [
          { "@type": "ListItem", position: 1, name: "Главная", item: SEO_SITE_URL },
          { "@type": "ListItem", position: 2, name: "ИИ в юридической сфере", item: url },
        ],
      },
    ],
  };

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(structuredData) }} />

      <section className="relative overflow-hidden border-b border-slate-700">
        <HeroBackdrop variant="solutions" tone="light" priority />
        <div className="relative mx-auto max-w-6xl px-4 pb-12 pt-24 sm:px-6 sm:pb-16 sm:pt-28 lg:px-8">
          <nav aria-label="Хлебные крошки" className="hidden text-sm text-slate-600 sm:block">
            <Link href="/" className="hover:text-amber-800">Главная</Link> / ИИ в юридической сфере
          </nav>
          <p className="text-sm font-semibold uppercase tracking-wide text-amber-800 sm:mt-6">Практический обзор Legal AI</p>
          <h1 className="mt-3 max-w-5xl text-[32px] font-semibold leading-[1.15] text-slate-950 sm:text-4xl md:text-5xl">
            ИИ для юриспруденции и юридической сферы: применение Legal AI
          </h1>
          <p className="mt-5 max-w-4xl text-base leading-7 text-slate-700 sm:mt-6 sm:text-lg sm:leading-relaxed">
            Разбираем, где искусственный интеллект помогает юристам, как контролировать ошибки и данные и как
            внедрить Legal AI в рабочий процесс.
          </p>
          <div className="mt-7 flex flex-wrap gap-3">
            <Link href="/for-lawyers" className="rounded-lg bg-amber-500 px-5 py-3 font-semibold text-slate-950 hover:bg-amber-400">
              ИИ для юристов
            </Link>
            <Link href="/services" className="rounded-lg border border-slate-500 px-5 py-3 font-semibold text-slate-800 hover:border-amber-600 hover:text-amber-800">
              Сценарии внедрения
            </Link>
          </div>
        </div>
      </section>

      <section className="border-y border-slate-800 bg-slate-900/70">
        <div className="mx-auto max-w-6xl px-4 py-14 sm:px-6 lg:px-8">
          <p className="text-sm font-semibold uppercase tracking-wide text-sky-300">Проверить на практике</p>
          <h2 className="mt-3 text-3xl font-semibold text-white">Инструменты и доказательства вместо обещаний</h2>
          <p className="mt-4 max-w-4xl leading-7 text-slate-300">
            Для решения о внедрении нужны работающий интерфейс, проверяемая методика и расчет на собственных данных.
            Эти материалы можно использовать отдельно от консультации.
          </p>
          <div className="mt-8 grid gap-5 md:grid-cols-3">
            <Link href="/contract-ai-system" className="rounded-xl border border-slate-700 bg-slate-950/70 p-6 hover:border-amber-500">
              <h3 className="text-lg font-semibold text-amber-300">Contract AI →</h3>
              <p className="mt-3 text-sm leading-6 text-slate-300">Действующий интерфейс для анализа и первичной проверки договоров.</p>
            </Link>
            <Link href="/legal-ai/roi" className="rounded-xl border border-slate-700 bg-slate-950/70 p-6 hover:border-amber-500">
              <h3 className="text-lg font-semibold text-amber-300">Калькулятор ROI →</h3>
              <p className="mt-3 text-sm leading-6 text-slate-300">Расчет времени, расходов, срока окупаемости и эффекта пилота.</p>
            </Link>
            <Link href="/cases" className="rounded-xl border border-slate-700 bg-slate-950/70 p-6 hover:border-amber-500">
              <h3 className="text-lg font-semibold text-amber-300">Методика кейса →</h3>
              <p className="mt-3 text-sm leading-6 text-slate-300">Какие показатели фиксировать и когда результат можно считать подтвержденным.</p>
            </Link>
          </div>
        </div>
      </section>

      <section className="border-y border-slate-800 bg-slate-900/70">
        <div className="mx-auto max-w-6xl px-4 py-14 sm:px-6 lg:px-8">
          <p className="text-sm font-semibold uppercase tracking-wide text-sky-300">Семантическая карта</p>
          <h2 className="mt-3 text-3xl font-semibold text-white">Как называют ИИ для юридической работы</h2>
          <p className="mt-4 max-w-4xl leading-7 text-slate-300">
            Люди формулируют одну потребность разными словами. Мы объединяем синонимы на канонической странице,
            а отдельный URL создаем только тогда, когда меняются задача, аудитория или ожидаемый результат.
          </p>
          <div className="mt-8 grid gap-5 md:grid-cols-2 xl:grid-cols-3">
            {queryGroups.map((group) => (
              <article key={group.title} className="rounded-xl border border-slate-700 bg-slate-950/70 p-6">
                <h3 className="text-lg font-semibold text-amber-300">{group.title}</h3>
                <p className="mt-3 text-sm leading-6 text-slate-300">{group.text}</p>
                <Link href={group.href} className="mt-5 inline-flex text-sm font-semibold text-sky-300 hover:text-sky-200">
                  Перейти к теме →
                </Link>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-14 sm:px-6 lg:px-8">
        <div className="grid gap-8 lg:grid-cols-[1.1fr_0.9fr]">
          <div>
            <h2 className="text-3xl font-semibold text-white">Что такое юридический искусственный интеллект</h2>
            <div className="mt-5 space-y-4 leading-7 text-slate-300">
              <p>
                Юридический ИИ — это не отдельный «электронный юрист», а набор технологий для работы с правовой
                информацией. Модели распознают и обобщают текст, извлекают факты, сопоставляют документы, находят
                фрагменты в базе знаний и готовят черновой материал по заданным правилам.
              </p>
              <p>
                Legal AI становится рабочей системой, когда к модели добавлены источники, роли, ограничения,
                интеграции и журнал действий. Поэтому внедрение ИИ в юридическую деятельность шире, чем доступ к
                универсальной нейросети или чату.
              </p>
            </div>
          </div>
          <aside className="rounded-2xl border border-amber-500/30 bg-amber-500/10 p-7">
            <p className="font-semibold text-amber-300">Короткий ответ для цитирования</p>
            <p className="mt-4 leading-7 text-slate-200">
              ИИ в юридической сфере автоматизирует обработку правовой информации: поиск, классификацию, анализ,
              сравнение и подготовку черновиков. Он помогает юристу быстрее работать с материалом, но не заменяет
              проверку фактов, правовую оценку и профессиональную ответственность человека.
            </p>
          </aside>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-14 sm:px-6 lg:px-8">
        <p className="text-sm font-semibold uppercase tracking-wide text-amber-300">Тематический каталог</p>
        <h2 className="mt-3 text-3xl font-semibold text-white">ИИ в работе юриста: отдельные задачи</h2>
        <p className="mt-4 max-w-4xl leading-7 text-slate-300">
          Выберите конкретный процесс. Каждый материал раскрывает самостоятельный поисковый вопрос и ведет к
          подходящему сервису, руководству или юридической практике без дублирования страниц.
        </p>
        <div className="mt-8 grid gap-5 md:grid-cols-2 xl:grid-cols-4">
          {legalAiTopics.map((topic) => (
            <Link
              key={topic.slug}
              href={`/legal-ai/${topic.slug}`}
              className="rounded-xl border border-slate-800 bg-slate-900 p-6 hover:border-amber-500"
            >
              <h3 className="font-semibold text-amber-300">{topic.title}</h3>
              <p className="mt-3 text-sm leading-6 text-slate-300">{topic.description}</p>
              <span className="mt-5 inline-flex text-sm font-semibold text-sky-300">Открыть материал →</span>
            </Link>
          ))}
        </div>
      </section>

      <section className="border-y border-slate-800 bg-slate-900/70">
        <div className="mx-auto max-w-6xl px-4 py-14 sm:px-6 lg:px-8">
          <h2 className="text-3xl font-semibold text-white">Где применяется ИИ в юридической работе</h2>
          <p className="mt-4 max-w-4xl leading-7 text-slate-300">
            Один инструмент не должен одинаково решать все правовые задачи. Для договора, судебного массива, базы
            знаний и входящего обращения нужны разные данные, критерии качества и способы подтверждения результата.
          </p>
          <div className="mt-8 overflow-hidden rounded-2xl border border-slate-700">
            <div className="hidden grid-cols-[0.8fr_1.2fr_1.2fr] bg-slate-800 px-6 py-4 text-sm font-semibold text-slate-200 md:grid">
              <span>Процесс</span><span>Что делает ИИ</span><span>Что проверяет человек</span>
            </div>
            {tasks.map((item) => (
              <article key={item.area} className="grid gap-4 border-t border-slate-800 bg-slate-950/70 px-6 py-6 first:border-t-0 md:grid-cols-[0.8fr_1.2fr_1.2fr]">
                <h3 className="font-semibold text-amber-300">
                  <Link href={item.href} className="hover:text-amber-200">{item.area} →</Link>
                </h3>
                <p className="text-sm leading-6 text-slate-300"><span className="font-semibold text-slate-200 md:hidden">ИИ: </span>{item.ai}</p>
                <p className="text-sm leading-6 text-slate-300"><span className="font-semibold text-slate-200 md:hidden">Человек: </span>{item.human}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-14 sm:px-6 lg:px-8">
        <h2 className="text-3xl font-semibold text-white">Как связаны ИИ, нейросети и автоматизация права</h2>
        <div className="mt-8 grid gap-5 md:grid-cols-2">
          {terms.map((item) => (
            <article key={item.title} className="rounded-xl border border-slate-800 bg-slate-900 p-6">
              <h3 className="text-xl font-semibold text-amber-300">{item.title}</h3>
              <p className="mt-3 text-sm leading-6 text-slate-300">{item.text}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="border-y border-slate-800 bg-slate-900/70">
        <div className="mx-auto max-w-6xl px-4 py-14 sm:px-6 lg:px-8">
          <h2 className="text-3xl font-semibold text-white">Риски применения ИИ в юриспруденции</h2>
          <div className="mt-8 grid gap-5 md:grid-cols-2 xl:grid-cols-4">
            {[
              ["Ошибочный уверенный ответ", "Модель может заполнить пробел правдоподобным текстом. Нужны источники, маркировка неопределенности и проверка юристом."],
              ["Конфиденциальность", "До передачи документа проверяются персональные данные, коммерческая тайна, условия провайдера и допустимая география обработки."],
              ["Устаревшие источники", "Правовой вывод зависит от редакции нормы, даты и фактов. Система должна показывать, на каких материалах основан результат."],
              ["Автоматизация ошибки", "Неверное правило, примененное к сотням документов, опаснее единичной ручной ошибки. Нужны тестовый набор и журнал изменений."],
            ].map(([title, text]) => (
              <article key={title} className="rounded-xl border border-slate-700 bg-slate-950/70 p-6">
                <h3 className="font-semibold text-amber-300">{title}</h3>
                <p className="mt-3 text-sm leading-6 text-slate-300">{text}</p>
              </article>
            ))}
          </div>
          <p className="mt-7 max-w-4xl text-sm leading-6 text-slate-400">
            Для проектов в России отдельно оцениваются требования к обработке персональных данных и защите
            информации. Базовые тексты для проверки требований: {" "}
            <a href="https://ips.pravo.gov.ru/api/ips/legislation/document?baseid=None&hash=98490812b3409e2a8d78a11ca9010f434ea3d9250a11dbbdb78690cd5551bdd6" className="text-sky-300 underline hover:text-sky-200">
              Федеральный закон № 152-ФЗ
            </a>{" "}
            и {" "}
            <a href="https://www.consultant.ru/document/cons_doc_LAW_61798/" className="text-sky-300 underline hover:text-sky-200">
            Федеральный закон № 149-ФЗ
            </a>. Конкретные обязанности зависят от данных, участников и архитектуры проекта.
          </p>
          <Link
            href="/ai-law"
            className="mt-5 inline-flex font-semibold text-amber-300 hover:text-amber-200"
          >
            Комментарии новых норм об искусственном интеллекте →
          </Link>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-14 sm:px-6 lg:px-8">
        <h2 className="text-3xl font-semibold text-white">Как внедрить ИИ в юридический отдел</h2>
        <ol className="mt-8 grid gap-5 lg:grid-cols-5">
          {stages.map(([num, title, text]) => (
            <li key={num} className="rounded-xl border border-slate-800 bg-slate-900 p-6">
              <span className="text-sm font-bold text-amber-400">{num}</span>
              <h3 className="mt-3 font-semibold text-white">{title}</h3>
              <p className="mt-3 text-sm leading-6 text-slate-300">{text}</p>
            </li>
          ))}
        </ol>
        <div className="mt-8 flex flex-wrap gap-4">
          <Link href="/guides/legal-ai-implementation" className="font-semibold text-amber-300 hover:text-amber-200">
            Руководство по внедрению Legal AI →
          </Link>
          <Link href="/guides/legal-ai-data-security" className="font-semibold text-sky-300 hover:text-sky-200">
            Данные и безопасность →
          </Link>
        </div>
      </section>

      <section className="border-y border-slate-800 bg-slate-900/70">
        <div className="mx-auto max-w-6xl px-4 py-14 sm:px-6 lg:px-8">
          <h2 className="text-3xl font-semibold text-white">Частые вопросы об искусственном интеллекте в праве</h2>
          <div className="mt-8 grid gap-5 md:grid-cols-2">
            {faq.map((item) => (
              <article key={item.question} className="rounded-xl border border-slate-700 bg-slate-950/70 p-6">
                <h3 className="text-lg font-semibold text-amber-300">{item.question}</h3>
                <p className="mt-3 text-sm leading-6 text-slate-300">{item.answer}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-14 sm:px-6 lg:px-8">
        <div className="grid gap-6 rounded-2xl border border-amber-500/30 bg-amber-500/10 p-7 md:grid-cols-[1fr_auto] md:items-center">
          <div>
            <h2 className="text-2xl font-semibold text-white">Разобрать применение ИИ в вашем юридическом процессе</h2>
            <p className="mt-3 max-w-3xl leading-7 text-slate-300">
              Опишите процесс, документы и текущие ограничения. Начнем с диагностики задачи и определим, где нужен
              AI, а где надежнее обычные правила или интеграция.
            </p>
          </div>
          <Link href="/#lead-form" className="rounded-lg bg-amber-500 px-6 py-3 text-center font-semibold text-slate-950 hover:bg-amber-400">
            Обсудить процесс
          </Link>
        </div>
        <p className="mt-8 text-sm leading-6 text-slate-500">
          Автор и ответственный за материал — <Link href="/team" className="underline hover:text-slate-300">{LEGAL_OPERATOR_NAME}</Link>.
          Материал проверен 13 августа 2026 года и не заменяет юридическую консультацию по конкретным обстоятельствам.
        </p>
      </section>
    </main>
  );
}
