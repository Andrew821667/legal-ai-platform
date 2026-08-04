import type { Metadata } from "next";
import Link from "next/link";
import { createPageMetadata } from "@/lib/seo";
import HeroBackdrop from "@/components/HeroBackdrop";

export const metadata: Metadata = createPageMetadata({
  title: "Услуги Legal AI",
  description:
    "Услуги AI Verdict: автоматизация юридической функции, договоры, судебная работа, комплаенс, аналитика, интеграции, боты, сайты и кастомная разработка.",
  path: "/services",
});

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
    title: "Инженерная практика",
    description: "Отдельное направление разработки: боты, сайты, Mini App, программы, AI-модули и интеграции.",
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
  const siteUrl = "https://ai-verdict.ru";
  const itemListSchema = {
    "@context": "https://schema.org",
    "@type": "ItemList",
    name: "Направления внедрения Legal AI",
    itemListElement: serviceLinks.map((item, index) => ({
      "@type": "ListItem",
      position: index + 1,
      name: item.title,
      url: `${siteUrl}${item.href}`,
    })),
  };

  return (
    <main className="min-h-screen bg-slate-50">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(itemListSchema) }} />
      <section className="relative overflow-hidden border-b border-slate-300 bg-slate-100">
        <HeroBackdrop variant="services" tone="light" />
        <div className="relative mx-auto max-w-5xl px-4 pb-20 pt-32 sm:px-6 lg:px-8">
          <h1 className="text-4xl md:text-5xl font-bold text-slate-900 mb-6">
            Услуги AI Verdict
          </h1>
          <p className="max-w-3xl text-lg text-slate-700">
            Основная практика AI Verdict автоматизирует юридическую функцию и связанные бизнес-процессы.
            Обычные правовые задачи ведет отдельная юридическая практика, а самостоятельные программные
            проекты — инженерная практика разработки и интеграций.
          </p>
        </div>
      </section>

      <section className="mx-auto max-w-5xl px-4 py-14 sm:px-6 lg:px-8">
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
            Удаленная работа с командами в регионах
          </h2>
          <p className="text-slate-600 mb-4">
            Диагностику и часть этапов внедрения можно проводить удаленно.
            Региональный раздел показывает типовые задачи и не означает наличие локальных офисов.
          </p>
          <Link href="/regions" className="text-amber-600 font-semibold">
            Перейти к регионам →
          </Link>
        </div>
      </section>
    </main>
  );
}
