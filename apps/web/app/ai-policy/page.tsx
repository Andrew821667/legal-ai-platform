import type { Metadata } from "next";

import LegalPageFrame from "@/components/LegalPageFrame";
import { LEGAL_BRAND, LEGAL_DOC_LINKS, LEGAL_UPDATED_AT } from "@/lib/legalProfile";
import { createPageMetadata } from "@/lib/seo";

export const metadata: Metadata = createPageMetadata({
  title: "Политика использования ИИ",
  description: "Принципы использования AI-функций и ограничения ответственности в AI Verdict.",
  path: LEGAL_DOC_LINKS.aiPolicy,
  type: "article",
});

export default function AiPolicyPage() {
  return (
    <LegalPageFrame
      title="Политика использования ИИ"
      description="Как в AI Verdict применяются AI-инструменты и какие ограничения нужно учитывать."
      updatedAt={LEGAL_UPDATED_AT}
    >
      <section className="rounded-xl bg-white p-8 shadow-sm">
        <h2 className="mb-4 text-2xl font-bold text-slate-900">1. Что делает AI в проекте</h2>
        <ul className="list-disc space-y-2 pl-6 text-slate-700">
          <li>помогает структурировать входящий запрос;</li>
          <li>готовит черновые ответы, гипотезы и предварительные summary;</li>
          <li>ускоряет диагностику сценариев автоматизации и правовых задач.</li>
        </ul>
      </section>

      <section className="rounded-xl bg-white p-8 shadow-sm">
        <h2 className="mb-4 text-2xl font-bold text-slate-900">2. Что AI не заменяет</h2>
        <div className="space-y-4 text-slate-700">
          <p>
            Материалы и ответы AI в {LEGAL_BRAND} носят информационный и вспомогательный характер.
            Они не заменяют индивидуальную юридическую консультацию, правовую экспертизу документов и
            решение по конкретному кейсу после анализа фактов и применимого права.
          </p>
          <p>
            Окончательные решения по клиентскому кейсу принимаются человеком, а не моделью.
          </p>
        </div>
      </section>

      <section className="rounded-xl bg-white p-8 shadow-sm">
        <h2 className="mb-4 text-2xl font-bold text-slate-900">3. Ограничения для пользователя</h2>
        <ul className="list-disc space-y-2 pl-6 text-slate-700">
          <li>не передавайте без необходимости персональные данные третьих лиц;</li>
          <li>не передавайте документы и сведения, которые нельзя направлять во внешние AI-сервисы;</li>
          <li>проверяйте фактуру, даты, суммы, реквизиты и ссылки на нормы права до использования результата.</li>
        </ul>
      </section>
    </LegalPageFrame>
  );
}
