import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import HeroBackdrop from "@/components/HeroBackdrop";
import LegalAiRoiCalculator from "@/components/LegalAiRoiCalculator";
import { LEGAL_OPERATOR_NAME } from "@/lib/legalProfile";
import { getLegalAiTopic, LEGAL_AI_REVIEWED_AT, legalAiTopics } from "@/lib/legalAiTopics";
import { createPageMetadata, SEO_SITE_URL } from "@/lib/seo";

type LegalAiTopicPageProps = {
  params: Promise<{ slug: string }>;
};

export function generateStaticParams() {
  return legalAiTopics.map((topic) => ({ slug: topic.slug }));
}

export async function generateMetadata({ params }: LegalAiTopicPageProps): Promise<Metadata> {
  const { slug } = await params;
  const topic = getLegalAiTopic(slug);
  if (!topic) return { title: "Материал не найден", robots: { index: false, follow: false } };

  return createPageMetadata({
    title: topic.seoTitle,
    description: topic.description,
    path: `/legal-ai/${topic.slug}`,
    type: "article",
    keywords: topic.keywords,
    socialImage: "/solutions/opengraph-image",
  });
}

export default async function LegalAiTopicPage({ params }: LegalAiTopicPageProps) {
  const { slug } = await params;
  const topic = getLegalAiTopic(slug);
  if (!topic) notFound();

  const url = `${SEO_SITE_URL}/legal-ai/${topic.slug}`;
  const reviewedAt = topic.reviewedAt ?? LEGAL_AI_REVIEWED_AT;
  const structuredData = {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": ["WebPage", "TechArticle"],
        "@id": `${url}#article`,
        url,
        headline: topic.title,
        description: topic.description,
        datePublished: LEGAL_AI_REVIEWED_AT,
        dateModified: reviewedAt,
        inLanguage: "ru-RU",
        mainEntityOfPage: { "@type": "WebPage", "@id": url },
        author: {
          "@type": "Person",
          "@id": `${SEO_SITE_URL}/#founder`,
          name: LEGAL_OPERATOR_NAME,
          url: `${SEO_SITE_URL}/team`,
        },
        publisher: {
          "@type": "Organization",
          "@id": `${SEO_SITE_URL}/#organization`,
          name: "AI Verdict",
          url: SEO_SITE_URL,
        },
        about: topic.keywords.map((name) => ({ "@type": "Thing", name })),
      },
      {
        "@type": "FAQPage",
        "@id": `${url}#faq`,
        mainEntity: topic.faq.map((item) => ({
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
          { "@type": "ListItem", position: 2, name: "ИИ в юридической сфере", item: `${SEO_SITE_URL}/legal-ai` },
          { "@type": "ListItem", position: 3, name: topic.title, item: url },
        ],
      },
      ...(topic.slug === "roi" ? [{
        "@type": "WebApplication",
        "@id": `${url}#calculator`,
        name: "Калькулятор ROI юридической автоматизации",
        description: "Бесплатный расчет ROI, срока окупаемости и потенциального эффекта пилота Legal AI.",
        applicationCategory: "BusinessApplication",
        operatingSystem: "Web",
        inLanguage: "ru-RU",
        isPartOf: { "@id": url },
        offers: { "@type": "Offer", price: "0", priceCurrency: "RUB" },
      }] : []),
    ],
  };

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(structuredData) }} />

      <section className="relative overflow-hidden border-b border-slate-700">
        <HeroBackdrop variant="solutions" tone="light" />
        <div className="relative mx-auto max-w-6xl px-4 pb-12 pt-24 sm:px-6 sm:pb-16 sm:pt-28 lg:px-8">
          <nav aria-label="Хлебные крошки" className="hidden text-sm text-slate-600 sm:block">
            <Link href="/" className="hover:text-amber-800">Главная</Link>{" / "}
            <Link href="/legal-ai" className="hover:text-amber-800">ИИ в юридической сфере</Link>{" / "}
            {topic.title}
          </nav>
          <p className="text-sm font-semibold uppercase tracking-wide text-amber-800 sm:mt-6">{topic.eyebrow}</p>
          <h1 className="mt-3 max-w-5xl text-[32px] font-semibold leading-[1.15] text-slate-950 sm:text-4xl md:text-5xl">
            {topic.title}
          </h1>
          <p className="mt-5 max-w-4xl text-base leading-7 text-slate-700 sm:mt-6 sm:text-lg sm:leading-relaxed">
            {topic.intro}
          </p>
          <div className="mt-7 flex flex-wrap gap-3">
            <Link href="/#lead-form" className="rounded-lg bg-amber-500 px-5 py-3 font-semibold text-slate-950 hover:bg-amber-400">
              Разобрать процесс
            </Link>
            <Link href="/legal-ai" className="rounded-lg border border-slate-500 px-5 py-3 font-semibold text-slate-800 hover:border-amber-600 hover:text-amber-800">
              Весь обзор Legal AI
            </Link>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-14 sm:px-6 lg:px-8">
        <div className="grid gap-7 lg:grid-cols-[1.15fr_0.85fr]">
          <div>
            <h2 className="text-3xl font-semibold text-white">Короткий ответ</h2>
            <p className="mt-5 text-lg leading-8 text-slate-300">{topic.shortAnswer}</p>
          </div>
          <aside className="rounded-2xl border border-amber-500/30 bg-amber-500/10 p-7">
            <p className="font-semibold text-amber-300">Кому полезен материал</p>
            <p className="mt-4 leading-7 text-slate-200">{topic.audience}</p>
          </aside>
        </div>
      </section>

      <section className="border-y border-slate-800 bg-slate-900/70">
        <div className="mx-auto max-w-6xl px-4 py-14 sm:px-6 lg:px-8">
          <h2 className="text-3xl font-semibold text-white">Практические сценарии</h2>
          <div className="mt-8 grid gap-5 md:grid-cols-2">
            {topic.useCases.map((item) => (
              <article key={item.title} className="rounded-xl border border-slate-700 bg-slate-950/70 p-6">
                <h3 className="text-xl font-semibold text-amber-300">{item.title}</h3>
                <p className="mt-3 leading-7 text-slate-300">{item.text}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-12 sm:px-6 lg:px-8">
        <h2 className="text-2xl font-semibold text-white">Как формулируют этот запрос</h2>
        <p className="mt-3 max-w-4xl leading-7 text-slate-300">
          Эти формулировки описывают близкое поисковое намерение и ведут на одну каноническую страницу, чтобы не
          создавать дублирующие материалы.
        </p>
        <ul className="mt-6 flex flex-wrap gap-3">
          {topic.keywords.map((keyword) => (
            <li key={keyword} className="rounded-full border border-slate-700 bg-slate-900 px-4 py-2 text-sm text-slate-200">
              {keyword}
            </li>
          ))}
        </ul>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-14 sm:px-6 lg:px-8">
        <h2 className="text-3xl font-semibold text-white">Рабочий порядок</h2>
        <ol className="mt-8 grid gap-5 md:grid-cols-2 xl:grid-cols-4">
          {topic.workflow.map((item) => (
            <li key={item.title} className="rounded-xl border border-slate-800 bg-slate-900 p-6">
              <h3 className="font-semibold text-amber-300">{item.title}</h3>
              <p className="mt-3 text-sm leading-6 text-slate-300">{item.text}</p>
            </li>
          ))}
        </ol>
      </section>

      {topic.slug === "roi" ? <LegalAiRoiCalculator /> : null}

      {topic.sources && (
        <section className="mx-auto max-w-6xl px-4 pb-14 sm:px-6 lg:px-8">
          <div className="rounded-2xl border border-slate-800 bg-slate-900 p-7">
            <h2 className="text-2xl font-semibold text-white">Официальные источники для проверки</h2>
            <ul className="mt-5 grid gap-3 md:grid-cols-2">
              {topic.sources.map((source) => (
                <li key={source.href}>
                  <a href={source.href} className="text-sky-300 underline underline-offset-4 hover:text-sky-200">
                    {source.label} →
                  </a>
                </li>
              ))}
            </ul>
          </div>
        </section>
      )}

      <section className="border-y border-slate-800 bg-slate-900/70">
        <div className="mx-auto max-w-6xl px-4 py-14 sm:px-6 lg:px-8">
          <h2 className="text-3xl font-semibold text-white">Что обязательно контролировать</h2>
          <div className="mt-8 grid gap-5 md:grid-cols-2 xl:grid-cols-4">
            {topic.controls.map((item) => (
              <article key={item.title} className="rounded-xl border border-slate-700 bg-slate-950/70 p-6">
                <h3 className="font-semibold text-sky-300">{item.title}</h3>
                <p className="mt-3 text-sm leading-6 text-slate-300">{item.text}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-14 sm:px-6 lg:px-8">
        <h2 className="text-3xl font-semibold text-white">Частые вопросы</h2>
        <div className="mt-8 grid gap-5 md:grid-cols-2">
          {topic.faq.map((item) => (
            <article key={item.question} className="rounded-xl border border-slate-800 bg-slate-900 p-6">
              <h3 className="text-lg font-semibold text-amber-300">{item.question}</h3>
              <p className="mt-3 text-sm leading-6 text-slate-300">{item.answer}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="border-y border-slate-800 bg-slate-900/70">
        <div className="mx-auto max-w-6xl px-4 py-14 sm:px-6 lg:px-8">
          <h2 className="text-3xl font-semibold text-white">Продолжить по теме</h2>
          <div className="mt-8 grid gap-5 md:grid-cols-3">
            {topic.related.map((item) => (
              <Link key={item.href} href={item.href} className="rounded-xl border border-slate-700 bg-slate-950/70 p-6 hover:border-amber-500">
                <h3 className="font-semibold text-amber-300">{item.label} →</h3>
                <p className="mt-3 text-sm leading-6 text-slate-300">{item.description}</p>
              </Link>
            ))}
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-14 sm:px-6 lg:px-8">
        <div className="grid gap-6 rounded-2xl border border-amber-500/30 bg-amber-500/10 p-7 md:grid-cols-[1fr_auto] md:items-center">
          <div>
            <h2 className="text-2xl font-semibold text-white">Проверить применимость к вашему процессу</h2>
            <p className="mt-3 max-w-3xl leading-7 text-slate-300">
              Опишите задачу, документы и ограничения. Определим, где нужен ИИ, где достаточно правил и какая проверка требуется до рабочего запуска.
            </p>
          </div>
          <Link href="/#lead-form" className="rounded-lg bg-amber-500 px-6 py-3 text-center font-semibold text-slate-950 hover:bg-amber-400">
            Обсудить задачу
          </Link>
        </div>
        <p className="mt-8 text-sm leading-6 text-slate-500">
          Автор и ответственный за материал — <Link href="/team" className="underline hover:text-slate-300">{LEGAL_OPERATOR_NAME}</Link>.
          Материал проверен {new Intl.DateTimeFormat("ru-RU", {
            day: "numeric",
            month: "long",
            year: "numeric",
            timeZone: "UTC",
          }).format(new Date(`${reviewedAt}T00:00:00.000Z`))} и не заменяет юридическую консультацию по конкретным обстоятельствам.
        </p>
      </section>
    </main>
  );
}
