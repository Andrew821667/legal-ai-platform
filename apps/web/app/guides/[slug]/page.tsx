import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { getGuideBySlug, guides } from "@/lib/guidesData";
import { LEGAL_OPERATOR_NAME, LEGAL_SITE_URL } from "@/lib/legalProfile";
import { createPageMetadata } from "@/lib/seo";

type GuidePageProps = {
  params: Promise<{ slug: string }>;
};

export function generateStaticParams() {
  return guides.map((guide) => ({ slug: guide.slug }));
}

export async function generateMetadata({ params }: GuidePageProps): Promise<Metadata> {
  const { slug } = await params;
  const guide = getGuideBySlug(slug);
  if (!guide) {
    return { title: "Материал не найден", robots: { index: false, follow: false } };
  }

  return createPageMetadata({
    title: guide.seoTitle || guide.title,
    description: guide.description,
    path: `/guides/${guide.slug}`,
    type: "article",
  });
}

export default async function GuidePage({ params }: GuidePageProps) {
  const { slug } = await params;
  const guide = getGuideBySlug(slug);
  if (!guide) notFound();

  const baseUrl = LEGAL_SITE_URL.replace(/\/$/, "");
  const canonicalUrl = `${baseUrl}/guides/${guide.slug}`;
  const relatedGuides = guides.filter((item) => item.slug !== guide.slug);
  const relatedService = guide.slug === "ai-contract-review-process"
    ? { href: "/services/contracts-ai", label: "Автоматизация договорной работы" }
    : guide.slug === "legal-ai-data-security"
      ? { href: "/services/custom-ai", label: "Безопасная архитектура и интеграции" }
      : { href: "/solutions", label: "Решения для юридической автоматизации" };
  const structuredData = {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "TechArticle",
        "@id": `${canonicalUrl}#article`,
        headline: guide.title,
        description: guide.description,
        datePublished: guide.publishedAt,
        dateModified: guide.updatedAt,
        inLanguage: "ru-RU",
        image: `${baseUrl}/opengraph-image`,
        mainEntityOfPage: { "@type": "WebPage", "@id": canonicalUrl },
        author: {
          "@type": "Person",
          "@id": `${baseUrl}/#founder`,
          name: LEGAL_OPERATOR_NAME,
          url: `${baseUrl}/team`,
        },
        publisher: {
          "@type": "Organization",
          "@id": `${baseUrl}/#organization`,
          name: "AI Verdict",
          url: baseUrl,
          logo: { "@type": "ImageObject", url: `${baseUrl}/icon.svg` },
        },
      },
      {
        "@type": "BreadcrumbList",
        "@id": `${canonicalUrl}#breadcrumb`,
        itemListElement: [
          { "@type": "ListItem", position: 1, name: "Главная", item: baseUrl },
          { "@type": "ListItem", position: 2, name: "Руководства", item: `${baseUrl}/guides` },
          { "@type": "ListItem", position: 3, name: guide.title, item: canonicalUrl },
        ],
      },
    ],
  };

  return (
    <main className="min-h-screen bg-slate-50 text-slate-900">
      <article className="mx-auto max-w-4xl px-4 py-16 sm:px-6 lg:px-8">
        <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(structuredData) }} />
        <nav aria-label="Хлебные крошки" className="text-sm text-slate-500">
          <Link href="/guides" className="hover:text-amber-700">Руководства</Link> / {guide.title}
        </nav>

        <header className="mt-6 border-b border-slate-200 pb-10">
          <p className="text-sm font-semibold uppercase tracking-wide text-amber-700">Практическое руководство</p>
          <h1 className="mt-3 text-4xl font-bold leading-tight md:text-5xl">{guide.title}</h1>
          <p className="mt-6 text-lg leading-relaxed text-slate-600">{guide.excerpt}</p>
          <div className="mt-6 flex flex-wrap gap-x-6 gap-y-2 text-sm text-slate-500">
            <span>Автор: <Link href="/team" className="font-medium text-slate-700 underline">{LEGAL_OPERATOR_NAME}</Link></span>
            <span>Обновлено: 13 июля 2026 года</span>
            <span>{guide.readingTime}</span>
          </div>
        </header>

        <div className="mt-10 space-y-12">
          {guide.sections.map((section) => (
            <section key={section.heading}>
              <h2 className="text-2xl font-bold">{section.heading}</h2>
              <div className="mt-4 space-y-4 text-base leading-7 text-slate-700">
                {section.paragraphs.map((paragraph) => <p key={paragraph}>{paragraph}</p>)}
              </div>
              {section.bullets && (
                <ul className="mt-5 list-disc space-y-2 pl-6 text-slate-700">
                  {section.bullets.map((item) => <li key={item}>{item}</li>)}
                </ul>
              )}
            </section>
          ))}
        </div>

        <section className="mt-14 rounded-xl border border-amber-200 bg-amber-50 p-7">
          <h2 className="text-2xl font-bold">Чек-лист перед стартом</h2>
          <ul className="mt-5 space-y-3">
            {guide.checklist.map((item) => (
              <li key={item} className="flex gap-3 text-slate-700"><span aria-hidden="true">✓</span><span>{item}</span></li>
            ))}
          </ul>
        </section>

        <section className="mt-10 rounded-xl bg-slate-900 p-7 text-slate-100">
          <h2 className="text-2xl font-semibold">Нужно разобрать ваш процесс?</h2>
          <p className="mt-3 text-slate-300">Опишите задачу и текущий маршрут — начнем с диагностики, а не с продажи инструмента.</p>
          <Link href="/#lead-form" className="mt-5 inline-flex rounded-lg bg-amber-500 px-5 py-3 font-semibold text-slate-950 hover:bg-amber-400">
            Оставить заявку
          </Link>
        </section>

        <section className="mt-10 border-t border-slate-200 pt-10">
          <h2 className="text-2xl font-bold">Продолжить по теме</h2>
          <div className="mt-5 grid gap-4 md:grid-cols-2">
            {relatedGuides.map((item) => (
              <Link key={item.slug} href={`/guides/${item.slug}`} className="rounded-xl border border-slate-200 bg-white p-5 hover:border-amber-400">
                <h3 className="font-semibold text-amber-800">{item.title}</h3>
                <p className="mt-2 text-sm leading-6 text-slate-600">{item.excerpt}</p>
              </Link>
            ))}
          </div>
          <Link href={relatedService.href} className="mt-5 inline-flex font-semibold text-amber-800 hover:text-amber-950">
            {relatedService.label} →
          </Link>
        </section>
      </article>
    </main>
  );
}
