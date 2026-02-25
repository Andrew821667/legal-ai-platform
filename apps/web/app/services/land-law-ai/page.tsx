import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Автоматизация земельного права с AI",
  description:
    "AI для задач земельного права: анализ правоустанавливающих документов, проверка рисков и сопровождение сделок с землей.",
  alternates: {
    canonical: "/services/land-law-ai",
  },
  openGraph: {
    title: "Автоматизация земельного права с AI | Legal AI PRO",
    description:
      "Снижаем риски в земельных сделках и ускоряем проверку документации.",
    url: "/services/land-law-ai",
    type: "article",
  },
  twitter: {
    card: "summary",
    title: "Автоматизация земельного права с AI | Legal AI PRO",
    description:
      "Снижаем риски в земельных сделках и ускоряем проверку документации.",
  },
  robots: {
    index: true,
    follow: true,
  },
};

export default function LandLawAIPage() {
  return (
    <main className="min-h-screen bg-slate-50">
      <section className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
        <p className="text-sm text-slate-500 mb-4">
          <Link href="/services" className="hover:text-amber-600">
            Услуги
          </Link>{" "}
          / Земельное право
        </p>

        <h1 className="text-4xl md:text-5xl font-bold text-slate-900 mb-6">
          Автоматизация земельного права с AI
        </h1>
        <p className="text-lg text-slate-600 mb-10">
          Помогаем быстрее анализировать земельные документы, проверять
          ограничения и сопровождать сделки без лишнего риска.
        </p>

        <div className="bg-white rounded-2xl border border-slate-200 p-8 mb-8">
          <h2 className="text-2xl font-bold text-slate-900 mb-4">
            Где AI помогает
          </h2>
          <ul className="space-y-3 text-slate-700">
            <li>Проверка правоустанавливающих документов и обременений.</li>
            <li>Подготовка материалов для сделок и аренды.</li>
            <li>Быстрый разбор кадастровых данных и истории объекта.</li>
            <li>Выявление спорных условий до подписания документов.</li>
          </ul>
        </div>

        <div className="bg-white rounded-2xl border border-slate-200 p-8 mb-8">
          <h2 className="text-2xl font-bold text-slate-900 mb-4">
            Кому подходит
          </h2>
          <ul className="space-y-3 text-slate-700">
            <li>Агробизнесу и девелоперским компаниям.</li>
            <li>Юротделам с большим объемом сделок по земле.</li>
            <li>Командам, которым нужен быстрый due diligence участков.</li>
          </ul>
        </div>

        <div className="flex flex-col sm:flex-row gap-4">
          <a
            href="https://t.me/legal_ai_helper_new_bot?start=consultation"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-block bg-amber-600 hover:bg-amber-700 text-white font-semibold px-8 py-4 rounded-lg text-center"
          >
            Получить консультацию
          </a>
          <Link
            href="/services/corporate-ma-ai"
            className="inline-block bg-white border border-slate-300 text-slate-700 font-semibold px-8 py-4 rounded-lg text-center hover:bg-slate-100"
          >
            Смотреть M&A направление
          </Link>
        </div>
      </section>
    </main>
  );
}
