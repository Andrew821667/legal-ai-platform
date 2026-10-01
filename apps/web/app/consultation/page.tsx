import type { Metadata } from "next";
import Link from "next/link";

import ConsultationBooking from "@/components/consultation/ConsultationBooking";
import { CONSULTATION_OFFER_PATH } from "@/lib/consultation-offer";
import { createPageMetadata } from "@/lib/seo";
import { starterOffers } from "@/lib/starter-offers";
import { isLightOpsTheme } from "@/lib/visualTheme";

export const metadata: Metadata = createPageMetadata({
  title: "Запись на консультацию юриста",
  description:
    "Онлайн-консультация юриста AI Verdict: оплата по QR, время — открытое в расписании или согласуем с вами; до 60 минут и письменный план дальнейших действий.",
  path: "/legal-help/online-consultation",
  index: false,
  follow: true,
});

const offer = starterOffers.legal_consultation;

export default function ConsultationPage() {
  return (
    <main className={`${isLightOpsTheme ? "visual-light-ops" : ""} min-h-screen bg-slate-900 text-slate-100`}>
      <div className="mx-auto w-full max-w-3xl px-4 pb-16 pt-24 sm:px-6 sm:pt-28">
        <p className="text-sm font-semibold uppercase tracking-wide text-amber-300">Консультация юриста</p>
        <h1 className="mt-2 text-3xl font-semibold text-white sm:text-4xl">Запись на консультацию</h1>
        <p className="mt-4 leading-7 text-slate-300">
          {offer.description} Стоимость — <b className="text-white">{offer.price}</b>, оплата по QR в приложении
          банка.
        </p>
        <ol className="mt-5 grid gap-3 text-sm text-slate-300 sm:grid-cols-3">
          <li className="rounded-lg border border-slate-700 bg-slate-900 p-3"><b className="text-white">1.</b> Выберите время или «время согласуем» и опишите вопрос</li>
          <li className="rounded-lg border border-slate-700 bg-slate-900 p-3"><b className="text-white">2.</b> Оплатите по QR и нажмите «Я оплатил»</li>
          <li className="rounded-lg border border-slate-700 bg-slate-900 p-3"><b className="text-white">3.</b> Юрист подтвердит запись и свяжется с вами</li>
        </ol>

        <div className="mt-8">
          <ConsultationBooking />
        </div>

        <section className="mt-10 rounded-xl border border-slate-800 bg-slate-900/60 p-5 text-sm leading-6 text-slate-400">
          <h2 className="text-base font-semibold text-slate-200">Условия записи</h2>
          <ul className="mt-2 list-disc space-y-1 pl-5">
            <li>Консультация — до 60 минут онлайн (видеосвязь или телефон) и короткий письменный план после неё.</li>
            <li>Время закрепляется за вами на время оплаты; запись подтверждается, когда юрист получит оплату.</li>
            <li>Если юрист не сможет провести консультацию, он предложит другое время или вернёт оплату полностью.</li>
            <li>Перенос консультации по вашей просьбе — по согласованию с юристом.</li>
            <li>До начала консультации от неё можно отказаться и вернуть оплату — условия в оферте.</li>
            <li>{offer.note}</li>
            <li>После оплаты юрист направит чек «Мой налог».</li>
          </ul>
          <p className="mt-3">
            Полные условия —{" "}
            <Link href={CONSULTATION_OFFER_PATH} className="text-amber-300 underline underline-offset-2">
              в оферте на консультацию
            </Link>
            .
          </p>
          <p className="mt-3">
            Если вопрос требует подготовки документов или представительства, юрист предложит договор отдельно. Общий
            порядок работы — на странице{" "}
            <Link href="/legal-help" className="text-amber-300 underline underline-offset-2">юридической помощи</Link>.
          </p>
        </section>
      </div>
    </main>
  );
}
