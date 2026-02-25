import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Кастомные AI-решения для юротдела",
  description:
    "Разработка кастомных AI-решений для юридических команд: интеграции с 1С/CRM, свои сценарии, контроль безопасности.",
  alternates: {
    canonical: "/services/custom-ai",
  },
  openGraph: {
    title: "Кастомные AI-решения для юротдела | Legal AI PRO",
    description:
      "Создаем AI-инструменты под ваши процессы, а не под шаблонный рынок.",
    url: "/services/custom-ai",
    type: "article",
  },
  twitter: {
    card: "summary",
    title: "Кастомные AI-решения для юротдела | Legal AI PRO",
    description:
      "Создаем AI-инструменты под ваши процессы, а не под шаблонный рынок.",
  },
  robots: {
    index: true,
    follow: true,
  },
};

export default function CustomAIPage() {
  return (
    <main className="min-h-screen bg-slate-50">
      <section className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
        <p className="text-sm text-slate-500 mb-4">
          <Link href="/services" className="hover:text-amber-600">
            Услуги
          </Link>{" "}
          / Кастомные AI-решения
        </p>

        <h1 className="text-4xl md:text-5xl font-bold text-slate-900 mb-6">
          Кастомные AI-решения для юридического отдела
        </h1>
        <p className="text-lg text-slate-600 mb-10">
          Проектируем и внедряем AI-инструменты под ваши внутренние процессы,
          бизнес-правила и требования безопасности.
        </p>

        <div className="bg-white rounded-2xl border border-slate-200 p-8 mb-8">
          <h2 className="text-2xl font-bold text-slate-900 mb-4">
            Что можно сделать
          </h2>
          <ul className="space-y-3 text-slate-700">
            <li>AI-ассистент для внутренней юридической базы знаний.</li>
            <li>Интеграции с 1С, CRM, ЭДО и корпоративными системами.</li>
            <li>Сценарии согласования и проверки документов под ваш регламент.</li>
            <li>On-premise или облачное размещение.</li>
          </ul>
        </div>

        <div className="bg-white rounded-2xl border border-slate-200 p-8 mb-8">
          <h2 className="text-2xl font-bold text-slate-900 mb-4">
            Почему кастомный подход
          </h2>
          <ul className="space-y-3 text-slate-700">
            <li>Готовые продукты не учитывают ваши внутренние нюансы.</li>
            <li>Свой процесс = выше точность и быстрее окупаемость.</li>
            <li>Можно развивать решение поэтапно без резкого риска.</li>
          </ul>
        </div>

        <div className="flex flex-col sm:flex-row gap-4">
          <a
            href="https://t.me/legal_ai_helper_new_bot?start=consultation"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-block bg-amber-600 hover:bg-amber-700 text-white font-semibold px-8 py-4 rounded-lg text-center"
          >
            Запросить аудит задач
          </a>
          <Link
            href="/services/legal-analytics-ai"
            className="inline-block bg-white border border-slate-300 text-slate-700 font-semibold px-8 py-4 rounded-lg text-center hover:bg-slate-100"
          >
            Смотреть юридическую аналитику
          </Link>
        </div>
      </section>
    </main>
  );
}
