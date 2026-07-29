import type { Metadata } from "next";
import Link from "next/link";

import HeroBackdrop from "@/components/HeroBackdrop";
import LegalHelpForm from "@/components/LegalHelpForm";
import LegalHelpTrust from "@/components/LegalHelpTrust";
import { LEGAL_HELP_REVIEWED_AT } from "@/lib/legalHelpPages";
import { legalHelpRegionList } from "@/lib/legalHelpRegions";
import { createPageMetadata, SEO_SITE_URL } from "@/lib/seo";
import { isLightOpsTheme } from "@/lib/visualTheme";

export const metadata: Metadata = createPageMetadata({
  title: "Юридическая помощь по регионам и агробизнесу России",
  description:
    "Дистанционная юридическая помощь в центрах федеральных округов и крупных аграрных регионах: договоры, земля, споры и сопровождение.",
  path: "/legal-help/regions",
  keywords: [
    "юридическая помощь по россии",
    "юрист по регионам",
    "юрист онлайн россия",
    "юридические услуги дистанционно",
    "юрист для агробизнеса",
    "сельскохозяйственный юрист",
  ],
});

export default function LegalHelpRegionsPage() {
  const canonicalUrl = `${SEO_SITE_URL}/legal-help/regions`;
  const federalRegions = legalHelpRegionList.filter((region) => region.categories?.includes("federal-center"));
  const agricultureRegions = legalHelpRegionList.filter((region) => region.categories?.includes("agriculture"));
  const schema = {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "CollectionPage",
        "@id": canonicalUrl,
        name: "Юридическая помощь по регионам и агробизнесу России",
        description: metadata.description,
        dateModified: LEGAL_HELP_REVIEWED_AT,
        inLanguage: "ru-RU",
        publisher: { "@id": `${SEO_SITE_URL}/#organization` },
        mainEntity: {
          "@type": "ItemList",
          itemListElement: legalHelpRegionList.map((region, index) => ({
            "@type": "ListItem",
            position: index + 1,
            name: region.name,
            url: `${canonicalUrl}/${region.slug}`,
          })),
        },
      },
      {
        "@type": "BreadcrumbList",
        "@id": `${canonicalUrl}#breadcrumb`,
        itemListElement: [
          { "@type": "ListItem", position: 1, name: "Главная", item: SEO_SITE_URL },
          { "@type": "ListItem", position: 2, name: "Юридическая помощь", item: `${SEO_SITE_URL}/legal-help` },
          { "@type": "ListItem", position: 3, name: "Регионы", item: canonicalUrl },
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
            <span>Регионы</span>
          </nav>
          <p className="mt-8 text-sm font-semibold uppercase tracking-wide text-amber-300">
            Дистанционная работа по России
          </p>
          <h1 className="mt-3 max-w-5xl text-4xl font-semibold leading-tight text-white md:text-5xl">
            Юридическая помощь по регионам и агробизнесу России
          </h1>
          <p className="mt-6 max-w-4xl text-lg leading-relaxed text-slate-200">
            География клиента, земли, производства, контрагента и суда может влиять на порядок действий.
            Отдельно развиваем помощь агробизнесу: учитываем сезонность, земельные отношения, поставки,
            хранение, переработку, субсидии и отраслевые доказательства.
          </p>
          <div className="mt-8 flex flex-col gap-3 sm:flex-row">
            <Link href="/legal-help/online-consultation" className="rounded-lg bg-amber-500 px-6 py-3 text-center font-semibold text-slate-950 hover:bg-amber-400">
              Получить онлайн-консультацию
            </Link>
            <a href="#legal-help-form" className="rounded-lg border border-slate-600 px-6 py-3 text-center font-semibold text-white hover:border-amber-400 hover:text-amber-200">
              Описать задачу
            </a>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-14 sm:px-6 lg:px-8">
        <h2 className="text-3xl font-semibold text-white">Центры федеральных округов</h2>
        <p className="mt-4 max-w-3xl leading-relaxed text-slate-300">
          Для каждого центра учитываем региональную подсудность, экономический профиль и официальные судебные
          сервисы. Наличие страницы не означает физический офис в указанном городе.
        </p>
        <div className="mt-8 grid gap-5 md:grid-cols-2 lg:grid-cols-3">
          {federalRegions.map((region) => (
            <Link
              key={region.slug}
              href={`/legal-help/regions/${region.slug}`}
              className="rounded-2xl border border-slate-700 bg-slate-800/60 p-7 hover:border-amber-400"
            >
              <h3 className="text-xl font-semibold text-white">{region.hubTitle ?? region.name}</h3>
              <p className="mt-4 leading-7 text-slate-300">{region.description}</p>
              <span className="mt-5 inline-flex font-semibold text-amber-300">Открыть регион →</span>
            </Link>
          ))}
        </div>
      </section>

      <section className="border-y border-emerald-500/20 bg-emerald-950/20">
        <div className="mx-auto max-w-6xl px-4 py-14 sm:px-6 lg:px-8">
          <p className="text-sm font-semibold uppercase tracking-wide text-emerald-300">Отраслевой контур</p>
          <h2 className="mt-3 text-3xl font-semibold text-white">Крупные сельскохозяйственные регионы</h2>
          <p className="mt-4 max-w-4xl leading-relaxed text-slate-300">
            Эти страницы предназначены не для формальной подстановки названия субъекта. В них разобраны
            характерные юридические связи земли, производства, качества, логистики, страхования и
            государственной поддержки.
          </p>
          <div className="mt-8 grid gap-5 md:grid-cols-2 lg:grid-cols-3">
            {agricultureRegions.map((region) => (
              <Link
                key={region.slug}
                href={`/legal-help/regions/${region.slug}`}
                className="rounded-2xl border border-emerald-500/20 bg-slate-900/60 p-7 hover:border-emerald-300"
              >
                <span className="text-xs font-semibold uppercase tracking-wide text-emerald-300">Агробизнес</span>
                <h3 className="mt-3 text-xl font-semibold text-white">{region.hubTitle ?? region.name}</h3>
                <p className="mt-4 leading-7 text-slate-300">{region.description}</p>
                <span className="mt-5 inline-flex font-semibold text-emerald-300">Открыть регион →</span>
              </Link>
            ))}
          </div>
        </div>
      </section>

      <LegalHelpTrust />
      <LegalHelpForm sourceContext="web_legal_help_regions" />
    </main>
  );
}
