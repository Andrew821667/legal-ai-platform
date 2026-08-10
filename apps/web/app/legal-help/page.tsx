import type { Metadata } from "next";
import Link from "next/link";
import { Building2, FileText, Landmark, MessageCircle, Scale, ShieldCheck, UserRound } from "lucide-react";

import HeroBackdrop from "@/components/HeroBackdrop";
import LegalHelpCommercialFacts from "@/components/LegalHelpCommercialFacts";
import LegalHelpForm from "@/components/LegalHelpForm";
import LegalHelpTrust from "@/components/LegalHelpTrust";
import PageFAQ from "@/components/PageFAQ";
import { createPageMetadata, SEO_SITE_URL } from "@/lib/seo";
import { isLightOpsTheme } from "@/lib/visualTheme";

export const metadata: Metadata = createPageMetadata({
  title: "Юридические услуги для бизнеса и частных лиц",
  description:
    "Юридические услуги AI Verdict для бизнеса и частных лиц: консультации, договоры, судебные споры, недвижимость, семейные, наследственные и трудовые вопросы.",
  path: "/legal-help",
  socialImage: "/legal-help/opengraph-image",
  keywords: ["юридическая помощь", "юридические услуги", "юрист для бизнеса", "консультация юриста"],
});

const areas = [
  { icon: MessageCircle, href: "/legal-help/online-consultation", title: "Консультация юриста онлайн", text: "Разбор ситуации, документов, сроков и вариантов дальнейших действий." },
  { icon: FileText, href: "/legal-help/contracts", title: "Договоры и сделки", text: "Проверка, подготовка, переговоры и сопровождение исполнения." },
  { icon: Scale, href: "/legal-help/litigation", title: "Судебные споры", text: "Оценка перспектив, претензии, процессуальные документы и представительство." },
  { icon: Building2, href: "/legal-help/corporate", title: "Корпоративные вопросы", text: "Решения участников, полномочия, внутренние документы и сделки бизнеса." },
  { icon: Landmark, href: "/legal-help/real-estate", title: "Недвижимость и земля", text: "Проверка сделок, регистрационные вопросы и имущественные споры." },
  { icon: UserRound, href: "/legal-help/family", title: "Семейные дела", text: "Развод, дети, алименты, раздел имущества и соглашения." },
  { icon: ShieldCheck, href: "/legal-help/inheritance", title: "Наследство", text: "Оформление прав, сроки, завещания, доли и наследственные споры." },
  { icon: Scale, href: "/legal-help/debt-collection", title: "Взыскание долгов", text: "Претензия, суд, расчёт задолженности и исполнительный этап." },
  { icon: Building2, href: "/legal-help/employment", title: "Трудовые вопросы", text: "Документы, процедуры, выплаты, увольнение и трудовые споры." },
];

const legalHelpFaqItems = [
  {
    question: "Как получить юридическую помощь в AI Verdict?",
    answer:
      "Опишите задачу, укажите ближайший срок и оставьте контакт через форму на этой странице. Юрист изучит обращение и предложит понятный следующий шаг, а работа начинается только после согласования формата и стоимости.",
  },
  {
    question: "С какими задачами вы работаете?",
    answer:
      "Договоры и сделки, претензии и споры, корпоративные и трудовые вопросы, налоги и комплаенс, недвижимость и земля, IT и персональные данные, а также личные юридические ситуации.",
  },
  {
    question: "Вы помогаете только бизнесу?",
    answer:
      "Нет, работаем и с компаниями, и с частными клиентами. У каждого направления есть отдельная страница с деталями: юридические услуги для бизнеса и помощь частным лицам.",
  },
  {
    question: "Чем ваш подход отличается от обычной юридической фирмы?",
    answer:
      "Мы совмещаем юридическую практику с технологиями AI Verdict: рутинные этапы ускоряет автоматизация, а решения по существу принимает юрист.",
  },
];

