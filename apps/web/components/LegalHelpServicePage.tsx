import Link from "next/link";

import HeroBackdrop from "@/components/HeroBackdrop";
import LegalHelpCommercialFacts from "@/components/LegalHelpCommercialFacts";
import LegalHelpForm from "@/components/LegalHelpForm";
import LegalHelpTrust from "@/components/LegalHelpTrust";
import PageFAQ from "@/components/PageFAQ";
import StarterOfferButton from "@/components/StarterOfferButton";
import { LEGAL_OPERATOR_NAME, LEGAL_SITE_URL } from "@/lib/legalProfile";
import {
  LEGAL_HELP_REVIEWED_AT,
  legalHelpPages,
  type LegalHelpPage,
} from "@/lib/legalHelpPages";
import { getStarterOffer } from "@/lib/starter-offers";
import { isLightOpsTheme } from "@/lib/visualTheme";

export default function LegalHelpServicePage({ page }: { page: LegalHelpPage }) {
  const baseUrl = LEGAL_SITE_URL.replace(/\/$/, "");
  const canonicalUrl = `${baseUrl}/legal-help/${page.slug}`;
  const featuredOffer = getStarterOffer(page.featuredOfferId, "legal");
  const featuredOfferLabel = page.featuredOfferId === "legal_contract_review"
    ? "Заказать проверку"
    : "Заказать документ";
  const structuredData = {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "Service",
        "@id": `${canonicalUrl}#service`,
        name: page.title,
        description: page.description,
        serviceType: page.eyebrow,
        url: canonicalUrl,
        areaServed: { "@type": "Country", name: "Россия" },
        provider: { "@id": `${baseUrl}/#organization` },
        termsOfService: `${baseUrl}/terms`,
        availableChannel: {
          "@type": "ServiceChannel",
          serviceUrl: canonicalUrl,
          availableLanguage: "ru-RU",
        },
        ...(featuredOffer ? {
          offers: {
            "@type": "AggregateOffer",
            lowPrice: featuredOffer.price.replace(/\D/g, ""),
            priceCurrency: "RUB",
            offerCount: 1,
            url: canonicalUrl,
          },
        } : {}),
      },
      {
        "@type": "WebPage",
        "@id": canonicalUrl,
        name: page.title,
        description: page.description,
        inLanguage: "ru-RU",
        dateModified: LEGAL_HELP_REVIEWED_AT,
        mainEntity: { "@id": `${canonicalUrl}#service` },
        reviewedBy: {
          "@type": "Person",
          "@id": `${baseUrl}/#founder`,
          name: LEGAL_OPERATOR_NAME,
          url: `${baseUrl}/team`,
        },
        publisher: { "@id": `${baseUrl}/#organization` },
      },
      {
        "@type": "BreadcrumbList",
        "@id": `${canonicalUrl}#breadcrumb`,
        itemListElement: [
          { "@type": "ListItem", position: 1, name: "Главная", item: baseUrl },
          { "@type": "ListItem", position: 2, name: "Юридическая помощь", item: `${baseUrl}/legal-help` },
          { "@type": "ListItem", position: 3, name: page.eyebrow, item: canonicalUrl },
        ],
      },
    ],
  };

  return (
    <main className={`${isLightOpsTheme ? "visual-light-ops" : ""} min-h-screen bg-slate-900 text-slate-100`}>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(structuredData) }} />

      <section className="relative overflow-hidden border-b border-slate-700">
        <HeroBackdrop variant="services" tone="light" />
        <div className="relative mx-auto max-w-6xl px-4 pb-16 pt-28 sm:px-6 lg:px-8 lg:pb-20 lg:pt-32">
          <nav aria-label="Хлебные крошки" className="text-sm text-slate-300">
            <Link href="/legal-help" className="hover:text-amber-300">Юридическая помощь</Link>
            <span aria-hidden="true"> / </span>
            <span>{page.eyebrow}</span>
          </nav>
          <p className="mt-8 text-sm font-semibold uppercase tracking-wide text-amber-300">{page.eyebrow}</p>
          <h1 className="mt-3 max-w-5xl text-4xl font-semibold leading-tight text-white md:text-5xl">
            {page.title}
          </h1>
          <p className="mt-6 max-w-4xl text-lg leading-relaxed text-slate-200">{page.intro}</p>
          {featuredOffer ? (
            <div className="mt-7 max-w-4xl rounded-2xl border border-amber-400/40 bg-slate-950/60 p-5 backdrop-blur-sm sm:flex sm:items-center sm:justify-between sm:gap-6">
              <div>
                <p className="text-sm font-semibold text-amber-300">{featuredOffer.title}</p>
                <p className="mt-1 text-2xl font-bold text-white">{featuredOffer.price}</p>
                <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-200">{featuredOffer.description}</p>
              </div>
              <StarterOfferButton
                offerId={featuredOffer.id}
                targetId="legal-help-form"
                label={featuredOfferLabel}
                className="mt-5 inline-flex w-full shrink-0 justify-center rounded-lg bg-amber-500 px-5 py-3 text-sm font-semibold text-slate-950 hover:bg-amber-400 sm:mt-0 sm:w-auto"
              />
            </div>
          ) : null}
          <div className="mt-8 flex flex-col gap-3 sm:flex-row">
            <a href="#legal-help-form" className="rounded-lg bg-amber-500 px-6 py-3 text-center font-semibold text-slate-950 hover:bg-amber-400">
              Описать ситуацию
            </a>
            <a href="#work-scope" className="rounded-lg border border-slate-600 bg-slate-900/20 px-6 py-3 text-center font-semibold text-white hover:border-amber-400 hover:text-amber-200">
              Что входит в работу
            </a>
          </div>
        </div>
      </section>

      {page.example ? (
        <section className="border-y border-slate-700 bg-slate-950/60">
          <div className="mx-auto max-w-6xl px-4 py-14 sm:px-6 lg:px-8">
            <p className="text-sm font-semibold uppercase tracking-wide text-amber-300">{page.example.eyebrow}</p>
            <h2 className="mt-2 text-3xl font-semibold text-white">{page.example.title}</h2>
            <p className="mt-4 max-w-4xl leading-7 text-slate-300">{page.example.description}</p>
            <div className="mt-8 grid gap-5 lg:grid-cols-3">
              {page.example.items.map((item, index) => (
                <article key={item.title} className="rounded-2xl border border-slate-700 bg-slate-900 p-6">
                  <span className="text-sm font-bold text-amber-300">0{index + 1}</span>
                  <h3 className="mt-3 text-xl font-semibold text-white">{item.title}</h3>
                  <p className="mt-3 text-sm leading-6 text-slate-300">{item.description}</p>
                </article>
              ))}
            </div>
            <p className="mt-5 text-sm leading-6 text-slate-400">{page.example.note}</p>
          </div>
        </section>
      ) : null}

      <section className="mx-auto max-w-6xl px-4 py-14 sm:px-6 lg:px-8">
        <div className="grid gap-6 lg:grid-cols-[1.25fr_0.75fr]">
          <article className="rounded-2xl border border-slate-700 bg-slate-800/60 p-7 md:p-9">
            <h2 className="text-3xl font-semibold text-white">Что важно в такой задаче</h2>
            <div className="mt-5 space-y-4 leading-7 text-slate-300">
              {page.context.map((paragraph) => <p key={paragraph}>{paragraph}</p>)}
            </div>
          </article>
          <aside className="rounded-2xl border border-amber-500/30 bg-amber-500/10 p-7 md:p-9">
            <h2 className="text-2xl font-semibold text-white">Когда стоит обратиться</h2>
            <ul className="mt-5 space-y-3 text-sm leading-6 text-slate-200">
              {page.situations.map((item) => <li key={item} className="flex gap-3"><span aria-hidden="true" className="text-amber-300">•</span><span>{item}</span></li>)}
            </ul>
          </aside>
        </div>
      </section>

      <section id="work-scope" className="border-y border-slate-700 bg-slate-800/40">
        <div className="mx-auto grid max-w-6xl gap-8 px-4 py-14 sm:px-6 lg:grid-cols-2 lg:px-8">
          <div>
            <h2 className="text-3xl font-semibold text-white">Что может входить в работу</h2>
            <ul className="mt-6 space-y-3 text-slate-300">
              {page.services.map((item) => <li key={item} className="flex gap-3"><span aria-hidden="true" className="text-emerald-400">✓</span><span>{item}</span></li>)}
            </ul>
          </div>
          <div>
            <h2 className="text-3xl font-semibold text-white">Что подготовить</h2>
            <p className="mt-3 text-sm leading-6 text-slate-400">Не загружайте документы в первичную форму. После проверки возможности принять задачу согласуем безопасный способ передачи.</p>
            <ul className="mt-6 space-y-3 text-slate-300">
              {page.preparation.map((item) => <li key={item} className="flex gap-3"><span aria-hidden="true" className="text-amber-300">→</span><span>{item}</span></li>)}
            </ul>
          </div>
        </div>
      </section>

      <LegalHelpCommercialFacts />

      <section className="mx-auto max-w-6xl px-4 py-14 sm:px-6 lg:px-8">
        <h2 className="text-3xl font-semibold text-white">Как проходит работа</h2>
        <p className="mt-4 max-w-3xl leading-relaxed text-slate-300">
          Формат, срок и стоимость согласуются после первичного изучения. Обращение через форму не означает
          автоматического принятия поручения.
        </p>
        <ol className="mt-8 grid gap-5 md:grid-cols-2 xl:grid-cols-4">
          {page.workflow.map((step, index) => (
            <li key={step.title} className="rounded-xl border border-slate-700 bg-slate-800/60 p-6">
              <span className="text-sm font-bold text-amber-300">0{index + 1}</span>
              <h3 className="mt-3 text-xl font-semibold text-white">{step.title}</h3>
              <p className="mt-3 text-sm leading-6 text-slate-300">{step.description}</p>
            </li>
          ))}
        </ol>
      </section>

      <section className="border-y border-slate-700 bg-slate-800/40">
        <div className="mx-auto grid max-w-6xl gap-6 px-4 py-14 sm:px-6 lg:grid-cols-2 lg:px-8">
          <div className="rounded-2xl border border-slate-700 bg-slate-900/50 p-7 md:p-9">
            <h2 className="text-2xl font-semibold text-white">Что получает клиент</h2>
            <ul className="mt-5 space-y-3 text-slate-300">
              {page.deliverables.map((item) => <li key={item} className="flex gap-3"><span aria-hidden="true" className="text-emerald-400">✓</span><span>{item}</span></li>)}
            </ul>
          </div>
          <div className="rounded-2xl border border-amber-500/30 bg-amber-500/10 p-7 md:p-9">
            <h2 className="text-2xl font-semibold text-white">Границы и честные ожидания</h2>
            <ul className="mt-5 space-y-3 text-slate-200">
              {page.boundaries.map((item) => <li key={item} className="flex gap-3"><span aria-hidden="true" className="text-amber-300">!</span><span>{item}</span></li>)}
            </ul>
          </div>
        </div>
      </section>

      <LegalHelpTrust />

      <PageFAQ items={page.faq} pageUrl={canonicalUrl} title={`Частые вопросы: ${page.eyebrow.toLowerCase()}`} />

      <section className="mx-auto max-w-6xl px-4 py-14 sm:px-6 lg:px-8">
        <h2 className="text-3xl font-semibold text-white">Связанные юридические услуги</h2>
        <div className="mt-7 grid gap-4 md:grid-cols-3">
          {page.related.map((slug) => {
            const relatedPage = legalHelpPages[slug];
            if (!relatedPage) return null;
            return (
              <Link key={slug} href={`/legal-help/${slug}`} className="rounded-xl border border-slate-700 bg-slate-800/60 p-6 hover:border-amber-400">
                <h3 className="font-semibold text-amber-300">{relatedPage.eyebrow} →</h3>
                <p className="mt-3 text-sm leading-6 text-slate-300">{relatedPage.description}</p>
              </Link>
            );
          })}
        </div>
        <div className="mt-7 flex flex-wrap gap-4 text-sm">
          <Link href="/legal-help/business" className="text-amber-300 hover:text-amber-200">Все услуги бизнесу →</Link>
          <Link href="/legal-help/individuals" className="text-amber-300 hover:text-amber-200">Помощь частным лицам →</Link>
        </div>
      </section>

      <LegalHelpForm
        sourceContext={`web_legal_help_${page.slug.replaceAll("-", "_")}`}
        initialClientType={page.clientType}
        initialArea={page.area}
      />
    </main>
  );
}
