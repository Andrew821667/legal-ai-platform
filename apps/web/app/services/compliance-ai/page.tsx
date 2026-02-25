import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Автоматизация комплаенса с AI",
  description:
    "AI для комплаенса: мониторинг изменений законодательства, контроль рисков и повышение прозрачности процессов.",
  alternates: {
    canonical: "/services/compliance-ai",
  },
  openGraph: {
    title: "Автоматизация комплаенса с AI | Legal AI PRO",
    description:
      "Помогаем выстроить системный комплаенс-контроль и снизить риски нарушений.",
    url: "/services/compliance-ai",
    type: "article",
  },
  twitter: {
    card: "summary",
    title: "Автоматизация комплаенса с AI | Legal AI PRO",
    description:
      "Помогаем выстроить системный комплаенс-контроль и снизить риски нарушений.",
  },
  robots: {
    index: true,
    follow: true,
  },
};

export default function ComplianceAIPage() {
  return (
    <main className="min-h-screen bg-slate-50">
      <section className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
        <p className="text-sm text-slate-500 mb-4">
          <Link href="/services" className="hover:text-amber-600">
            Услуги
          </Link>{" "}
          / Комплаенс
        </p>

        <h1 className="text-4xl md:text-5xl font-bold text-slate-900 mb-6">
          Автоматизация комплаенса с AI
        </h1>
        <p className="text-lg text-slate-600 mb-10">
          Настраиваем постоянный контроль изменений и рисков, чтобы команда
          работала уверенно и без лишней ручной нагрузки.
        </p>

        <div className="bg-white rounded-2xl border border-slate-200 p-8 mb-8">
          <h2 className="text-2xl font-bold text-slate-900 mb-4">
            Что автоматизируем
          </h2>
          <ul className="space-y-3 text-slate-700">
            <li>Мониторинг изменений законодательства и требований.</li>
            <li>Санкционный и антикоррупционный контроль.</li>
            <li>Проверка контрагентов и фиксация рисков.</li>
            <li>Отчеты и дашборды для руководства.</li>
          </ul>
        </div>

        <div className="bg-white rounded-2xl border border-slate-200 p-8 mb-8">
          <h2 className="text-2xl font-bold text-slate-900 mb-4">
            Результат для бизнеса
          </h2>
          <ul className="space-y-3 text-slate-700">
            <li>Меньше ручной рутины в комплаенс-процедурах.</li>
            <li>Снижение риска пропуска критичных изменений.</li>
            <li>Прозрачная картина рисков для менеджмента.</li>
          </ul>
        </div>

        <div className="flex flex-col sm:flex-row gap-4">
          <a
            href="https://t.me/legal_ai_helper_new_bot?start=consultation"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-block bg-amber-600 hover:bg-amber-700 text-white font-semibold px-8 py-4 rounded-lg text-center"
          >
            Обсудить задачу
          </a>
          <Link
            href="/services/litigation-ai"
            className="inline-block bg-white border border-slate-300 text-slate-700 font-semibold px-8 py-4 rounded-lg text-center hover:bg-slate-100"
          >
            Смотреть судебную автоматизацию
          </Link>
        </div>
      </section>
    </main>
  );
}
