import { ArrowRight, CalendarDays, CheckCircle2, FileCheck2, Scale } from "lucide-react";
import Link from "next/link";

import HeroBackdrop from "@/components/HeroBackdrop";
import { AI_LAW_REVIEWED_AT, aiLawComments } from "@/lib/aiLawComments";
import { LEGAL_OPERATOR_NAME, LEGAL_SITE_URL } from "@/lib/legalProfile";
import { ROUTES } from "@/lib/links";
import { createPageMetadata } from "@/lib/seo";

export const metadata = createPageMetadata({
  title: "Комментарии законодательства об искусственном интеллекте",
  description:
    "Экспертные комментарии новых российских норм об ИИ: сроки вступления в силу, применимость, отложенные положения и практические действия бизнеса.",
  path: "/ai-law",
  keywords: [
    "законодательство об искусственном интеллекте",
    "регулирование ИИ в России",
    "законы об ИИ",
    "AI law Россия",
    "требования к искусственному интеллекту",
  ],
});

function formatDate(date: string): string {
  return new Intl.DateTimeFormat("ru-RU", {
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(`${date}T00:00:00.000Z`));
}

export default function AiLawPage() {
  const baseUrl = LEGAL_SITE_URL.replace(/\/$/, "");
  const pageUrl = `${baseUrl}/ai-law`;
  const structuredData = {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "CollectionPage",
        "@id": `${pageUrl}#page`,
        url: pageUrl,
        name: "Комментарии законодательства об искусственном интеллекте",
        description:
          "Проверяемые комментарии российских правовых новелл об искусственном интеллекте.",
        dateModified: AI_LAW_REVIEWED_AT,
        inLanguage: "ru-RU",
        publisher: { "@id": `${baseUrl}/#organization` },
      },
      {
        "@type": "ItemList",
        "@id": `${pageUrl}#comments`,
        itemListElement: aiLawComments.map((comment, idx) => ({
          "@type": "ListItem",
          position: idx + 1,
          name: comment.title,
          url: `${pageUrl}/${comment.slug}`,
        })),
      },
      {
        "@type": "BreadcrumbList",
        "@id": `${pageUrl}#breadcrumb`,
        itemListElement: [
          { "@type": "ListItem", position: 1, name: "Главная", item: baseUrl },
          { "@type": "ListItem", position: 2, name: "Комментарии законодательства", item: pageUrl },
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
        <div className="relative mx-auto max-w-6xl px-4 pb-16 pt-28 sm:px-6 md:pb-20 md:pt-32 lg:px-8">
          <div className="flex items-center gap-2 text-sm font-semibold uppercase text-amber-300">
            <Scale className="h-4 w-4" aria-hidden="true" />
            Юридическая практика · AI law
          </div>
          <h1 className="mt-4 max-w-5xl text-4xl font-semibold leading-tight text-white md:text-5xl">
            Комментарии новелл законодательства в сфере искусственного интеллекта
          </h1>
          <p className="mt-5 max-w-3xl text-lg leading-relaxed text-slate-200">
            Отделяем дату публикации закона от даты реальных обязанностей. Показываем,
            кого касается норма, что еще отложено и какие действия бизнесу нужны сейчас.
          </p>
          <div className="mt-7 flex flex-wrap gap-x-6 gap-y-3 text-sm text-slate-300">
            <span className="inline-flex items-center gap-2">
              <FileCheck2 className="h-4 w-4 text-emerald-400" aria-hidden="true" />
              Только официальные первоисточники
            </span>
            <span className="inline-flex items-center gap-2">
              <CalendarDays className="h-4 w-4 text-sky-300" aria-hidden="true" />
              Проверено {formatDate(AI_LAW_REVIEWED_AT)}
            </span>
          </div>
        </div>
      </section>

      <section className="border-b border-slate-300 bg-white">
        <div className="mx-auto grid max-w-6xl gap-8 px-4 py-10 sm:px-6 md:grid-cols-3 lg:px-8">
          {[
            ["1", "Норма", "Сверяем текст, предмет регулирования и официальный источник."],
            ["2", "Срок", "Разделяем опубликование, общее вступление в силу и отложенные положения."],
            ["3", "Действие", "Переводим требования в проверяемые шаги для юридической, IT- и бизнес-команд."],
          ].map(([num, title, text]) => (
            <div key={num} className="grid grid-cols-[2rem_1fr] gap-3">
              <span className="flex h-8 w-8 items-center justify-center rounded-full bg-slate-900 text-sm font-semibold text-white">
                {num}
              </span>
              <div>
                <h2 className="font-semibold text-slate-950">{title}</h2>
                <p className="mt-1 text-sm leading-6 text-slate-600">{text}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-14 sm:px-6 lg:px-8">
        <div className="flex flex-col gap-3 border-b border-slate-300 pb-6 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="text-sm font-semibold uppercase text-amber-800">Новые комментарии</p>
            <h2 className="mt-2 text-3xl font-semibold text-slate-950">Что меняется для бизнеса</h2>
          </div>
          <p className="max-w-xl text-sm leading-6 text-slate-600">
            Публикуем материал только после проверки дат, адресатов нормы и ссылки на
            официальное опубликование.
          </p>
        </div>

        <div className="mt-8 space-y-5">
          {aiLawComments.map((comment) => (
            <article
              key={comment.slug}
              className="rounded-lg border border-slate-300 bg-white p-6 shadow-sm md:p-8"
            >
              <div className="flex flex-wrap items-center gap-3 text-xs font-semibold uppercase text-slate-600">
                <span className="inline-flex items-center gap-1.5 text-emerald-700">
                  <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
                  Проверено
                </span>
                <span>{comment.lawNumber}</span>
                <span>Обновлено {formatDate(comment.reviewedAt)}</span>
                <span>{comment.readingTime}</span>
              </div>
              <h3 className="mt-4 max-w-4xl text-2xl font-semibold leading-snug text-slate-950">
                {comment.title}
              </h3>
              <p className="mt-4 max-w-4xl leading-7 text-slate-700">{comment.summary}</p>

              <div className="mt-6 grid gap-3 sm:grid-cols-2">
                {comment.effectiveStages.map((stage) => (
                  <div key={stage.date} className="border-l-4 border-amber-500 bg-slate-100 px-4 py-3">
                    <time dateTime={stage.date} className="text-sm font-semibold text-slate-950">
                      {formatDate(stage.date)}
                    </time>
                    <p className="mt-1 text-sm text-slate-600">{stage.title}</p>
                  </div>
                ))}
              </div>

              <Link
                href={`/ai-law/${comment.slug}`}
                className="mt-7 inline-flex items-center gap-2 font-semibold text-amber-800 hover:text-amber-950"
              >
                Читать комментарий
                <ArrowRight className="h-4 w-4" aria-hidden="true" />
              </Link>
            </article>
          ))}
        </div>
      </section>

      <section className="border-y border-slate-300 bg-slate-200">
        <div className="mx-auto grid max-w-6xl gap-8 px-4 py-12 sm:px-6 md:grid-cols-[1.2fr_0.8fr] lg:px-8">
          <div>
            <p className="text-sm font-semibold uppercase text-slate-600">Редакционный стандарт</p>
            <h2 className="mt-2 text-3xl font-semibold text-slate-950">Проверяемость важнее скорости</h2>
            <p className="mt-4 max-w-2xl leading-7 text-slate-700">
              Каждый материал содержит дату юридической проверки и прямую ссылку на
              официальный акт. Если обязательность зависит от будущего постановления,
              перечня или порядка, мы прямо отмечаем эту зависимость.
            </p>
          </div>
          <div className="border-l-4 border-slate-700 pl-5">
            <p className="text-sm leading-6 text-slate-700">
              Ответственный за материалы: {LEGAL_OPERATOR_NAME}. Комментарии носят
              информационный характер; применимость нормы к конкретной системе зависит
              от ее роли, архитектуры и фактического использования.
            </p>
            <Link
              href={ROUTES.legalHelpBusiness}
              className="mt-5 inline-flex items-center gap-2 font-semibold text-slate-950 hover:text-amber-900"
            >
              Оценить применимость к вашей системе
              <ArrowRight className="h-4 w-4" aria-hidden="true" />
            </Link>
          </div>
        </div>
      </section>
    </main>
  );
}
