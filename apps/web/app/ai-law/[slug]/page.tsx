import type { Metadata } from "next";
import {
  ArrowRight,
  CalendarClock,
  CheckCircle2,
  ExternalLink,
  FileText,
  Scale,
  ShieldAlert,
} from "lucide-react";
import Link from "next/link";
import { notFound } from "next/navigation";

import HeroBackdrop from "@/components/HeroBackdrop";
import { aiLawComments, getAiLawComment } from "@/lib/aiLawComments";
import { LEGAL_OPERATOR_NAME, LEGAL_SITE_URL } from "@/lib/legalProfile";
import { ROUTES } from "@/lib/links";
import { createPageMetadata } from "@/lib/seo";

type AiLawCommentPageProps = {
  params: Promise<{ slug: string }>;
};

function formatDate(date: string): string {
  return new Intl.DateTimeFormat("ru-RU", {
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(`${date}T00:00:00.000Z`));
}

export function generateStaticParams() {
  return aiLawComments.map((comment) => ({ slug: comment.slug }));
}

export async function generateMetadata({ params }: AiLawCommentPageProps): Promise<Metadata> {
  const { slug } = await params;
  const comment = getAiLawComment(slug);
  if (!comment) {
    return { title: "Комментарий не найден", robots: { index: false, follow: false } };
  }

  return createPageMetadata({
    title: comment.seoTitle,
    description: comment.description,
    path: `/ai-law/${comment.slug}`,
    type: "article",
    keywords: comment.keywords,
  });
}

export default async function AiLawCommentPage({ params }: AiLawCommentPageProps) {
  const { slug } = await params;
  const comment = getAiLawComment(slug);
  if (!comment) notFound();

  const baseUrl = LEGAL_SITE_URL.replace(/\/$/, "");
  const canonicalUrl = `${baseUrl}/ai-law/${comment.slug}`;
  const structuredData = {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "Article",
        "@id": `${canonicalUrl}#article`,
        headline: comment.title,
        description: comment.description,
        datePublished: comment.publishedAt,
        dateModified: comment.reviewedAt,
        inLanguage: "ru-RU",
        mainEntityOfPage: { "@type": "WebPage", "@id": canonicalUrl },
        about: {
          "@type": "Legislation",
          name: `Федеральный закон от ${formatDate(comment.lawDate)} № ${comment.lawNumber}`,
          legislationIdentifier: comment.lawNumber,
          legislationDate: comment.lawDate,
          url: comment.officialSource.url,
        },
        author: {
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
          { "@type": "ListItem", position: 2, name: "Комментарии законодательства", item: `${baseUrl}/ai-law` },
          { "@type": "ListItem", position: 3, name: comment.title, item: canonicalUrl },
        ],
      },
    ],
  };

  return (
    <main className="min-h-screen bg-slate-50 text-slate-900">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(structuredData) }}
      />

      <section className="relative overflow-hidden border-b border-slate-300 bg-slate-900">
        <HeroBackdrop variant="insights" tone="light" />
        <div className="relative mx-auto max-w-5xl px-4 pb-16 pt-28 sm:px-6 md:pt-32 lg:px-8">
          <nav aria-label="Хлебные крошки" className="text-sm text-slate-300">
            <Link href="/ai-law" className="hover:text-amber-300">Комментарии законодательства</Link>
            <span aria-hidden="true"> / </span>
            {comment.lawNumber}
          </nav>
          <div className="mt-6 flex items-center gap-2 text-sm font-semibold uppercase text-amber-300">
            <Scale className="h-4 w-4" aria-hidden="true" />
            Проверенный правовой комментарий
          </div>
          <h1 className="mt-4 max-w-5xl text-4xl font-semibold leading-tight text-white md:text-5xl">
            {comment.title}
          </h1>
          <p className="mt-6 max-w-4xl text-lg leading-relaxed text-slate-200">{comment.summary}</p>
          <div className="mt-7 flex flex-wrap gap-x-6 gap-y-3 text-sm text-slate-300">
            <span className="inline-flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-emerald-400" aria-hidden="true" />
              Статус: проверено
            </span>
            <span>Опубликовано: {formatDate(comment.publishedAt)}</span>
            <span>Проверено: {formatDate(comment.reviewedAt)}</span>
            <span>{comment.readingTime}</span>
          </div>
        </div>
      </section>

      <article className="mx-auto max-w-5xl px-4 pb-16 sm:px-6 lg:px-8">
        <section className="grid gap-6 border-b border-slate-300 py-10 md:grid-cols-[1fr_1.2fr]">
          <div>
            <p className="text-sm font-semibold uppercase text-slate-600">Комментируемый акт</p>
            <h2 className="mt-2 text-2xl font-semibold text-slate-950">
              Федеральный закон от {formatDate(comment.lawDate)} № {comment.lawNumber}
            </h2>
            <p className="mt-3 leading-7 text-slate-700">«{comment.lawTitle}»</p>
          </div>
          <div className="border-l-4 border-emerald-600 bg-white px-5 py-4">
            <p className="text-sm font-semibold text-emerald-800">Первичный официальный источник</p>
            <a
              href={comment.officialSource.url}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-2 inline-flex items-start gap-2 font-semibold text-slate-950 underline decoration-emerald-600 underline-offset-4 hover:text-emerald-900"
            >
              <FileText className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
              {comment.officialSource.title}
              <ExternalLink className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
            </a>
            <p className="mt-2 text-xs text-slate-500">
              Номер опубликования: {comment.officialSource.publicationId}
            </p>
          </div>
        </section>

        <section className="py-12">
          <div className="flex items-center gap-3">
            <CalendarClock className="h-6 w-6 text-amber-700" aria-hidden="true" />
            <h2 className="text-3xl font-semibold text-slate-950">Два этапа вступления в силу</h2>
          </div>
          <div className="mt-7 grid gap-5 md:grid-cols-2">
            {comment.effectiveStages.map((stage) => (
              <section key={stage.date} className="rounded-lg border border-slate-300 bg-white p-6">
                <p className="text-sm font-semibold uppercase text-amber-800">{stage.label}</p>
                <time dateTime={stage.date} className="mt-2 block text-2xl font-semibold text-slate-950">
                  {formatDate(stage.date)}
                </time>
                <h3 className="mt-2 text-lg font-semibold text-slate-900">{stage.title}</h3>
                <p className="mt-3 text-sm leading-6 text-slate-600">{stage.summary}</p>
                <ul className="mt-5 space-y-3 text-sm leading-6 text-slate-700">
                  {stage.points.map((point) => (
                    <li key={point} className="flex gap-3">
                      <CheckCircle2 className="mt-1 h-4 w-4 shrink-0 text-emerald-600" aria-hidden="true" />
                      <span>{point}</span>
                    </li>
                  ))}
                </ul>
                <p className="mt-5 border-t border-slate-200 pt-4 text-xs leading-5 text-slate-500">
                  Основание: {stage.legalBasis}
                </p>
              </section>
            ))}
          </div>
        </section>

        <section className="border-y border-slate-300 bg-slate-200 px-5 py-9 md:px-8">
          <h2 className="text-2xl font-semibold text-slate-950">Кому проверить применимость</h2>
          <div className="mt-5 grid gap-x-8 gap-y-3 md:grid-cols-2">
            {comment.audience.map((item) => (
              <div key={item} className="flex gap-3 text-slate-700">
                <CheckCircle2 className="mt-1 h-4 w-4 shrink-0 text-slate-700" aria-hidden="true" />
                <span>{item}</span>
              </div>
            ))}
          </div>
        </section>

        <div className="space-y-12 py-12">
          {comment.sections.map((section) => (
            <section key={section.heading}>
              <h2 className="text-2xl font-semibold text-slate-950">{section.heading}</h2>
              <div className="mt-4 space-y-4 leading-7 text-slate-700">
                {section.paragraphs.map((paragraph) => <p key={paragraph}>{paragraph}</p>)}
              </div>
              {section.bullets ? (
                <ul className="mt-5 space-y-3 border-l-4 border-slate-400 pl-5 leading-7 text-slate-700">
                  {section.bullets.map((item) => <li key={item}>{item}</li>)}
                </ul>
              ) : null}
            </section>
          ))}
        </div>

        <section className="border-y border-rose-200 bg-rose-50 px-5 py-10 md:px-8">
          <div className="flex items-center gap-3">
            <ShieldAlert className="h-6 w-6 text-rose-700" aria-hidden="true" />
            <h2 className="text-2xl font-semibold text-slate-950">Что закон не означает</h2>
          </div>
          <div className="mt-7 divide-y divide-rose-200">
            {comment.misconceptions.map((item) => (
              <div key={item.claim} className="grid gap-3 py-5 md:grid-cols-[0.9fr_1.1fr] md:gap-8">
                <p className="font-semibold text-rose-950">Миф: {item.claim}</p>
                <p className="leading-7 text-slate-700">{item.reality}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="py-12">
          <p className="text-sm font-semibold uppercase text-amber-800">Практический маршрут</p>
          <h2 className="mt-2 text-3xl font-semibold text-slate-950">Что сделать бизнесу сейчас</h2>
          <div className="mt-7 divide-y divide-slate-300 border-y border-slate-300">
            {comment.actions.map((action, idx) => (
              <div key={action.title} className="grid gap-3 py-6 md:grid-cols-[3rem_0.7fr_1.3fr] md:gap-6">
                <span className="text-2xl font-semibold text-amber-700">{String(idx + 1).padStart(2, "0")}</span>
                <h3 className="font-semibold text-slate-950">{action.title}</h3>
                <p className="leading-7 text-slate-700">{action.description}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="rounded-lg border border-sky-200 bg-sky-50 p-6 md:p-8">
          <h2 className="text-2xl font-semibold text-slate-950">Какие акты еще нужно отслеживать</h2>
          <ul className="mt-5 space-y-3 leading-7 text-slate-700">
            {comment.watchItems.map((item) => (
              <li key={item} className="flex gap-3">
                <ArrowRight className="mt-1 h-4 w-4 shrink-0 text-sky-700" aria-hidden="true" />
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </section>

        <section className="mt-10 border-t border-slate-300 pt-8 text-sm leading-6 text-slate-600">
          <p>
            Материал подготовлен юридической практикой AI Verdict и проверен {formatDate(comment.reviewedAt)}.
            Он не заменяет анализ применимости закона к конкретной системе, договорной модели и архитектуре данных.
          </p>
          <p className="mt-2">
            Ответственный за содержание: <Link href="/team" className="font-semibold text-slate-800 underline">{LEGAL_OPERATOR_NAME}</Link>.
          </p>
        </section>

        <section className="mt-10 rounded-lg bg-slate-900 p-7 text-slate-100 md:p-8">
          <h2 className="text-2xl font-semibold">Нужно определить, какие требования относятся к вашей AI-системе?</h2>
          <p className="mt-3 max-w-3xl leading-7 text-slate-300">
            Опишите роль компании, модель, данные и текущий процесс. Юридическая и
            инженерная практики разберут применимость вместе, без общих запретов и догадок.
          </p>
          <Link
            href={ROUTES.legalHelpBusiness}
            className="mt-6 inline-flex items-center gap-2 rounded-lg bg-amber-500 px-5 py-3 font-semibold text-slate-950 hover:bg-amber-400"
          >
            Описать задачу
            <ArrowRight className="h-4 w-4" aria-hidden="true" />
          </Link>
        </section>
      </article>
    </main>
  );
}
