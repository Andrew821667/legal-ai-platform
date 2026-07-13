import type { Metadata } from "next";
import Link from "next/link";
import LeadCaptureForm from "@/components/LeadCaptureForm";
import { createPageMetadata } from "@/lib/seo";
import { contractAIEntryHref } from "@/lib/links";

export const metadata: Metadata = createPageMetadata({
  title: "Внедрение AI в договорную работу",
  description:
    "Консалтинг по внедрению AI в договорный процесс: диагностика, правила проверки, пилот, метрики и интеграция в работу юридической команды.",
  path: "/services/contracts-ai",
  type: "article",
});

export default function ContractsAIPage() {
  return (
    <main className="min-h-screen bg-slate-50">
      <section className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
        <p className="text-sm text-slate-500 mb-4">
          <Link href="/services" className="hover:text-amber-600">
            Услуги
          </Link>{" "}
          / Автоматизация договоров
        </p>

        <h1 className="text-4xl md:text-5xl font-bold text-slate-900 mb-6">
          Автоматизация договорной работы с AI
        </h1>
        <p className="text-lg text-slate-600 mb-10">
          Помогаем юридической команде быстрее проверять договоры, видеть риски
          до подписания и сокращать время согласования.
        </p>

        <div className="bg-white rounded-2xl border border-slate-200 p-8 mb-8">
          <h2 className="text-2xl font-bold text-slate-900 mb-4">
            Что вы получаете
          </h2>
          <ul className="space-y-3 text-slate-700">
            <li>Ускорение первого прохода по договору и выделение зон внимания.</li>
            <li>Подсветка рисков и спорных формулировок.</li>
            <li>Шаблоны и единые правила согласования для команды.</li>
            <li>Протоколы разногласий и комментарии в удобном виде.</li>
          </ul>
        </div>

        <div className="mb-8 rounded-2xl border border-sky-200 bg-sky-50 p-8">
          <h2 className="text-2xl font-bold text-slate-900 mb-3">Нужен готовый сервис для проверки договора?</h2>
          <p className="text-slate-700 mb-5">
            Эта страница посвящена внедрению процесса в юридическую команду. Самостоятельный анализ документов
            доступен в отдельном продукте Contract AI System на домене contract.ai-verdict.ru.
          </p>
          <a
            href={contractAIEntryHref("demo")}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex rounded-lg bg-sky-700 px-6 py-3 font-semibold text-white hover:bg-sky-800"
          >
            Проверить договор в Contract AI System →
          </a>
        </div>

        <div className="bg-white rounded-2xl border border-slate-200 p-8 mb-8">
          <h2 className="text-2xl font-bold text-slate-900 mb-4">
            Когда это особенно полезно
          </h2>
          <ul className="space-y-3 text-slate-700">
            <li>Большой поток типовых договоров каждый месяц.</li>
            <li>Много согласований между юристами и бизнесом.</li>
            <li>Нужен быстрый контроль качества документов.</li>
          </ul>
        </div>

        <div className="flex flex-col sm:flex-row gap-4">
          <a
            href="#lead-form"
            className="inline-block bg-amber-600 hover:bg-amber-700 text-white font-semibold px-8 py-4 rounded-lg text-center"
          >
            Обсудить внедрение
          </a>
          <Link
            href="/cases"
            className="inline-block bg-white border border-slate-300 text-slate-700 font-semibold px-8 py-4 rounded-lg text-center hover:bg-slate-100"
          >
            Посмотреть сценарии
          </Link>
        </div>
      </section>

      <LeadCaptureForm />
    </main>
  );
}
