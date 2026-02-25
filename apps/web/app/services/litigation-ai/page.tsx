import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Автоматизация судебной работы с AI",
  description:
    "AI для судебной работы: поиск практики, генерация документов и контроль сроков по делам.",
  alternates: {
    canonical: "/services/litigation-ai",
  },
  openGraph: {
    title: "Автоматизация судебной работы с AI | Legal AI PRO",
    description:
      "Помогаем юристам ускорить судебные процессы и снизить риск пропуска важных событий.",
    url: "/services/litigation-ai",
    type: "article",
  },
  twitter: {
    card: "summary",
    title: "Автоматизация судебной работы с AI | Legal AI PRO",
    description:
      "Помогаем юристам ускорить судебные процессы и снизить риск пропуска важных событий.",
  },
  robots: {
    index: true,
    follow: true,
  },
};

export default function LitigationAIPage() {
  return (
    <main className="min-h-screen bg-slate-50">
      <section className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
        <p className="text-sm text-slate-500 mb-4">
          <Link href="/services" className="hover:text-amber-600">
            Услуги
          </Link>{" "}
          / Судебная работа
        </p>

        <h1 className="text-4xl md:text-5xl font-bold text-slate-900 mb-6">
          Автоматизация судебной работы с AI
        </h1>
        <p className="text-lg text-slate-600 mb-10">
          Упрощаем подготовку к процессу: быстрее ищем практику, готовим
          документы и контролируем сроки.
        </p>

        <div className="bg-white rounded-2xl border border-slate-200 p-8 mb-8">
          <h2 className="text-2xl font-bold text-slate-900 mb-4">
            Что входит
          </h2>
          <ul className="space-y-3 text-slate-700">
            <li>Поиск релевантной судебной практики по делу.</li>
            <li>Подготовка проектов исков, отзывов и ходатайств.</li>
            <li>Мониторинг карточек дел и событий в процессе.</li>
            <li>Напоминания о сроках и контроль статусов.</li>
          </ul>
        </div>

        <div className="bg-white rounded-2xl border border-slate-200 p-8 mb-8">
          <h2 className="text-2xl font-bold text-slate-900 mb-4">
            Для кого подходит
          </h2>
          <ul className="space-y-3 text-slate-700">
            <li>Юротделы с большим судебным портфелем.</li>
            <li>Команды, которым важна скорость подготовки документов.</li>
            <li>Компании, где критичен контроль процессуальных сроков.</li>
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
            href="/services/contracts-ai"
            className="inline-block bg-white border border-slate-300 text-slate-700 font-semibold px-8 py-4 rounded-lg text-center hover:bg-slate-100"
          >
            Смотреть услугу по договорам
          </Link>
        </div>
      </section>
    </main>
  );
}