export default function LegalHelpPage() {
  const canonicalUrl = `${SEO_SITE_URL}/legal-help`;
  const schema = {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "Service",
        "@id": `${canonicalUrl}#service`,
        name: "Юридическая практика AI Verdict",
        description:
          "Юридические услуги по российскому праву для бизнеса и частных клиентов в дистанционном формате по России.",
        serviceType: "Юридические услуги по праву Российской Федерации",
        category: ["Консультации", "Договоры", "Судебные споры", "Корпоративные и частные правовые вопросы"],
        provider: { "@id": `${SEO_SITE_URL}/#organization` },
        areaServed: { "@type": "Country", name: "Россия" },
        url: canonicalUrl,
        audience: {
          "@type": "Audience",
          audienceType: "Компании, предприниматели и частные клиенты",
        },
        availableChannel: {
          "@type": "ServiceChannel",
          serviceUrl: canonicalUrl,
          availableLanguage: "ru-RU",
        },
        hasOfferCatalog: {
          "@type": "OfferCatalog",
          name: "Направления юридической помощи",
          itemListElement: areas.map((area) => ({
            "@type": "Offer",
            itemOffered: {
              "@type": "Service",
              name: area.title,
              url: `${SEO_SITE_URL}${area.href}`,
            },
          })),
        },
      },
      {
        "@type": "WebPage",
        "@id": canonicalUrl,
        name: "Юридические услуги для бизнеса и частных клиентов",
        dateModified: "2026-08-05",
        url: canonicalUrl,
        inLanguage: "ru-RU",
        mainEntity: { "@id": `${canonicalUrl}#service` },
      },
      {
        "@type": "BreadcrumbList",
        "@id": `${canonicalUrl}#breadcrumb`,
        itemListElement: [
          { "@type": "ListItem", position: 1, name: "Главная", item: SEO_SITE_URL },
          { "@type": "ListItem", position: 2, name: "Юридическая помощь", item: canonicalUrl },
        ],
      },
    ],
  };

  return (
    <main className={`${isLightOpsTheme ? "visual-light-ops" : ""} min-h-screen bg-slate-900 text-slate-100`}>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(schema) }} />

      <section className="relative flex min-h-[660px] items-start overflow-hidden border-b border-slate-800 sm:min-h-[540px] sm:items-center">
        <HeroBackdrop variant="legal" tone="light" priority />
        <div className="relative mx-auto w-full max-w-7xl px-4 pb-12 pt-24 sm:px-6 sm:py-28 lg:px-8">
          <p className="text-sm font-semibold text-amber-300">Юридическое направление AI Verdict</p>
          <h1 className="mt-4 max-w-4xl text-4xl font-semibold leading-tight text-white md:text-5xl">
            Юридические услуги для бизнеса и частных клиентов
          </h1>
          <p className="mt-5 max-w-3xl text-lg leading-relaxed text-slate-300">
            Мы не только разрабатываем юридические технологии, но и работаем с правом на практике. Опишите задачу,
            ближайший срок и оставьте контакт. Юрист изучит обращение и предложит консультацию или другой
            понятный следующий шаг в дистанционном формате по России.
          </p>
          <div className="mt-8 flex flex-col items-start gap-4 sm:flex-row sm:items-center">
            <a href="#legal-help-form" className="w-full rounded-lg bg-amber-500 px-6 py-3 text-center font-semibold text-slate-950 hover:bg-amber-400 sm:w-auto">
              Описать задачу
            </a>
            <div className="flex flex-wrap gap-x-5 gap-y-2 text-sm font-semibold">
              <Link href="/legal-help/business" className="text-slate-700 underline decoration-amber-500/60 underline-offset-4 hover:text-amber-700">
                Помощь бизнесу →
              </Link>
              <Link href="/legal-help/individuals" className="text-slate-700 underline decoration-amber-500/60 underline-offset-4 hover:text-amber-700">
                Частным клиентам →
              </Link>
            </div>
          </div>
        </div>
      </section>

      <section className="border-b border-slate-800 bg-slate-900">
        <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
          <div className="max-w-4xl rounded-xl border border-sky-200 bg-white p-7">
            <p className="text-sm font-semibold uppercase tracking-wide text-sky-800">Короткий ответ</p>
            <h2 className="mt-2 text-2xl font-semibold text-slate-900">Что делает юридическая практика AI Verdict</h2>
            <p className="mt-4 leading-7 text-slate-700">
              Юридическая практика AI Verdict оказывает дистанционные юридические услуги по российскому праву
              компаниям, предпринимателям и частным клиентам. Юрист разбирает обстоятельства и документы,
              согласует формат, срок и стоимость работы, а AI используется только как вспомогательный инструмент
              для структурирования информации и подготовки материалов.
            </p>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8">
        <div className="max-w-3xl">
          <h2 className="text-3xl font-semibold text-white">С какими задачами можно обратиться</h2>
          <p className="mt-3 text-slate-300">Необязательно самостоятельно определять отрасль права. Достаточно описать ситуацию своими словами.</p>
        </div>
        <div className="mt-8 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {areas.map((area) => (
            <Link key={area.title} href={area.href} className="rounded-lg border border-slate-800 bg-slate-800/60 p-6 hover:border-amber-400">
              <area.icon className="h-6 w-6 text-amber-300" />
              <h3 className="mt-4 text-lg font-semibold text-white">{area.title} →</h3>
              <p className="mt-2 text-sm leading-relaxed text-slate-300">{area.text}</p>
            </Link>
          ))}
        </div>
        <div className="mt-8 rounded-xl border border-slate-700 bg-slate-800/40 p-6">
          <h2 className="text-xl font-semibold text-white">Юридическая помощь по регионам России</h2>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-300">
            Дистанционно разбираем задачи клиентов из разных регионов и отдельно проверяем подсудность,
            способы подачи документов и необходимость очного участия.
          </p>
          <Link href="/legal-help/regions" className="mt-4 inline-flex font-semibold text-amber-300 hover:text-amber-200">
            Открыть региональные направления →
          </Link>
        </div>
      </section>

      <section className="border-y border-slate-800 bg-slate-800/40">
        <div className="mx-auto grid max-w-7xl gap-8 px-4 py-16 sm:px-6 lg:grid-cols-3 lg:px-8">
          <div>
            <p className="text-sm font-semibold text-amber-300">1. Обращение</p>
            <h2 className="mt-2 text-xl font-semibold text-white">Вы описываете задачу</h2>
            <p className="mt-3 text-sm text-slate-300">Без регистрации, загрузки документов и сложной анкеты.</p>
          </div>
          <div>
            <p className="text-sm font-semibold text-amber-300">2. Проверка</p>
            <h2 className="mt-2 text-xl font-semibold text-white">Юрист уточняет обстоятельства</h2>
            <p className="mt-3 text-sm text-slate-300">Проверяем сроки, возможность принять задачу и необходимый объём работы.</p>
          </div>
          <div>
            <p className="text-sm font-semibold text-amber-300">3. Условия</p>
            <h2 className="mt-2 text-xl font-semibold text-white">Согласовываем формат и стоимость</h2>
            <p className="mt-3 text-sm text-slate-300">Юридическая работа начинается только после согласования условий.</p>
          </div>
        </div>
      </section>

      <LegalHelpCommercialFacts />

      <LegalHelpTrust />

      <PageFAQ items={legalHelpFaqItems} pageUrl={canonicalUrl} title="Частые вопросы о юридической помощи" />

      <LegalHelpForm sourceContext="web_legal_help" />
    </main>
  );
}
