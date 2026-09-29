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
  title: "Обезличивание перед сервисами ИИ",
  description: "Персональные данные сервисам ИИ не передаются: перед отправкой они заменяются условными метками.",
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
      title="Обезличивание перед сервисами ИИ"
      description="Персональные данные за рубеж не передаются: сервисы ИИ получают текст, из которого они убраны."
      updatedAt={LEGAL_UPDATED_AT}
    >
      <section className="rounded-xl bg-white p-8 shadow-sm">
        <h2 className="mb-4 text-2xl font-bold text-slate-900">1. Что происходит с текстом</h2>
        <div className="space-y-4 text-slate-700">
          <p>
            {LEGAL_BRAND} использует сервисы искусственного интеллекта (OpenAI, DeepSeek) для предварительного разбора
            обращений, который готовится юристу, и для ответов ассистента. Эти сервисы работают за рубежом, поэтому
            персональные данные им не передаются.
          </p>
          <p>
            Перед отправкой текст автоматически обезличивается: данные, по которым можно узнать человека, заменяются
            условными метками вроде [ИМЯ_1] или [ТЕЛЕФОН_1]. Сервис отвечает с метками, а настоящие значения
            подставляются обратно уже у нас. Таблица замен никуда не отправляется.
          </p>
        </div>
      </section>

      <section className="rounded-xl bg-white p-8 shadow-sm">
        <h2 className="mb-4 text-2xl font-bold text-slate-900">2. Что заменяется метками</h2>
        <ul className="list-disc space-y-2 pl-6 text-slate-700">
          <li>фамилии, имена и отчества;</li>
          <li>телефоны, адреса электронной почты, имена в Telegram;</li>
          <li>номера паспорта, ИНН, СНИЛС, ОГРН(ИП), банковских карт и счетов;</li>
          <li>адреса (улица, дом, квартира), даты рождения, номера автомобилей.</li>
        </ul>
        <p className="mt-4 text-slate-700">
          Суть ситуации, даты договоров, суммы, город и суд остаются — без них разбор невозможен. Поэтому не указывайте
          в описании то, что для дела не нужно: паспортные данные, сведения о здоровье, данные посторонних людей.
          Автоматическое обезличивание — дополнительная мера, а не повод их присылать.
        </p>
      </section>

      <section className="rounded-xl bg-white p-8 shadow-sm">
        <h2 className="mb-4 text-2xl font-bold text-slate-900">3. Кто оператор</h2>
        <p className="text-slate-700">
          Оператор: <strong>{LEGAL_OPERATOR_NAME}</strong> ({LEGAL_OPERATOR_STATUS}), проект{" "}
          <strong>{LEGAL_BRAND}</strong>. Порядок обработки персональных данных — в{" "}
          <a href="/privacy" className="text-amber-700 underline">политике конфиденциальности</a>.
        </p>
      </section>

      <section className="rounded-xl bg-white p-8 shadow-sm">
        <h2 className="mb-4 text-2xl font-bold text-slate-900">4. Вопросы и отзыв согласия</h2>
        <p className="text-slate-700">
          Отозвать согласие на обработку персональных данных и запросить их удаление можно через команды бота,
          контактные каналы проекта или по адресу{" "}
          <a href={`mailto:${LEGAL_CONTACT_EMAIL}`} className="text-amber-700 underline">
            {LEGAL_CONTACT_EMAIL}
          </a>
          .
        </p>
      </section>
    </LegalPageFrame>
  );
}
