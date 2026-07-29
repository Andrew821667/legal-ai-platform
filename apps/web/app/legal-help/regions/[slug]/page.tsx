import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import HeroBackdrop from "@/components/HeroBackdrop";
import LegalHelpCommercialFacts from "@/components/LegalHelpCommercialFacts";
import LegalHelpForm from "@/components/LegalHelpForm";
import LegalHelpTrust from "@/components/LegalHelpTrust";
import PageFAQ from "@/components/PageFAQ";
import { LEGAL_HELP_REVIEWED_AT } from "@/lib/legalHelpPages";
import { getLegalHelpRegion, legalHelpRegionList } from "@/lib/legalHelpRegions";
import { createPageMetadata, SEO_SITE_URL } from "@/lib/seo";
import { isLightOpsTheme } from "@/lib/visualTheme";

type RegionPageProps = {
  params: Promise<{ slug: string }>;
};

const services = [
  { href: "/legal-help/online-consultation", title: "Консультация юриста онлайн" },
  { href: "/legal-help/contracts", title: "Договоры и сделки" },
  { href: "/legal-help/litigation", title: "Судебные споры" },
  { href: "/legal-help/real-estate", title: "Недвижимость и земля" },
  { href: "/legal-help/family", title: "Семейные дела" },
  { href: "/legal-help/inheritance", title: "Наследство" },
  { href: "/legal-help/debt-collection", title: "Взыскание долгов" },
  { href: "/legal-help/employment", title: "Трудовые вопросы" },
];

export const dynamicParams = false;

export function generateStaticParams() {
  return legalHelpRegionList.map((region) => ({ slug: region.slug }));
}

export async function generateMetadata({ params }: RegionPageProps): Promise<Metadata> {
  const { slug } = await params;
  const region = getLegalHelpRegion(slug);
  if (!region) {
    return { title: "Регион не найден", robots: { index: false, follow: false } };
  }

  return createPageMetadata({
    title: region.seoTitle,
    description: region.description,
    path: `/legal-help/regions/${region.slug}`,
    keywords: [
      `юридическая помощь ${region.name}`,
      `юрист ${region.name}`,
      `юридические услуги ${region.name}`,
      `онлайн юрист ${region.name}`,
    ],
  });
}

