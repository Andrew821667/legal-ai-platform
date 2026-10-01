import type { Metadata } from "next";

import LegalPageFrame from "@/components/LegalPageFrame";
import {
  LEGAL_BRAND,
  LEGAL_CONTACT_EMAIL,
  LEGAL_CONTACT_PHONE,
  LEGAL_DOC_LINKS,
  LEGAL_OPERATOR_INN,
  LEGAL_OPERATOR_NAME,
  LEGAL_SITE_URL,
  LEGAL_UPDATED_AT,
} from "@/lib/legalProfile";

export const metadata: Metadata = {
  title: "Согласие на обработку персональных данных",
  description: "Текст согласия на обработку персональных данных, которое даётся в формах сайта, личном кабинете и Mini App.",
  alternates: { canonical: LEGAL_DOC_LINKS.pdConsent },
  robots: { index: false, follow: true, nocache: true },
};

/**
 * Согласие оформлено отдельным документом (ч. 1 ст. 9 152-ФЗ): конкретное,
 * информированное. Галочка в формах ссылается сюда (PdConsentText).
 */
export default function PdConsentPage() {
  return (
    <LegalPageFrame
      title="Согласие на обработку персональных данных"
      description="Что вы разрешаете, отмечая согласие в форме обращения, в личном кабинете или в Mini App."
      updatedAt={LEGAL_UPDATED_AT}
    >
      <section className="rounded-xl bg-white p-8 shadow-sm">
        <div className="space-y-4 text-slate-700">
          <p>
            Отмечая согласие в форме на сайте {LEGAL_SITE_URL.replace(/^https?:\/\//, "")}, в личном кабинете или в
            Mini App, я свободно, своей волей и в своём интересе даю согласие оператору —{" "}
            <strong>{LEGAL_OPERATOR_NAME}</strong>, ИНН {LEGAL_OPERATOR_INN} (проект {LEGAL_BRAND}), — на обработку моих
            персональных данных на следующих условиях.
          </p>
        </div>
      </section>

      <section className="rounded-xl bg-white p-8 shadow-sm">
        <h2 className="mb-4 text-2xl font-bold text-slate-900">1. Какие данные</h2>
        <ul className="list-disc space-y-2 pl-6 text-slate-700">
          <li>имя, фамилия, отчество;</li>
          <li>телефон, адрес электронной почты, имя пользователя и идентификатор в Telegram;</li>
          <li>название организации и должность, если обращаюсь от организации;</li>
          <li>описание обращения и переписка по нему;</li>
          <li>данные учётной записи Яндекс ID при входе в личный кабинет: идентификатор, логин, имя, адрес почты.</li>
        </ul>
      </section>

      <section className="rounded-xl bg-white p-8 shadow-sm">
        <h2 className="mb-4 text-2xl font-bold text-slate-900">2. Для чего</h2>
        <p className="text-slate-700">
          Рассмотреть моё обращение, связаться со мной, подготовить и обсудить предложение об услугах, вести мои
          обращения в личном кабинете.
        </p>
      </section>

      <section className="rounded-xl bg-white p-8 shadow-sm">
        <h2 className="mb-4 text-2xl font-bold text-slate-900">3. Что оператор может делать с данными</h2>
        <p className="text-slate-700">
          Сбор, запись, систематизация, накопление, хранение, уточнение, извлечение, использование, обезличивание,
          блокирование, удаление и уничтожение — с использованием средств автоматизации и без них. Для разбора
          обращения оператор использует сервисы искусственного интеллекта, расположенные за рубежом; им направляется
          только текст, из которого автоматически удалены сведения, прямо указывающие на меня (подробнее —{" "}
          <a href={LEGAL_DOC_LINKS.transborderConsent} className="text-amber-700 underline">об обезличивании</a>). Третьим
          лицам данные передаются только в случаях, указанных в{" "}
          <a href={LEGAL_DOC_LINKS.privacy} className="text-amber-700 underline">политике конфиденциальности</a>.
        </p>
      </section>

      <section className="rounded-xl bg-white p-8 shadow-sm">
        <h2 className="mb-4 text-2xl font-bold text-slate-900">4. Срок и отзыв</h2>
        <div className="space-y-4 text-slate-700">
          <p>
            Согласие действует до его отзыва, но не более 3 лет с моего последнего обращения. Если со мной заключён
            договор, данные по нему обрабатываются на основании договора и закона в сроки, указанные в политике
            конфиденциальности.
          </p>
          <p>
            Отозвать согласие можно в любой момент: командой /revoke_consent в Telegram-боте, по телефону{" "}
            {LEGAL_CONTACT_PHONE} или письмом на{" "}
            <a href={`mailto:${LEGAL_CONTACT_EMAIL}`} className="text-amber-700 underline">{LEGAL_CONTACT_EMAIL}</a>. После
            отзыва обработка прекращается, а данные уничтожаются или обезличиваются в течение 30 дней, кроме тех,
            которые оператор обязан хранить по закону или договору (ч. 5 ст. 21 152-ФЗ).
          </p>
        </div>
      </section>
    </LegalPageFrame>
  );
}
