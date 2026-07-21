import Link from "next/link";

import { LEGAL_OPERATOR_NAME } from "@/lib/legalProfile";
import { LEGAL_HELP_REVIEWED_AT } from "@/lib/legalHelpPages";

const formattedDate = new Intl.DateTimeFormat("ru-RU", {
  day: "numeric",
  month: "long",
  year: "numeric",
  timeZone: "UTC",
}).format(new Date(`${LEGAL_HELP_REVIEWED_AT}T00:00:00.000Z`));

export default function LegalHelpTrust() {
  return (
    <section className="border-y border-slate-700 bg-slate-800/70">
      <div className="mx-auto grid max-w-6xl gap-6 px-4 py-10 sm:px-6 md:grid-cols-[1fr_auto] md:items-center lg:px-8">
        <div>
          <p className="text-sm font-semibold uppercase tracking-wide text-amber-300">
            Ответственность за материалы
          </p>
          <h2 className="mt-2 text-2xl font-semibold text-white">Юридическая и редакционная проверка</h2>
          <p className="mt-3 max-w-3xl leading-relaxed text-slate-300">
            Ответственный за материалы — {" "}
            <Link href="/team" className="font-medium text-amber-300 underline hover:text-amber-200">
              {LEGAL_OPERATOR_NAME}
            </Link>
            , основатель AI Verdict. На сайте указано более 20 лет юридической практики. Материалы подготовлены
            для первичной ориентации по законодательству Российской Федерации и не заменяют консультацию по
            обстоятельствам конкретного дела.
          </p>
          <p className="mt-3 text-sm leading-relaxed text-slate-400">
            AI-инструменты могут использоваться для структурирования информации. Юридическую позицию,
            рекомендации клиенту и решения по существу подтверждает человек.
          </p>
        </div>
        <div className="rounded-xl border border-slate-600 bg-slate-900/60 px-5 py-4 text-sm text-slate-300">
          <p>Последняя содержательная проверка</p>
          <time dateTime={LEGAL_HELP_REVIEWED_AT} className="mt-1 block font-semibold text-white">
            {formattedDate}
          </time>
          <Link href="/ai-policy" className="mt-2 inline-flex text-amber-300 hover:text-amber-200">
            Принципы использования AI →
          </Link>
        </div>
      </div>
    </section>
  );
}
