import type { Metadata } from "next";

import LegalPageFrame from "@/components/LegalPageFrame";
import {
  LEGAL_BRAND,
  LEGAL_CONTACT_EMAIL,
  LEGAL_DOC_LINKS,
  LEGAL_OPERATOR_NAME,
  LEGAL_OPERATOR_STATUS,
  LEGAL_UPDATED_AT,
} from "@/lib/legalProfile";

export const metadata: Metadata = {
  title: "Согласие на трансграничную передачу данных",
  description: "Условия включения AI-режима и трансграничной передачи данных в AI Verdict.",
  alternates: {
    canonical: LEGAL_DOC_LINKS.transborderConsent,
  },
  robots: {
    index: false,
    follow: true,
    nocache: true,
  },
};

export default function TransborderConsentPage() {
  return (
    <LegalPageFrame
      title="Согласие на трансграничную передачу данных"
      description="Условия использования внешних AI-сервисов и трансграничной передачи данных при включении AI-режима."
      updatedAt={LEGAL_UPDATED_AT}
    >
      <section className="rounded-xl bg-white p-8 shadow-sm">
        <h2 className="mb-4 text-2xl font-bold text-slate-900">1. Когда это согласие нужно</h2>
        <div className="space-y-4 text-slate-700">
          <p>
            Это согласие относится к сценариям, где {LEGAL_BRAND} использует внешние AI-сервисы для
            анализа запроса, текста сообщения или подготовительных материалов пользователя.
          </p>
          <p>
            Если AI-режим не включается, базовые сценарии сайта и бота остаются доступны без
            трансграничной передачи данных.
          </p>
        </div>
      </section>

      <section className="rounded-xl bg-white p-8 shadow-sm">
        <h2 className="mb-4 text-2xl font-bold text-slate-900">2. Кто действует как оператор</h2>
        <p className="text-slate-700">
          Оператор: <strong>{LEGAL_OPERATOR_NAME}</strong> ({LEGAL_OPERATOR_STATUS}), проект{" "}
          <strong>{LEGAL_BRAND}</strong>.
        </p>
      </section>

      <section className="rounded-xl bg-white p-8 shadow-sm">
        <h2 className="mb-4 text-2xl font-bold text-slate-900">3. Что может передаваться</h2>
        <ul className="list-disc space-y-2 pl-6 text-slate-700">
          <li>текст вашего сообщения и части диалога, нужные для ответа или анализа;</li>
          <li>фрагменты описания задачи, контекста и приложенных материалов;</li>
          <li>технические метаданные запроса, которые использует AI-провайдер.</li>
        </ul>
        <p className="mt-4 text-slate-700">
          Не присылайте без необходимости персональные данные третьих лиц, паспортные реквизиты,
          коммерческую тайну и материалы, которые нельзя направлять во внешние сервисы.
        </p>
      </section>

      <section className="rounded-xl bg-white p-8 shadow-sm">
        <h2 className="mb-4 text-2xl font-bold text-slate-900">4. Что будет, если не соглашаться</h2>
        <ul className="list-disc space-y-2 pl-6 text-slate-700">
          <li>вы сможете пользоваться меню и базовыми информационными сценариями;</li>
          <li>сможете оставить заявку и перейти в ручную обработку командой;</li>
          <li>AI-разбор и AI-ответ по содержанию сообщения будут отключены.</li>
        </ul>
      </section>

      <section className="rounded-xl bg-white p-8 shadow-sm">
        <h2 className="mb-4 text-2xl font-bold text-slate-900">5. Как отозвать согласие</h2>
        <p className="text-slate-700">
          Вы можете отозвать согласие и запросить удаление/анонимизацию данных через команды бота,
          через контактные каналы проекта или по адресу{" "}
          <a href={`mailto:${LEGAL_CONTACT_EMAIL}`} className="text-amber-700 underline">
            {LEGAL_CONTACT_EMAIL}
          </a>
          .
        </p>
      </section>
    </LegalPageFrame>
  );
}
