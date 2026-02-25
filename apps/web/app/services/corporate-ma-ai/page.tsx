import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Корпоративное право и M&A с AI",
  description:
    "AI для корпоративного права и сделок M&A: ускорение Due Diligence, анализ структуры и контроль юридических рисков.",
  alternates: {
    canonical: "/services/corporate-ma-ai",
  },
  openGraph: {
    title: "Корпоративное право и M&A с AI | Legal AI PRO",
    description:
      "Помогаем ускорить Due Diligence и принимать решения по сделкам на основе проверенных данных.",
    url: "/services/corporate-ma-ai",
    type: "article",
  },
  twitter: {
    card: "summary",
    title: "Корпоративное право и M&A с AI | Legal AI PRO",
    description:
      "Помогаем ускорить Due Diligence и принимать решения по сделкам на основе проверенных данных.",
  },
  robots: {
    index: true,
    follow: true,
  },
};

export default function CorporateMAPage() {
  return (
    <main className="min-h-screen bg-slate-50">
      <section className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
        <p className="text-sm text-slate-500 mb-4">
          <Link href="/services" className="hover:text-amber-600">
            Услуги
          </Link>{" "}
          / Корпоративное право и M&A
        </p>

        <h1 className="text-4xl md:text-5xl font-bold text-slate-900 mb-6">
          Корпоративное право и M&A с AI
        </h1>
        <p className="text-lg text-slate-600 mb-10">
          Автоматизируем проверку корпоративных документов и ускоряем Due
          Diligence, чтобы сделки не тормозили рост бизнеса.
        </p>

        <div className="bg-white rounded-2xl border border-slate-200 p-8 mb-8">
          <h2 className="text-2xl font-bold text-slate-900 mb-4">
            Что автоматизируем
          </h2>
          <ul className="space-y-3 text-slate-700">
            <li>Пакетный анализ корпоративных документов.</li>
            <li>Выявление юридических рисков и ограничений.</li>
            <li>Структурированные отчеты для руководства и инвесторов.</li>
            <li>Контроль сроков и статусов в сделке.</li>
          </ul>
        </div>

        <div className="bg-white rounded-2xl border border-slate-200 p-8 mb-8">
          <h2 className="text-2xl font-bold text-slate-900 mb-4">
            Эффект для команды
          </h2>
          <ul className="space-y-3 text-slate-700">
            <li>Сокращение времени проверки документов с недель до дней.</li>
            <li>Меньше ручной рутины в корпоративном блоке.</li>
            <li>Более предсказуемый процесс закрытия сделок.</li>
          </ul>
        </div>

        <div className="flex flex-col sm:flex-row gap-4">
          <a
            href="https://t.me/legal_ai_helper_new_bot?start=consultation"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-block bg-amber-600 hover:bg-amber-700 text-white font-semibold px-8 py-4 rounded-lg text-center"
          >
            Обсудить проект
          </a>
          <Link
            href="/cases"
            className="inline-block bg-white border border-slate-300 text-slate-700 font-semibold px-8 py-4 rounded-lg text-center hover:bg-slate-100"
          >
            Посмотреть кейсы
          </Link>
        </div>
      </section>
    </main>
  );
}
