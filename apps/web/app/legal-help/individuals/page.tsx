import type { Metadata } from "next";
import Link from "next/link";

import HeroBackdrop from "@/components/HeroBackdrop";
import LegalHelpCommercialFacts from "@/components/LegalHelpCommercialFacts";
import LegalHelpForm from "@/components/LegalHelpForm";
import LegalHelpTrust from "@/components/LegalHelpTrust";
import PageFAQ from "@/components/PageFAQ";
import { LEGAL_HELP_REVIEWED_AT, legalHelpPages } from "@/lib/legalHelpPages";
import { createPageMetadata, SEO_SITE_URL } from "@/lib/seo";
import { isLightOpsTheme } from "@/lib/visualTheme";

export const metadata: Metadata = createPageMetadata({
  title: "Юридические услуги для частных лиц",
  description:
    "Юридическая помощь частным лицам: семейные и наследственные дела, недвижимость, договоры, долги, трудовые вопросы и судебные споры.",
  path: "/legal-help/individuals",
  keywords: [
    "юридическая помощь частным лицам",
    "юрист для физических лиц",
    "помощь юриста",
    "юридические услуги физическим лицам",
  ],
});

const directions = ["online-consultation", "family", "inheritance", "real-estate", "contracts", "debt-collection", "litigation", "employment"]
  .map((slug) => legalHelpPages[slug]);

const faq = [
  {
    question: "Первичное обращение бесплатно?",
    answer:
      "Передача описания и проверка возможности принять задачу не являются консультацией и не оплачиваются. Юридический анализ, подготовка документов и представительство начинаются после согласования объёма и стоимости.",
  },
  {
    question: "Нужно сразу отправлять документы?",
    answer:
      "Нет. В первичной форме достаточно описать ситуацию и срок. Не указывайте полные паспортные данные и банковские реквизиты. Безопасный способ передачи документов согласуем отдельно.",
  },
  {
    question: "Можно получить помощь дистанционно?",
    answer:
      "Первичное обсуждение, анализ и подготовка документов часто возможны дистанционно. Необходимость личного участия зависит от задачи, региона, суда, нотариуса или другого органа.",
  },
  {
    question: "Вы гарантируете результат дела?",
    answer:
      "Нет. Юрист может оценить документы, риски и варианты действий, но решение суда, нотариуса или государственного органа нельзя гарантировать.",
  },
  {
    question: "Что делать, если срок истекает сегодня?",
    answer:
      "Укажите точную дату и событие в форме, но при угрозе жизни, насилии или иной экстренной ситуации обращайтесь в соответствующие службы немедленно, не ожидая ответа сайта.",
  },
];

