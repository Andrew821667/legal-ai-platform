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
      description="Какие данные и кому передаются за рубеж: сервисы ИИ для разбора обращений и ответов ассистента, веб-аналитика, Telegram."
      updatedAt={LEGAL_UPDATED_AT}
    >
      <section className="rounded-xl bg-white p-8 shadow-sm">
        <h2 className="mb-4 text-2xl font-bold text-slate-900">1. Когда данные передаются за рубеж</h2>
        <ul className="list-disc space-y-2 pl-6 text-slate-700">
          <li>
            <strong>Юридические обращения</strong> через формы сайта, личного кабинета и Mini App: текст обращения
            передаётся сервису ИИ <strong>OpenAI (США)</strong> для предварительного разбора, который готовится юристу.
            Согласие даётся в самой форме.
          </li>
          <li>
            <strong>Переписка с ассистентом</strong> в Telegram и на сайте: сообщения передаются сервису ИИ{" "}
            <strong>DeepSeek (КНР)</strong> для подготовки ответа. В Telegram-боте это отдельный шаг — согласие на
            AI-режим.
          </li>
          <li>
            <strong>Веб-аналитика Google Analytics (США)</strong> — только после согласия на cookies в баннере сайта.
          </li>
          <li>
            <strong>Telegram</strong>: сообщения в боте и Mini App проходят через инфраструктуру мессенджера.
          </li>
        </ul>
        <p className="mt-4 text-slate-700">
          Паспортные данные и реквизиты документов, удостоверяющих личность, сервисам ИИ не передаются.
        </p>
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
          <li>в Telegram-боте останутся меню и базовые информационные сценарии, AI-ответы будут отключены;</li>
          <li>
            формы обращений на сайте без этого согласия не отправляются — напишите юристу напрямую по{" "}
            <a href={`mailto:${LEGAL_CONTACT_EMAIL}`} className="text-amber-700 underline">
              {LEGAL_CONTACT_EMAIL}
            </a>{" "}
            или позвоните: такое обращение обрабатывается без сервисов ИИ;
          </li>
          <li>без согласия на cookies счётчики аналитики не включаются.</li>
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
