import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Налоговый комплаенс с AI",
  description:
    "AI для налогового комплаенса: мониторинг изменений, анализ налоговых рисков и автоматизация регулярной отчетности.",
  alternates: {
    canonical: "/services/tax-compliance-ai",
  },
  openGraph: {
    title: "Налоговый комплаенс с AI | Legal AI PRO",
    description:
      "Помогаем юридической и финансовой функции быстрее реагировать на изменения налоговой практики.",
    url: "/services/tax-compliance-ai",
    type: "article",
  },
  twitter: {
    card: "summary",
    title: "Налоговый комплаенс с AI | Legal AI PRO",
    description:
      "Помогаем юридической и финансовой функции быстрее реагировать на изменения налоговой практики.",
  },
  robots: {
    index: true,
    follow: true,
  },
};

export default function TaxComplianceAIPage() {
  return (
    <main className="min-h-screen bg-slate-50">
      <section className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
        <p className="text-sm text-slate-500 mb-4">
          <Link href="/services" className="hover:text-amber-600">
            Услуги
          </Link>{" "}
          / Налоговый комплаенс
        </p>

        <h1 className="text-4xl md:text-5xl font-bold text-slate-900 mb-6">
          Налоговый комплаенс с AI
        </h1>
        <p className="text-lg text-slate-600 mb-10">
          Настраиваем систему, которая отслеживает налоговые изменения,
          выявляет риски и помогает команде быстро готовить корректные решения.
        </p>

        <div className="bg-white rounded-2xl border border-slate-200 p-8 mb-8">
          <h2 className="text-2xl font-bold text-slate-900 mb-4">
            Что автоматизируем
          </h2>
          <ul className="space-y-3 text-slate-700">
            <li>Мониторинг изменений в НК РФ и правоприменительной практике.</li>
            <li>Проверка контрагентов и сигнализация налоговых рисков.</li>
            <li>Подготовка материалов для внутренних проверок.</li>
            <li>Регулярные отчеты для юристов и финансового блока.</li>
          </ul>
        </div>

        <div className="bg-white rounded-2xl border border-slate-200 p-8 mb-8">
          <h2 className="text-2xl font-bold text-slate-900 mb-4">
            Результат
          </h2>
          <ul className="space-y-3 text-slate-700">
            <li>Снижение риска пропуска критичных налоговых изменений.</li>
            <li>Более предсказуемый контроль налоговой нагрузки.</li>
            <li>Меньше ручной работы в регулярных проверках.</li>
          </ul>
        </div>

        <div className="flex flex-col sm:flex-row gap-4">
          <a
            href="https://t.me/legal_ai_helper_new_bot?start=consultation"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-block bg-amber-600 hover:bg-amber-700 text-white font-semibold px-8 py-4 rounded-lg text-center"
          >
            Обсудить налоговый контур
          </a>
          <Link
            href="/services/compliance-ai"
            className="inline-block bg-white border border-slate-300 text-slate-700 font-semibold px-8 py-4 rounded-lg text-center hover:bg-slate-100"
          >
            Смотреть общий комплаенс
          </Link>
        </div>
      </section>
    </main>
  );
}
