import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Юридическая аналитика с AI",
  description:
    "AI-аналитика для юридического отдела: риск-дашборды, KPI и прогнозы по портфелю договоров и споров.",
  alternates: {
    canonical: "/services/legal-analytics-ai",
  },
  openGraph: {
    title: "Юридическая аналитика с AI | Legal AI PRO",
    description:
      "Преобразуем юридические данные в дашборды и метрики для управленческих решений.",
    url: "/services/legal-analytics-ai",
    type: "article",
  },
  twitter: {
    card: "summary",
    title: "Юридическая аналитика с AI | Legal AI PRO",
    description:
      "Преобразуем юридические данные в дашборды и метрики для управленческих решений.",
  },
  robots: {
    index: true,
    follow: true,
  },
};

export default function LegalAnalyticsAIPage() {
  return (
    <main className="min-h-screen bg-slate-50">
      <section className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
        <p className="text-sm text-slate-500 mb-4">
          <Link href="/services" className="hover:text-amber-600">
            Услуги
          </Link>{" "}
          / Юридическая аналитика
        </p>

        <h1 className="text-4xl md:text-5xl font-bold text-slate-900 mb-6">
          Юридическая аналитика с AI
        </h1>
        <p className="text-lg text-slate-600 mb-10">
          Строим систему показателей для юротдела: где риски, где потери
          времени и какие процессы стоит автоматизировать в первую очередь.
        </p>

        <div className="bg-white rounded-2xl border border-slate-200 p-8 mb-8">
          <h2 className="text-2xl font-bold text-slate-900 mb-4">
            Что получаете
          </h2>
          <ul className="space-y-3 text-slate-700">
            <li>Дашборды по договорам, спорам и срокам.</li>
            <li>Приоритизация рисков по важности для бизнеса.</li>
            <li>KPI юридической функции в одном окне.</li>
            <li>Отчеты для руководства и планирования ресурсов.</li>
          </ul>
        </div>

        <div className="bg-white rounded-2xl border border-slate-200 p-8 mb-8">
          <h2 className="text-2xl font-bold text-slate-900 mb-4">
            Когда это особенно полезно
          </h2>
          <ul className="space-y-3 text-slate-700">
            <li>Нужно обосновать бюджет и приоритеты юротдела.</li>
            <li>Нужен прозрачный контроль рисков для менеджмента.</li>
            <li>Есть разрозненные данные и нет единой картины.</li>
          </ul>
        </div>

        <div className="flex flex-col sm:flex-row gap-4">
          <a
            href="https://t.me/legal_ai_helper_new_bot?start=consultation"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-block bg-amber-600 hover:bg-amber-700 text-white font-semibold px-8 py-4 rounded-lg text-center"
          >
            Обсудить аналитику
          </a>
          <Link
            href="/services/custom-ai"
            className="inline-block bg-white border border-slate-300 text-slate-700 font-semibold px-8 py-4 rounded-lg text-center hover:bg-slate-100"
          >
            Смотреть кастомные решения
          </Link>
        </div>
      </section>
    </main>
  );
}
