import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Услуги Legal AI",
  description:
    "Услуги Legal AI PRO: договоры, судебная работа, M&A, комплаенс, налоги, аналитика и кастомные AI-решения для юротдела.",
  alternates: {
    canonical: "/services",
  },
  openGraph: {
    title: "Услуги Legal AI | Legal AI PRO",
    description:
      "Выберите направление автоматизации: договоры, судебная работа, M&A, комплаенс, аналитика и другие услуги.",
    url: "/services",
    type: "website",
  },
  twitter: {
    card: "summary",
    title: "Услуги Legal AI | Legal AI PRO",
    description:
      "Выберите направление автоматизации: договоры, судебная работа, M&A, комплаенс, аналитика и другие услуги.",
  },
  robots: {
    index: true,
    follow: true,
  },
};

const serviceLinks = [
  {
    title: "Автоматизация договорной работы",
    description: "Проверка договоров, выявление рисков, ускорение согласования.",
    href: "/services/contracts-ai",
  },
  {
    title: "Автоматизация судебной работы",
    description:
      "Поиск практики, подготовка документов и контроль сроков по делам.",
    href: "/services/litigation-ai",
  },
  {
    title: "Автоматизация комплаенса",
    description:
      "Мониторинг изменений законодательства и контроль комплаенс-рисков.",
    href: "/services/compliance-ai",
  },
  {
    title: "Корпоративное право и M&A",
    description: "Ускорение Due Diligence и анализ корпоративных рисков.",
    href: "/services/corporate-ma-ai",
  },
  {
    title: "Земельное право",
    description: "Проверка документов и сопровождение сделок с землей.",
    href: "/services/land-law-ai",
  },
  {
    title: "Юридическая аналитика",
    description: "Риск-дашборды, KPI и управленческая аналитика юротдела.",
    href: "/services/legal-analytics-ai",
  },
  {
    title: "Кастомные AI-решения",
    description: "Интеграции и сценарии автоматизации под ваши процессы.",
    href: "/services/custom-ai",
  },
  {
    title: "Аутсорсинг + AI",
    description: "Гибридная модель: юридическая экспертиза и автоматизация.",
    href: "/services/outsourcing-ai",
  },
  {
    title: "Налоговый комплаенс",
    description: "Мониторинг налоговых изменений и оценка рисков.",
    href: "/services/tax-compliance-ai",
  },
];

export default function ServicesPage() {
  return (
    <main className="min-h-screen bg-slate-50">
      <section className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
        <h1 className="text-4xl md:text-5xl font-bold text-slate-900 mb-6">
          Услуги Legal AI PRO
        </h1>
        <p className="text-lg text-slate-600 mb-10">
          Выберите направление и посмотрите, как AI может помочь вашему
          юридическому отделу.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {serviceLinks.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm hover:shadow-md transition-shadow"
            >
              <h2 className="text-xl font-semibold text-slate-900 mb-3">
                {item.title}
              </h2>
              <p className="text-slate-600 mb-4">{item.description}</p>
              <span className="text-amber-600 font-semibold">Подробнее →</span>
            </Link>
          ))}
        </div>

        <div className="mt-12 bg-white rounded-2xl border border-slate-200 p-8">
          <h2 className="text-2xl font-bold text-slate-900 mb-3">
            Региональные страницы
          </h2>
          <p className="text-slate-600 mb-4">
            Для локального поиска мы сделали отдельные страницы под ключевые
            регионы: Москва, Санкт-Петербург, Краснодарский край,
            Ставропольский край, Воронежская и Новосибирская области и другие.
          </p>
          <Link href="/regions" className="text-amber-600 font-semibold">
            Перейти к регионам →
          </Link>
        </div>
      </section>
    </main>
  );
}