export default async function LegalHelpRegionPage({ params }: RegionPageProps) {
  const { slug } = await params;
  const region = getLegalHelpRegion(slug);
  if (!region) notFound();

  const canonicalUrl = `${SEO_SITE_URL}/legal-help/regions/${region.slug}`;
  const schema = {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "Service",
        "@id": `${canonicalUrl}#service`,
        name: `Юридическая помощь в ${region.prepositionalName}`,
        description: region.description,
        serviceType: "Дистанционные юридические услуги",
        provider: { "@id": `${SEO_SITE_URL}/#organization` },
        areaServed: { "@type": "City", name: region.name },
        availableChannel: {
          "@type": "ServiceChannel",
          serviceUrl: canonicalUrl,
          availableLanguage: "ru-RU",
        },
        url: canonicalUrl,
      },
      {
        "@type": "WebPage",
        "@id": canonicalUrl,
        name: region.seoTitle,
        description: region.description,
        dateModified: LEGAL_HELP_REVIEWED_AT,
        inLanguage: "ru-RU",
        mainEntity: { "@id": `${canonicalUrl}#service` },
        publisher: { "@id": `${SEO_SITE_URL}/#organization` },
      },
      {
        "@type": "BreadcrumbList",
        "@id": `${canonicalUrl}#breadcrumb`,
        itemListElement: [
          { "@type": "ListItem", position: 1, name: "Главная", item: SEO_SITE_URL },
          { "@type": "ListItem", position: 2, name: "Юридическая помощь", item: `${SEO_SITE_URL}/legal-help` },
          { "@type": "ListItem", position: 3, name: "Регионы", item: `${SEO_SITE_URL}/legal-help/regions` },
          { "@type": "ListItem", position: 4, name: region.name, item: canonicalUrl },
        ],
      },
    ],
  };

  return (
    <main className={`${isLightOpsTheme ? "visual-light-ops" : ""} min-h-screen bg-slate-900 text-slate-100`}>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(schema) }} />

      <section className="relative overflow-hidden border-b border-slate-700">
        <HeroBackdrop variant="services" tone="light" />
        <div className="relative mx-auto max-w-6xl px-4 pb-16 pt-28 sm:px-6 lg:px-8 lg:pt-32">
          <nav aria-label="Хлебные крошки" className="text-sm text-slate-300">
            <Link href="/legal-help" className="hover:text-amber-300">Юридическая помощь</Link>
            <span aria-hidden="true"> / </span>
            <Link href="/legal-help/regions" className="hover:text-amber-300">Регионы</Link>
            <span aria-hidden="true"> / </span>
            <span>{region.name}</span>
          </nav>
          <p className="mt-8 text-sm font-semibold uppercase tracking-wide text-amber-300">
            Онлайн по законодательству Российской Федерации
          </p>
          <h1 className="mt-3 max-w-5xl text-4xl font-semibold leading-tight text-white md:text-5xl">
            Юридическая помощь в {region.prepositionalName}
          </h1>
          <p className="mt-6 max-w-4xl text-lg leading-relaxed text-slate-200">{region.intro}</p>
          <div className="mt-8 flex flex-col gap-3 sm:flex-row">
            <a href="#legal-help-form" className="rounded-lg bg-amber-500 px-6 py-3 text-center font-semibold text-slate-950 hover:bg-amber-400">
              Описать ситуацию
            </a>
            <Link href="/legal-help/online-consultation" className="rounded-lg border border-slate-600 px-6 py-3 text-center font-semibold text-white hover:border-amber-400 hover:text-amber-200">
              Как проходит консультация
            </Link>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-14 sm:px-6 lg:px-8">
        <div className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
          <article className="rounded-2xl border border-slate-700 bg-slate-800/60 p-7 md:p-9">
            <h2 className="text-3xl font-semibold text-white">Что учитывать в регионе</h2>
            <div className="mt-5 space-y-4 leading-7 text-slate-300">
              {region.context.map((paragraph) => <p key={paragraph}>{paragraph}</p>)}
            </div>
          </article>
          <aside className="rounded-2xl border border-amber-500/30 bg-amber-500/10 p-7 md:p-9">
            <h2 className="text-2xl font-semibold text-white">С чем можно обратиться</h2>
            <ul className="mt-5 space-y-3 text-sm leading-6 text-slate-200">
              {region.focus.map((item) => (
                <li key={item} className="flex gap-3">
                  <span aria-hidden="true" className="text-amber-300">•</span>
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </aside>
        </div>
      </section>

      <section className="border-y border-slate-700 bg-slate-800/40">
        <div className="mx-auto max-w-6xl px-4 py-14 sm:px-6 lg:px-8">
          <h2 className="text-3xl font-semibold text-white">Как проверяем региональный маршрут</h2>
          <ol className="mt-7 grid gap-5 md:grid-cols-2">
            {region.localProcess.map((item, index) => (
              <li key={item} className="rounded-xl border border-slate-700 bg-slate-900/50 p-6">
                <span className="text-sm font-bold text-amber-300">0{index + 1}</span>
                <p className="mt-3 leading-7 text-slate-300">{item}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <LegalHelpCommercialFacts />

      <section className="border-y border-slate-700 bg-slate-800/40">
        <div className="mx-auto max-w-6xl px-4 py-14 sm:px-6 lg:px-8">
          <h2 className="text-3xl font-semibold text-white">Официальные региональные сервисы</h2>
          <p className="mt-4 max-w-3xl leading-relaxed text-slate-300">
            Ссылки помогают проверить суд и сведения о деле. Они не заменяют анализ подсудности и требований
            к конкретному обращению.
          </p>
          <div className="mt-7 grid gap-5 md:grid-cols-3">
            {region.officialResources.map((resource) => (
              <a
                key={resource.href}
                href={resource.href}
                target="_blank"
                rel="noopener noreferrer"
                className="rounded-xl border border-slate-700 bg-slate-900/50 p-6 hover:border-amber-400"
              >
                <h3 className="font-semibold text-amber-300">{resource.title} ↗</h3>
                <p className="mt-3 text-sm leading-6 text-slate-300">{resource.description}</p>
              </a>
            ))}
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-14 sm:px-6 lg:px-8">
        <h2 className="text-3xl font-semibold text-white">Юридические направления</h2>
        <div className="mt-7 grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {services.map((service) => (
            <Link key={service.href} href={service.href} className="rounded-xl border border-slate-700 bg-slate-800/60 p-5 font-semibold text-amber-300 hover:border-amber-400">
              {service.title} →
            </Link>
          ))}
        </div>
      </section>

      <LegalHelpTrust />
      <PageFAQ items={region.faq} pageUrl={canonicalUrl} title={`Частые вопросы: ${region.name}`} />
      <LegalHelpForm
        sourceContext={`web_legal_help_region_${region.slug.replaceAll("-", "_")}`}
        initialArea={region.initialArea}
      />
    </main>
  );
}
