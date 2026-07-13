import type { Metadata } from "next";

import LegalPageFrame from "@/components/LegalPageFrame";
import {
  LEGAL_BRAND,
  LEGAL_CONTACT_EMAIL,
  LEGAL_DOC_LINKS,
  LEGAL_UPDATED_AT,
} from "@/lib/legalProfile";

export const metadata: Metadata = {
  title: "Согласие на рассылки",
  description: "Условия получения информационных и маркетинговых сообщений от AI Verdict.",
  alternates: {
    canonical: LEGAL_DOC_LINKS.marketingConsent,
  },
  robots: {
    index: false,
    follow: true,
    nocache: true,
  },
};

export default function MarketingConsentPage() {
  return (
    <LegalPageFrame
      title="Согласие на информационные и маркетинговые сообщения"
      description="Какие сообщения может отправлять AI Verdict и как от них отказаться."
      updatedAt={LEGAL_UPDATED_AT}
    >
      <section className="rounded-xl bg-white p-8 shadow-sm">
        <h2 className="mb-4 text-2xl font-bold text-slate-900">1. О каких сообщениях идет речь</h2>
        <ul className="list-disc space-y-2 pl-6 text-slate-700">
          <li>анонсы материалов и практических разборов;</li>
          <li>приглашения на консультации, демо и рабочие созвоны;</li>
          <li>сообщения о новых сервисах и форматах работы {LEGAL_BRAND};</li>
          <li>follow-up по вашему запросу, если вы сами оставили контакт.</li>
        </ul>
      </section>

      <section className="rounded-xl bg-white p-8 shadow-sm">
        <h2 className="mb-4 text-2xl font-bold text-slate-900">2. Когда сообщения допустимы</h2>
        <div className="space-y-4 text-slate-700">
          <p>
            Маркетинговые и информационные сообщения отправляются только при наличии отдельного
            согласия или в объеме, необходимом для ответа на ваш собственный запрос.
          </p>
          <p>
            Обычная деловая переписка по вашей заявке не считается подпиской на регулярную рассылку.
          </p>
        </div>
      </section>

      <section className="rounded-xl bg-white p-8 shadow-sm">
        <h2 className="mb-4 text-2xl font-bold text-slate-900">3. Как отказаться</h2>
        <p className="text-slate-700">
          Отказаться от рассылок можно в любой момент: ответом на сообщение, через бота или по адресу{" "}
          <a href={`mailto:${LEGAL_CONTACT_EMAIL}`} className="text-amber-700 underline">
            {LEGAL_CONTACT_EMAIL}
          </a>
          . После отказа регулярные промо- и информационные сообщения прекращаются.
        </p>
      </section>
    </LegalPageFrame>
  );
}
