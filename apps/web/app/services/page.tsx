import type { Metadata } from "next";
import Link from "next/link";
import { createPageMetadata } from "@/lib/seo";
import HeroBackdrop from "@/components/HeroBackdrop";

export const metadata: Metadata = createPageMetadata({
  title: "Юридическая помощь, разработка и услуги Legal AI",
  description:
    "Услуги AI Verdict на стыке юридической и инженерной практик: Legal AI, автоматизация юрфункции, юридическая помощь, разработка программ и интеграций.",
  path: "/services",
});

const automationServices = [
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

const legalServices = [
  {
    title: "Юридическая помощь бизнесу",
    description: "Договоры, корпоративные вопросы, споры, долги, трудовые и другие правовые задачи компании.",
    href: "/legal-help/business",
  },
  {
    title: "Юридическая помощь частным лицам",
    description: "Недвижимость, семейные и наследственные дела, долги, трудовые вопросы и судебные споры.",
    href: "/legal-help/individuals",
  },
  {
    title: "Консультация юриста онлайн",
    description: "Дистанционный разбор ситуации по российскому праву с согласованием формата, срока и стоимости.",
    href: "/legal-help/online-consultation",
  },
  {
    title: "Юридическая помощь по регионам",
    description: "Дистанционная работа с проверкой подсудности, способов подачи документов и необходимости очного участия.",
    href: "/legal-help/regions",
  },
];

const engineeringServices = [
  {
    title: "Разработка программ, AI-сервисов и интеграций",
    description: "Боты, сайты, Mini App, внутренние программы, AI-модули и интеграции вокруг измеримого бизнес-процесса.",
    href: "/engineering",
  },
];

const serviceGroups = [
  {
    id: "automation",
    label: "Ключевое пересечение практик",
    title: "Автоматизация юридической функции",
    description:
      "Юристы определяют логику, риски и контрольные точки, а инженеры превращают процесс в рабочую систему с AI, интерфейсами и интеграциями.",
    items: automationServices,
  },
  {
    id: "legal-practice",
    label: "Самостоятельное направление",
    title: "Юридическая практика",
    description:
      "Практическая юридическая помощь компаниям, предпринимателям и частным клиентам в дистанционном формате по России.",
    items: legalServices,
  },
  {
    id: "engineering-practice",
    label: "Самостоятельное направление",
    title: "Инженерная практика",
    description:
      "End-to-end разработка прикладных систем для задач бизнеса — от диагностики и архитектуры до запуска и поддержки.",
    items: engineeringServices,
  },
];

const serviceLinks = serviceGroups.flatMap((group) => group.items);

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
        <HeroBackdrop variant="home" tone="light" priority />
        <div className="relative mx-auto flex min-h-[560px] max-w-7xl items-center px-4 pb-14 pt-24 sm:min-h-[500px] sm:px-6 sm:py-28 lg:px-8">
          <div>
            <p className="text-sm font-semibold text-amber-700">Две практики и их ключевое пересечение</p>
          <h1 className="text-4xl md:text-5xl font-bold text-slate-900 mb-6">
            Услуги AI Verdict
          </h1>
          <p className="max-w-3xl text-lg text-slate-700">
            AI Verdict объединяет юридическую и инженерную практики. На их стыке команда автоматизирует юридическую
            функцию и внедряет Legal AI. Вне совместного контура юридическая практика решает правовые задачи,
            а инженерная создает прикладные программные системы и интеграции.
          </p>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 py-14 sm:px-6 lg:px-8">
        <div className="space-y-16">
          {serviceGroups.map((group) => (
            <section key={group.id} id={group.id} aria-labelledby={`${group.id}-title`}>
              <div className="max-w-3xl">
                <p className="text-sm font-semibold text-amber-700">{group.label}</p>
                <h2 id={`${group.id}-title`} className="mt-2 text-3xl font-bold text-slate-950">{group.title}</h2>
                <p className="mt-4 leading-7 text-slate-600">{group.description}</p>
              </div>
              <div className={`mt-8 grid gap-6 ${group.items.length === 1 ? "lg:grid-cols-1" : "md:grid-cols-2 lg:grid-cols-3"}`}>
                {group.items.map((item) => (
                  <Link
                    key={item.href}
                    href={item.href}
                    className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm transition-all hover:-translate-y-0.5 hover:border-amber-400 hover:shadow-md"
                  >
                    <h3 className="text-xl font-semibold text-slate-900">{item.title}</h3>
                    <p className="mt-3 text-slate-600">{item.description}</p>
                    <span className="mt-5 inline-flex font-semibold text-amber-700">Подробнее →</span>
                  </Link>
                ))}
              </div>
            </section>
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
