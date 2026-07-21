import type { Metadata } from "next";
import Link from "next/link";

import HeroBackdrop from "@/components/HeroBackdrop";
import LegalHelpForm from "@/components/LegalHelpForm";
import LegalHelpTrust from "@/components/LegalHelpTrust";
import PageFAQ from "@/components/PageFAQ";
import { LEGAL_HELP_REVIEWED_AT, legalHelpPages } from "@/lib/legalHelpPages";
import { createPageMetadata, SEO_SITE_URL } from "@/lib/seo";
import { isLightOpsTheme } from "@/lib/visualTheme";

export const metadata: Metadata = createPageMetadata({
  title: "Юридические услуги для бизнеса и ИП",
  description:
    "Юридические услуги для компаний и предпринимателей: договоры, взыскание долгов, суды, корпоративные и трудовые вопросы, недвижимость и сопровождение бизнеса.",
  path: "/legal-help/business",
  keywords: [
    "юридические услуги для бизнеса",
    "юрист для бизнеса",
    "юрист для ИП",
    "юридическое сопровождение компании",
    "корпоративный юрист",
  ],
});

const directions = ["contracts", "corporate", "litigation", "debt-collection", "employment", "real-estate"]
  .map((slug) => legalHelpPages[slug]);

const faq = [
  {
    question: "Можно обратиться с одной задачей, а не за абонентским обслуживанием?",
    answer:
      "Да. Сначала можно согласовать отдельную проверку договора, претензию, корпоративный документ или судебную задачу. Регулярное сопровождение обсуждается только если оно действительно нужно бизнесу.",
  },
  {
    question: "Работаете с ИП и небольшими компаниями?",
    answer:
      "Да. Объём работы подбирается под задачу и фактический документооборот, без обязательного крупного пакета услуг.",
  },
  {
    question: "Как определяется стоимость юридической работы?",
    answer:
      "После первичного описания юрист уточняет документы, сроки, число участников и ожидаемый результат. Затем согласуются объём, формат, стоимость и возможные дополнительные этапы.",
  },
  {
    question: "Можно передать срочную задачу?",
    answer:
      "Укажите ближайший срок и событие в форме. Сначала проверим, возможно ли принять обращение и выполнить необходимый объём без потери качества; автоматического обещания срочного результата нет.",
  },
  {
    question: "Как используются AI-инструменты?",
    answer:
      "Они могут ускорять структурирование документов, поиск условий и подготовку рабочего материала. Юридическую позицию и итоговые рекомендации подтверждает человек.",
  },
];

export default function BusinessLegalHelpPage() {
  const canonicalUrl = `${SEO_SITE_URL}/legal-help/business`;
  const schema = {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "Service",
        "@id": `${canonicalUrl}#service`,
        name: "Юридические услуги для бизнеса",
        description: metadata.description,
        serviceType: "Юридическое сопровождение компаний и предпринимателей",
        provider: { "@id": `${SEO_SITE_URL}/#organization` },
        areaServed: { "@type": "Country", name: "Россия" },
        url: canonicalUrl,
      },
      {
        "@type": "WebPage",
        "@id": canonicalUrl,
        name: "Юридические услуги для бизнеса",
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
          { "@type": "ListItem", position: 3, name: "Услуги бизнесу", item: canonicalUrl },
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
            <Link href="/legal-help" className="hover:text-amber-300">Юридическая помощь</Link> / Бизнесу
          </nav>
          <p className="mt-8 text-sm font-semibold uppercase tracking-wide text-amber-300">Для компаний и предпринимателей</p>
          <h1 className="mt-3 max-w-5xl text-4xl font-semibold leading-tight text-white md:text-5xl">
            Юридические услуги для бизнеса и ИП
          </h1>
          <p className="mt-6 max-w-4xl text-lg leading-relaxed text-slate-200">
            Помогаем решать отдельные правовые задачи и выстраивать регулярное сопровождение: от договора и
            претензии до корпоративной процедуры, трудового вопроса или судебного спора. Работаем по
            законодательству РФ, формат и стоимость согласуем до начала юридической работы.
          </p>
          <a href="#legal-help-form" className="mt-8 inline-flex rounded-lg bg-amber-500 px-6 py-3 font-semibold text-slate-950 hover:bg-amber-400">
            Передать задачу юристу
          </a>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-14 sm:px-6 lg:px-8">
        <div className="max-w-4xl">
          <h2 className="text-3xl font-semibold text-white">Направления юридической помощи бизнесу</h2>
          <p className="mt-4 leading-7 text-slate-300">
            Необязательно самостоятельно выбирать отрасль права. Опишите факты и ближайший срок — обращение
            будет отнесено к нужному направлению после первичной проверки.
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
        <div className="mx-auto grid max-w-6xl gap-8 px-4 py-14 sm:px-6 lg:grid-cols-2 lg:px-8">
          <div>
            <h2 className="text-3xl font-semibold text-white">Разовая задача</h2>
            <p className="mt-4 leading-7 text-slate-300">
              Подходит, когда нужно проверить документ, подготовить претензию, оформить корпоративное решение,
              оценить спор или выполнить другой понятный объём. До старта фиксируем результат этапа, срок и цену.
            </p>
          </div>
          <div>
            <h2 className="text-3xl font-semibold text-white">Регулярное сопровождение</h2>
            <p className="mt-4 leading-7 text-slate-300">
              Для повторяющегося потока задач согласуем каналы обращений, приоритеты, сроки реакции, включённый
              объём и порядок эскалации. Абонентский формат предлагается только после понимания реальной нагрузки.
            </p>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-14 sm:px-6 lg:px-8">
        <h2 className="text-3xl font-semibold text-white">Порядок начала работы</h2>
        <ol className="mt-8 grid gap-5 md:grid-cols-2 lg:grid-cols-4">
          {[
            ["01", "Описание", "Вы сообщаете суть задачи, участников и ближайший срок без загрузки чувствительных документов."],
            ["02", "Проверка", "Юрист уточняет факты, возможность принять задачу и необходимый комплект материалов."],
            ["03", "Предложение", "Согласуем объём, формат результата, сроки, стоимость и границы поручения."],
            ["04", "Работа", "После подтверждения условий безопасно получаем документы и выполняем согласованный этап."],
          ].map(([num, title, text]) => (
            <li key={num} className="rounded-xl border border-slate-700 bg-slate-800/60 p-6">
              <span className="text-sm font-bold text-amber-300">{num}</span>
              <h3 className="mt-3 text-xl font-semibold text-white">{title}</h3>
              <p className="mt-3 text-sm leading-6 text-slate-300">{text}</p>
            </li>
          ))}
        </ol>
      </section>

      <LegalHelpTrust />
      <PageFAQ items={faq} pageUrl={canonicalUrl} title="Частые вопросы о юридических услугах для бизнеса" />
      <LegalHelpForm sourceContext="web_legal_help_business" initialClientType="company" />
    </main>
  );
}
