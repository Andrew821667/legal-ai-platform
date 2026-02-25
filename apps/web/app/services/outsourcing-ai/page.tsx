import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Юридический аутсорсинг с AI",
  description:
    "Гибридная модель: юрист + AI. Передайте рутинные юридические задачи и получите контролируемый результат в срок.",
  alternates: {
    canonical: "/services/outsourcing-ai",
  },
  openGraph: {
    title: "Юридический аутсорсинг с AI | Legal AI PRO",
    description:
      "Сочетаем экспертную юридическую работу и AI-инструменты для снижения нагрузки на команду.",
    url: "/services/outsourcing-ai",
    type: "article",
  },
  twitter: {
    card: "summary",
    title: "Юридический аутсорсинг с AI | Legal AI PRO",
    description:
      "Сочетаем экспертную юридическую работу и AI-инструменты для снижения нагрузки на команду.",
  },
  robots: {
    index: true,
    follow: true,
  },
};

export default function OutsourcingAIPage() {
  return (
    <main className="min-h-screen bg-slate-50">
      <section className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
        <p className="text-sm text-slate-500 mb-4">
          <Link href="/services" className="hover:text-amber-600">
            Услуги
          </Link>{" "}
          / Аутсорсинг + AI
        </p>

        <h1 className="text-4xl md:text-5xl font-bold text-slate-900 mb-6">
          Юридический аутсорсинг + AI
        </h1>
        <p className="text-lg text-slate-600 mb-10">
          Закрываем операционную юридическую нагрузку за счет гибридной модели:
          экспертиза юриста плюс автоматизация рутинных шагов.
        </p>

        <div className="bg-white rounded-2xl border border-slate-200 p-8 mb-8">
          <h2 className="text-2xl font-bold text-slate-900 mb-4">
            Что берём на себя
          </h2>
          <ul className="space-y-3 text-slate-700">
            <li>Поток договоров и претензионную работу.</li>
            <li>Подготовку типовых процессуальных документов.</li>
            <li>Первичный анализ рисков и юридических событий.</li>
            <li>Регулярную отчетность по статусу задач.</li>
          </ul>
        </div>

        <div className="bg-white rounded-2xl border border-slate-200 p-8 mb-8">
          <h2 className="text-2xl font-bold text-slate-900 mb-4">
            Почему это выгодно
          </h2>
          <ul className="space-y-3 text-slate-700">
            <li>Быстрый запуск без долгого найма сотрудников.</li>
            <li>Прозрачная загрузка и предсказуемая стоимость.</li>
            <li>Усиление внутренней команды без перегруза.</li>
          </ul>
        </div>

        <div className="flex flex-col sm:flex-row gap-4">
          <a
            href="https://t.me/legal_ai_helper_new_bot?start=consultation"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-block bg-amber-600 hover:bg-amber-700 text-white font-semibold px-8 py-4 rounded-lg text-center"
          >
            Обсудить формат
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