export default function IndividualLegalHelpPage() {
  const canonicalUrl = `${SEO_SITE_URL}/legal-help/individuals`;
  const schema = {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "Service",
        "@id": `${canonicalUrl}#service`,
        name: "Юридические услуги для частных лиц",
        description: metadata.description,
        serviceType: "Юридические услуги для физических лиц",
        provider: { "@id": `${SEO_SITE_URL}/#organization` },
        audience: { "@type": "PeopleAudience", audienceType: "Частные лица" },
        areaServed: { "@type": "Country", name: "Россия" },
        url: canonicalUrl,
      },
      {
        "@type": "WebPage",
        "@id": canonicalUrl,
        name: "Юридические услуги для частных лиц",
        dateModified: LEGAL_HELP_REVIEWED_AT,
        inLanguage: "ru-RU",
        mainEntity: { "@id": `${canonicalUrl}#service` },
      },
      {
        "@type": "BreadcrumbList",
        "@id": `${canonicalUrl}#breadcrumb`,
        itemListElement: [
          { "@type": "ListItem", position: 1, name: "Главная", item: SEO_SITE_URL },
          { "@type": "ListItem", position: 2, name: "Юридическая помощь", item: `${SEO_SITE_URL}/legal-help` },
          { "@type": "ListItem", position: 3, name: "Частным лицам", item: canonicalUrl },
        ],
      },
    ],
  };

  return (
    <main className={`${isLightOpsTheme ? "visual-light-ops" : ""} min-h-screen bg-slate-900 text-slate-100`}>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(schema) }} />

      <section className="relative overflow-hidden border-b border-slate-700">
        <HeroBackdrop variant="services" tone="light" />
        <div className="relative mx-auto max-w-6xl px-4 pb-16 pt-28 sm:px-6 lg:px-8">
          <nav aria-label="Хлебные крошки" className="text-sm text-slate-300">
            <Link href="/legal-help" className="hover:text-amber-300">Юридическая помощь</Link> / Частным лицам
          </nav>
          <p className="mt-8 text-sm font-semibold uppercase tracking-wide text-amber-300">Для частных клиентов</p>
          <h1 className="mt-3 max-w-5xl text-4xl font-semibold leading-tight text-white md:text-5xl">
            Юридические услуги для частных лиц
          </h1>
          <p className="mt-6 max-w-4xl text-lg leading-relaxed text-slate-200">
            Опишите ситуацию обычными словами — самостоятельно определять отрасль права не нужно. Юрист уточнит
            факты и срок, проверит возможность принять задачу и до начала работы согласует понятный объём и стоимость.
          </p>
          <a href="#legal-help-form" className="mt-8 inline-flex rounded-lg bg-amber-500 px-6 py-3 font-semibold text-slate-950 hover:bg-amber-400">
            Описать ситуацию
          </a>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-14 sm:px-6 lg:px-8">
        <div className="max-w-4xl">
          <h2 className="text-3xl font-semibold text-white">С какими вопросами можно обратиться</h2>
          <p className="mt-4 leading-7 text-slate-300">
            На отдельных страницах указан типовой порядок работы. Он помогает сориентироваться, но не является
            готовой консультацией: вывод зависит от документов, дат и обстоятельств именно вашей ситуации.
          </p>
        </div>
        <div className="mt-8 grid gap-5 md:grid-cols-2 lg:grid-cols-3">
          {directions.map((item) => (
            <Link key={item.slug} href={`/legal-help/${item.slug}`} className="rounded-xl border border-slate-700 bg-slate-800/60 p-6 hover:border-amber-400">
              <h3 className="text-xl font-semibold text-amber-300">{item.eyebrow} →</h3>
              <p className="mt-3 text-sm leading-6 text-slate-300">{item.description}</p>
            </Link>
          ))}
        </div>
      </section>

      <section className="border-y border-slate-700 bg-slate-800/40">
        <div className="mx-auto max-w-6xl px-4 py-14 sm:px-6 lg:px-8">
          <h2 className="text-3xl font-semibold text-white">Что происходит после обращения</h2>
          <div className="mt-8 grid gap-5 md:grid-cols-3">
            <article className="rounded-xl border border-slate-700 bg-slate-900/50 p-6">
              <p className="text-sm font-semibold text-amber-300">1. Первичная проверка</p>
              <p className="mt-3 leading-6 text-slate-300">Уточняем суть, сроки и наличие конфликта интересов. Это ещё не юридическая консультация и не принятие дела.</p>
            </article>
            <article className="rounded-xl border border-slate-700 bg-slate-900/50 p-6">
              <p className="text-sm font-semibold text-amber-300">2. Предложение</p>
              <p className="mt-3 leading-6 text-slate-300">Объясняем, какие документы нужны, какой этап можно выполнить, сколько он займёт и сколько будет стоить.</p>
            </article>
            <article className="rounded-xl border border-slate-700 bg-slate-900/50 p-6">
              <p className="text-sm font-semibold text-amber-300">3. Юридическая работа</p>
              <p className="mt-3 leading-6 text-slate-300">После согласования безопасно получаем материалы, выполняем поручение и сообщаем о следующих действиях.</p>
            </article>
          </div>
        </div>
      </section>

      <LegalHelpCommercialFacts />

      <LegalHelpTrust />
      <PageFAQ items={faq} pageUrl={canonicalUrl} title="Частые вопросы о юридической помощи частным лицам" />
      <LegalHelpForm sourceContext="web_legal_help_individuals" initialClientType="individual" />
    </main>
  );
}
