import type { Metadata } from "next";
import Link from "next/link";
import { EXTERNAL_LINKS, ROUTES, contractAIEntryHref, contractAIEntryIsExternal, contractAISsoUrl } from "@/lib/links";
import { SEO_SITE_URL } from "@/lib/seo";
import CtaFrameworkPanel from "@/components/CtaFrameworkPanel";
import PageFAQ from "@/components/PageFAQ";

export const metadata: Metadata = {
  title: "Contract AI — нейросеть для анализа и проверки договоров",
  description:
    "Contract AI от AI Verdict: анализ и проверка договоров нейросетью, поиск юридических рисков и рекомендации по правкам. До 3 договоров в месяц бесплатно.",
  alternates: { canonical: "/contract-ai-system" },
  openGraph: {
    title: "Contract AI — анализ и проверка договоров с ИИ | AI Verdict",
    description:
      "AI-сервис для первичной проверки договоров, выявления рисков и запуска пилота договорной автоматизации.",
    url: "/contract-ai-system",
    type: "website",
    images: [{ url: "/opengraph-image", width: 1200, height: 630, alt: "Contract AI от AI Verdict" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "Contract AI — анализ и проверка договоров с ИИ | AI Verdict",
    description: "Проверка договоров нейросетью, риск-профиль и бесплатный старт.",
    images: ["/opengraph-image"],
  },
  robots: {
    index: true,
    follow: true,
  },
};

const contractProductUrl = "https://contract.ai-verdict.ru";

const contractBreadcrumbSchema = {
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  "@id": `${SEO_SITE_URL}/contract-ai-system#breadcrumb`,
  itemListElement: [
    { "@type": "ListItem", position: 1, name: "Главная", item: SEO_SITE_URL },
    { "@type": "ListItem", position: 2, name: "Contract AI", item: `${SEO_SITE_URL}/contract-ai-system` },
  ],
};

const contractFaqItems = [
  {
    question: "Сколько стоит проверка договора в Contract AI?",
    answer:
      "Стартовый режим бесплатный — до 3 договоров в месяц. Этого достаточно, чтобы проверить сервис на реальных документах, а для регулярной работы обсуждается пилот и рабочий контур.",
  },
  {
    question: "Что делает Contract AI при проверке договора?",
    answer:
      "Сервис анализирует условия документа, выделяет юридические риски и предлагает рекомендации по правкам. Также он умеет сравнивать версии договоров и готовить протоколы разногласий.",
  },
  {
    question: "Заменяет ли Contract AI юриста?",
    answer:
      "Нет. Сервис ускоряет первичную проверку и подсвечивает риски, а решения остаётся принимать юристу — это принцип всей платформы AI Verdict.",
  },
  {
    question: "Как начать работу с Contract AI?",
    answer:
      "Откройте сервис contract.ai-verdict.ru, загрузите договор и получите разбор рисков. Бесплатного режима хватает для первой проверки, дальше можно обсудить пилот под ваши процессы.",
  },
];

const softwareSchema = {
  "@context": "https://schema.org",
  "@type": "WebApplication",
  "@id": `${contractProductUrl}/#application`,
  name: "Contract AI by AI Verdict",
  alternateName: "Contract AI System",
  url: contractProductUrl,
  mainEntityOfPage: `${SEO_SITE_URL}/contract-ai-system`,
  applicationCategory: "BusinessApplication",
  operatingSystem: "Web",
  inLanguage: "ru-RU",
  description: "Сервис анализа, проверки, подготовки и согласования договоров с помощью ИИ.",
  sameAs: [EXTERNAL_LINKS.githubContractAI],
  featureList: [
    "Анализ условий и юридических рисков",
    "Рекомендации по правкам",
    "Сравнение версий договоров",
    "Протоколы разногласий",
  ],
  offers: {
    "@type": "Offer",
    name: "Бесплатный режим",
    price: "0",
    priceCurrency: "RUB",
    description: "До 3 договоров в месяц.",
  },
  provider: {
    "@type": "Organization",
    "@id": `${SEO_SITE_URL}/#organization`,
    name: "AI Verdict",
    url: SEO_SITE_URL,
  },
};

const valuePoints = [
  {
    title: "Скорость первичной проверки",
    details: "Система за минуты формирует первичный риск-профиль договора и подсвечивает спорные зоны.",
  },
  {
    title: "Предсказуемость качества",
    details: "Единая логика комментариев снижает разрыв между юристами и сокращает число возвратов на доработку.",
  },
  {
    title: "Контроль рисков",
    details: "Выявляются условия по ответственности, срокам, штрафам, расторжению и обязательствам сторон.",
  },
];

const taskTracks = [
  {
    title: "Что решаем для юристов",
    href: ROUTES.forLawyers,
    items: [
      "Ускоряем первичный анализ договора",
      "Упорядочиваем согласование правок",
      "Снижаем рутину на повторяющихся договорах",
    ],
  },
  {
    title: "Что решаем для бизнеса",
    href: ROUTES.forBusiness,
    items: [
      "Сокращаем цикл согласования сделки",
      "Делаем риски прозрачными для руководителей",
      "Стабилизируем сроки реакции юридической функции",
    ],
  },
];

const demoSteps = [
  "Начинаете с 3 бесплатных договоров в месяц и проверяете базовый сценарий.",
  "Получаете анализ рисков и примеры юридических комментариев/правок.",
  "Сверяем эффект на KPI и фиксируем сценарий пилотного внедрения.",
];

const integrationPoints = [
  "API-контур в рамках текущего ядра платформы",
  "Журнал решений и ручной контроль юриста",
  "Поэтапное расширение на соседние legal-процессы",
  "Поддержка внутренних регламентов и матриц ответственности",
];

const launchFormats = [
  "Бесплатный вход: 3 договора в месяц без оплаты, чтобы проверить интерфейс и формат отчета.",
  "Пилотный сценарий: ограниченный контур на ваших документах после бесплатной проверки.",
  "Рабочий контур: расширение на процесс согласования, роли, контроль качества и экспорт.",
  "Интеграции и масштабирование: отдельный следующий этап после подтвержденного пилота.",
];

export default function ContractAISystemPage() {
  const contractAIHref = contractAIEntryHref("demo");
  const contractAIExternal = contractAIEntryIsExternal();
  const ssoUrl = contractAISsoUrl();
  return (
    <main className="bg-slate-900 text-slate-100 min-h-screen">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(softwareSchema) }} />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(contractBreadcrumbSchema) }} />
      <section className="border-b border-slate-800">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 pt-28 pb-14">
          <span className="inline-flex rounded-full border border-emerald-500/40 bg-emerald-500/10 px-4 py-1 text-sm text-emerald-300">
            Флагманский продукт платформы
          </span>
          <h1 className="mt-5 text-4xl md:text-5xl font-semibold text-white leading-tight">
            Contract AI — анализ и проверка договоров с ИИ
          </h1>
          <p className="mt-5 max-w-3xl text-slate-300 text-lg leading-relaxed">
            Это флагманский внешний сервис проверки договоров. Через него удобно быстро проверить гипотезу на реальных
            документах: начать с 3 бесплатных договоров в месяц, увидеть риски, получить рекомендации по правкам
            и понять, стоит ли переходить к пилоту.
          </p>
          <div className="mt-8">
            <CtaFrameworkPanel
              leadStart="contract_demo"
              miniAppHref={ROUTES.miniAppTools}
              title="Маршрут Contract AI: Узнать -> Проверить -> Обсудить пилот"
              variant="validate-first"
            />
          </div>
          {contractAIExternal ? (
            <div className="mt-4 flex flex-wrap gap-3">
              <a
                href={contractAIHref}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex rounded-lg border border-emerald-500/50 bg-emerald-500/10 px-4 py-2 text-sm font-semibold text-emerald-200 hover:border-emerald-300"
              >
                Открыть сервис проверки договоров
              </a>
              {ssoUrl ? (
                <a
                  href={ssoUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex rounded-lg border border-sky-500/50 bg-sky-500/10 px-4 py-2 text-sm font-semibold text-sky-200 hover:border-sky-300"
                >
                  Войти через AI Verdict (SSO)
                </a>
              ) : null}
            </div>
          ) : null}
        </div>
      </section>

      <section className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-14">
        <h2 className="text-3xl font-semibold text-white">Ценность продукта</h2>
        <div className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-4">
          {valuePoints.map((item) => (
            <article key={item.title} className="rounded-xl border border-slate-800 bg-slate-800/60 p-6">
              <h3 className="text-lg font-semibold text-amber-300">{item.title}</h3>
              <p className="mt-3 text-sm text-slate-300 leading-relaxed">{item.details}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="border-y border-slate-800 bg-slate-800/40">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-14">
          <h2 className="text-3xl font-semibold text-white">Ключевые сценарии применения</h2>
          <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-4">
            {taskTracks.map((track) => (
              <article key={track.title} className="rounded-xl border border-slate-800 bg-slate-900/60 p-6">
                <h3 className="text-xl font-semibold text-amber-300">{track.title}</h3>
                <ul className="mt-3 space-y-2 text-sm text-slate-300 leading-relaxed">
                  {track.items.map((item) => (
                    <li key={item}>• {item}</li>
                  ))}
                </ul>
                <Link href={track.href} className="mt-5 inline-flex font-semibold text-sky-300 hover:text-sky-200">
                  Открыть подробный маршрут →
                </Link>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section id="demo" className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-14">
        <h2 className="text-3xl font-semibold text-white">Демо и пилот</h2>
        <p className="mt-4 max-w-3xl text-slate-300">
          Для старта не нужна тяжелая интеграция: сначала используем бесплатный лимит 3 договора в месяц,
          подтверждаем прикладной эффект и только потом масштабируем в рабочий контур.
        </p>
        <ol className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-4">
          {demoSteps.map((step) => (
            <li key={step} className="rounded-xl border border-slate-800 bg-slate-800/60 p-5 text-sm text-slate-200">
              {step}
            </li>
          ))}
        </ol>
        <div className="mt-8 grid gap-4 md:grid-cols-3">
          <Link href="/guides/ai-contract-review-process" className="rounded-xl border border-slate-700 bg-slate-950/60 p-5 hover:border-amber-500">
            <h3 className="font-semibold text-amber-300">Методика проверки договора →</h3>
            <p className="mt-2 text-sm leading-6 text-slate-300">Матрица рисков, контрольный набор, роль юриста и критерии качества.</p>
          </Link>
          <Link href="/legal-ai/roi" className="rounded-xl border border-slate-700 bg-slate-950/60 p-5 hover:border-amber-500">
            <h3 className="font-semibold text-amber-300">Рассчитать ROI пилота →</h3>
            <p className="mt-2 text-sm leading-6 text-slate-300">Интерактивный расчет времени, расходов, эффекта и срока окупаемости.</p>
          </Link>
          <Link href="/cases" className="rounded-xl border border-slate-700 bg-slate-950/60 p-5 hover:border-amber-500">
            <h3 className="font-semibold text-amber-300">Сценарии и метрики →</h3>
            <p className="mt-2 text-sm leading-6 text-slate-300">Как проектная модель превращается в подтвержденный кейс.</p>
          </Link>
        </div>
      </section>

      <section className="border-y border-slate-800 bg-slate-800/40">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-14">
          <h2 className="text-3xl font-semibold text-white">Как устроен запуск</h2>
          <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-4">
            {launchFormats.map((item) => (
              <article key={item} className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 text-slate-200">
                {item}
              </article>
            ))}
          </div>
        </div>
      </section>

      <section id="integrations" className="border-y border-slate-800 bg-slate-800/40">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-14">
          <h2 className="text-3xl font-semibold text-white">Интеграции и контроль</h2>
          <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-4">
            {integrationPoints.map((item) => (
              <article key={item} className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 text-slate-200">
                {item}
              </article>
            ))}
          </div>
          <p className="mt-6 text-sm leading-6 text-slate-400">
            Архитектура и история разработки представлены в{" "}
            <a
              href={EXTERNAL_LINKS.githubContractAI}
              target="_blank"
              rel="noopener noreferrer"
              className="font-semibold text-sky-300 hover:text-sky-200"
            >
              публичном репозитории Contract AI ↗
            </a>
            .
          </p>
        </div>
      </section>

      <section className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-14">
        <div className="rounded-2xl border border-amber-500/35 bg-amber-500/10 p-7">
          <h2 className="text-2xl font-semibold text-white">Следующий шаг</h2>
          <p className="mt-3 max-w-3xl text-slate-200">
            Если хотите разобрать ваш договорный процесс и проверить, где ИИ даст максимальный эффект, передайте кейс в
            Ассистент AI Verdict. Получите понятный формат пилота без лишней архитектурной сложности.
          </p>
          <div className="mt-6">
            <CtaFrameworkPanel
              leadStart="contract_consultation"
              miniAppHref={ROUTES.miniAppTools}
              title="Следующий шаг: Узнать -> Проверить -> Обсудить пилот"
              variant="consult-first"
            />
          </div>
        </div>
      </section>
      <PageFAQ items={contractFaqItems} pageUrl={`${SEO_SITE_URL}/contract-ai-system`} title="Частые вопросы о Contract AI" />
    </main>
  );
}
