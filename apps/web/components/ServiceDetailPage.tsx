import Link from "next/link";

import LeadCaptureForm from "@/components/LeadCaptureForm";
import HeroBackdrop from "@/components/HeroBackdrop";
import { LEGAL_BRAND, LEGAL_SITE_URL } from "@/lib/legalProfile";
import type { ServiceDetail } from "@/lib/serviceDetailData";

export default function ServiceDetailPage({ service }: { service: ServiceDetail }) {
  const canonicalUrl = `${LEGAL_SITE_URL.replace(/\/$/, "")}/services/${service.slug}`;
  const isEngineeringPractice = service.slug === "custom-ai";
  const structuredData = {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "Service",
        "@id": `${canonicalUrl}#service`,
        name: service.title,
        description: service.description,
        url: canonicalUrl,
        provider: { "@id": `${LEGAL_SITE_URL.replace(/\/$/, "")}/#organization` },
        areaServed: { "@type": "Country", name: "Россия" },
        serviceType: isEngineeringPractice
          ? "Разработка программного обеспечения, AI-сервисов и интеграций"
          : service.eyebrow,
        category: isEngineeringPractice
          ? ["Software development", "AI integration", "Business process automation"]
          : "Legal operations automation",
        audience: {
          "@type": "BusinessAudience",
          audienceType: "Компании, команды и предприниматели",
        },
        availableChannel: {
          "@type": "ServiceChannel",
          serviceUrl: canonicalUrl,
          availableLanguage: "ru-RU",
        },
      },
      {
        "@type": "WebPage",
        "@id": canonicalUrl,
        name: service.title,
        description: service.description,
        url: canonicalUrl,
        inLanguage: "ru-RU",
        mainEntity: { "@id": `${canonicalUrl}#service` },
        ...(isEngineeringPractice ? { dateModified: "2026-08-05" } : {}),
      },
      {
        "@type": "BreadcrumbList",
        "@id": `${canonicalUrl}#breadcrumb`,
        itemListElement: [
          { "@type": "ListItem", position: 1, name: "Главная", item: LEGAL_SITE_URL },
          { "@type": "ListItem", position: 2, name: "Услуги", item: `${LEGAL_SITE_URL.replace(/\/$/, "")}/services` },
          { "@type": "ListItem", position: 3, name: service.title, item: canonicalUrl },
        ],
      },
      {
        "@type": "FAQPage",
        "@id": `${canonicalUrl}#faq`,
        mainEntity: service.faq.map((item) => ({
          "@type": "Question",
          name: item.question,
          acceptedAnswer: { "@type": "Answer", text: item.answer },
        })),
      },
    ],
  };

  return (
    <main className="min-h-screen bg-slate-50 text-slate-900">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(structuredData) }} />

      <section className="relative overflow-hidden border-b border-slate-300 bg-slate-100">
        <HeroBackdrop variant="services" tone="light" />
        <div className="relative mx-auto max-w-6xl px-4 pb-16 pt-28 sm:px-6 lg:px-8 lg:pb-20 lg:pt-32">
          <nav aria-label="Хлебные крошки" className="text-sm text-slate-500">
            <Link href="/services" className="hover:text-amber-700">Услуги</Link> / {service.eyebrow}
          </nav>
          <p className="mt-8 text-sm font-semibold uppercase tracking-wide text-amber-700">{service.eyebrow}</p>
          <h1 className="mt-3 max-w-5xl text-4xl font-bold leading-tight md:text-5xl">{service.title}</h1>
          <p className="mt-6 max-w-4xl text-xl leading-relaxed text-slate-600">{service.intro}</p>
          <div className="mt-8 flex flex-col gap-3 sm:flex-row">
            <a href="#lead-form" className="rounded-lg bg-amber-700 px-6 py-3 text-center font-semibold text-white hover:bg-amber-800">
              Обсудить процесс
            </a>
            <a href="#workflow" className="rounded-lg border border-slate-300 px-6 py-3 text-center font-semibold text-slate-700 hover:bg-slate-100">
              Как проходит внедрение
            </a>
          </div>
        </div>
      </section>

      {service.shortAnswer && (
        <section className="border-b border-slate-200 bg-white">
          <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6 lg:px-8">
            <div className="max-w-4xl rounded-2xl border border-sky-200 bg-sky-50 p-7 md:p-8">
              <p className="text-sm font-semibold uppercase tracking-wide text-sky-800">Короткий ответ</p>
              <h2 className="mt-2 text-2xl font-bold text-slate-900">Что делает инженерная практика AI Verdict</h2>
              <p className="mt-4 text-base leading-7 text-slate-700">{service.shortAnswer}</p>
            </div>
          </div>
        </section>
      )}

      <section className="mx-auto max-w-6xl px-4 py-14 sm:px-6 lg:px-8">
        <div className="grid gap-6 lg:grid-cols-[1.35fr_0.65fr]">
          <div className="rounded-2xl border border-slate-200 bg-white p-7 md:p-9">
            <h2 className="text-3xl font-bold">Где возникает эффект</h2>
            <div className="mt-5 space-y-4 text-base leading-7 text-slate-700">
              {service.context.map((paragraph) => <p key={paragraph}>{paragraph}</p>)}
            </div>
          </div>
          <aside className="rounded-2xl bg-slate-900 p-7 text-slate-100 md:p-9">
            <h2 className="text-2xl font-semibold">Что нужно на входе</h2>
            <ul className="mt-5 space-y-3 text-slate-300">
              {service.inputs.map((item) => <li key={item} className="flex gap-3"><span aria-hidden="true" className="text-amber-400">•</span><span>{item}</span></li>)}
            </ul>
          </aside>
        </div>
      </section>

      <section id="workflow" className="border-y border-slate-200 bg-slate-100">
        <div className="mx-auto max-w-6xl px-4 py-14 sm:px-6 lg:px-8">
          <h2 className="text-3xl font-bold">Как строится рабочий контур</h2>
          <p className="mt-4 max-w-3xl text-slate-600">Каждый этап дает проверяемый результат. Масштабирование начинается только после подтверждения качества на реальных данных.</p>
          <ol className="mt-8 grid gap-5 md:grid-cols-2 xl:grid-cols-4">
            {service.workflow.map((step, index) => (
              <li key={step.title} className="rounded-xl border border-slate-200 bg-white p-6">
                <span className="text-sm font-bold text-amber-700">0{index + 1}</span>
                <h3 className="mt-3 text-xl font-semibold">{step.title}</h3>
                <p className="mt-3 text-sm leading-6 text-slate-600">{step.description}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-14 sm:px-6 lg:px-8">
        <div className="grid gap-6 lg:grid-cols-2">
          <div className="rounded-2xl border border-slate-200 bg-white p-7 md:p-9">
            <h2 className="text-2xl font-bold">Результаты проекта</h2>
            <ul className="mt-5 space-y-3 text-slate-700">
              {service.deliverables.map((item) => <li key={item} className="flex gap-3"><span aria-hidden="true" className="text-emerald-700">✓</span><span>{item}</span></li>)}
            </ul>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-white p-7 md:p-9">
            <h2 className="text-2xl font-bold">Как измеряем результат</h2>
            <ul className="mt-5 space-y-3 text-slate-700">
              {service.metrics.map((item) => <li key={item} className="flex gap-3"><span aria-hidden="true" className="text-sky-700">→</span><span>{item}</span></li>)}
            </ul>
          </div>
        </div>
        <div className="mt-6 rounded-2xl border border-amber-200 bg-amber-50 p-7 md:p-9">
          <h2 className="text-2xl font-bold">Контроль и границы AI</h2>
          <ul className="mt-5 grid gap-4 md:grid-cols-3">
            {service.safeguards.map((item) => <li key={item} className="rounded-xl bg-white p-5 text-sm leading-6 text-slate-700">{item}</li>)}
          </ul>
        </div>
      </section>

      <section className="border-y border-slate-200 bg-white">
        <div className="mx-auto max-w-6xl px-4 py-14 sm:px-6 lg:px-8">
          <h2 className="text-3xl font-bold">Частые вопросы</h2>
          <div className="mt-8 grid gap-5 lg:grid-cols-3">
            {service.faq.map((item) => (
              <article key={item.question} className="rounded-xl border border-slate-200 p-6">
                <h3 className="text-lg font-semibold">{item.question}</h3>
                <p className="mt-3 text-sm leading-6 text-slate-600">{item.answer}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-14 sm:px-6 lg:px-8">
        <h2 className="text-3xl font-bold">Связанные материалы и решения</h2>
        <div className="mt-8 grid gap-5 lg:grid-cols-3">
          {service.related.map((item) => item.external ? (
            <a key={item.href} href={item.href} target="_blank" rel="noopener noreferrer" className="rounded-xl border border-slate-200 bg-white p-6 hover:border-amber-400">
              <h3 className="font-semibold text-amber-800">{item.label} →</h3>
              <p className="mt-3 text-sm leading-6 text-slate-600">{item.description}</p>
            </a>
          ) : (
            <Link key={item.href} href={item.href} className="rounded-xl border border-slate-200 bg-white p-6 hover:border-amber-400">
              <h3 className="font-semibold text-amber-800">{item.label} →</h3>
              <p className="mt-3 text-sm leading-6 text-slate-600">{item.description}</p>
            </Link>
          ))}
        </div>
        <p className="mt-8 text-sm text-slate-500">{LEGAL_BRAND} начинает с диагностики процесса и не обещает автоматическое юридическое решение без проверки специалистом.</p>
      </section>

      <LeadCaptureForm />
    </main>
  );
}
