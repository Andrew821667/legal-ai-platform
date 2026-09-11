"use client";

import { formatRub } from "@/lib/money";
import { Card, Pill } from "./ui";
import type { Tone } from "./ui";
import { AGREEMENT_STATUS, label, shortDate } from "./labels";
import type { Finance, FinanceAgreement, MoneyBucket } from "./types";

/**
 * Деньги практики одним взглядом.
 *
 * До этого сумма существовала только текстом внутри карточки одного клиента:
 * «сколько за месяц» нельзя было посчитать даже вручную по экрану. Рядом с
 * каждым итогом — сколько договоров в него не вошло: сумма без числа
 * складывается в ноль молча, и итог выглядел бы полным, когда он неполный.
 */

function monthName(iso: string): string {
  // Границы месяца ядро считает по Москве; подпись должна совпадать с ними,
  // а не с поясом того, кто открыл экран.
  return new Date(iso).toLocaleDateString("ru-RU", { month: "long", timeZone: "Europe/Moscow" });
}

function statusTone(status: string): Tone {
  if (status === "signed") return "ok";
  if (status === "declined" || status === "expired" || status === "cancelled") return "alert";
  if (status === "draft") return "warn";
  return "mute";
}

function Tile({ title, bucket, note }: { title: string; bucket: MoneyBucket; note?: string }) {
  return (
    <Card>
      <p className="text-sm text-slate-400">{title}</p>
      <p className="mt-1 text-2xl font-semibold tabular-nums text-white">{formatRub(bucket.minor)}</p>
      <p className="mt-0.5 text-sm text-slate-400">
        {bucket.count === 0
          ? "нет договоров"
          : `${bucket.count} ${bucket.count === 1 ? "договор" : bucket.count < 5 ? "договора" : "договоров"}`}
        {bucket.unpriced ? (
          <span className="text-amber-200"> · без суммы: {bucket.unpriced}</span>
        ) : null}
      </p>
      {note ? <p className="mt-1 text-sm text-slate-400">{note}</p> : null}
    </Card>
  );
}

function Row({ item, onOpen }: { item: FinanceAgreement; onOpen: (leadId: string) => void }) {
  const when = item.signed_at || item.sent_at || item.created_at;
  return (
    <li>
      <button
        type="button"
        disabled={!item.lead_id}
        onClick={() => item.lead_id && onOpen(item.lead_id)}
        className="w-full rounded-xl bg-slate-800/70 p-3 text-left transition-colors hover:bg-slate-800 disabled:cursor-default"
      >
        <div className="flex items-baseline justify-between gap-3">
          <span className="min-w-0 truncate text-base font-medium text-white">{item.client}</span>
          <span className="shrink-0 tabular-nums text-base font-medium text-white">
            {item.amount_minor === null ? (
              <span className="text-sm font-normal text-amber-200">нет суммы</span>
            ) : (
              formatRub(item.amount_minor)
            )}
          </span>
        </div>
        <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-slate-400">
          <Pill tone={statusTone(item.status)}>{label(AGREEMENT_STATUS, item.status)}</Pill>
          <span className="min-w-0 truncate">{item.subject}</span>
          <span className="shrink-0">{shortDate(when)}</span>
        </div>
      </button>
    </li>
  );
}

export default function FinanceView({
  finance,
  onOpen,
}: {
  finance: Finance;
  onOpen: (leadId: string) => void;
}) {
  const month = monthName(finance.month_from);
  const unpriced =
    finance.signed_total.unpriced + finance.in_pipeline.unpriced + finance.drafts.unpriced;
  const prev = finance.signed_prev_month;

  return (
    <div className="space-y-4">
      {unpriced > 0 ? (
        <p className="rounded-xl bg-amber-500/10 p-3 text-sm text-amber-200">
          У {unpriced} {unpriced === 1 ? "договора" : "договоров"} не указана сумма к учёту —
          итоги ниже неполные. Указать можно в карточке клиента, в блоке договора.
        </p>
      ) : null}

      <div className="grid grid-cols-2 gap-2">
        <Tile
          title={`Подписано, ${month}`}
          bucket={finance.signed_this_month}
          note={prev.count ? `Прошлый месяц: ${formatRub(prev.minor)}` : undefined}
        />
        <Tile title="В работе у клиентов" bucket={finance.in_pipeline} />
        <Tile title="Черновики" bucket={finance.drafts} />
        <Card>
          <p className="text-sm text-slate-400">Средний чек</p>
          <p className="mt-1 text-2xl font-semibold tabular-nums text-white">
            {formatRub(finance.average_signed_minor)}
          </p>
          <p className="mt-0.5 text-sm text-slate-400">
            по {finance.signed_total.count - finance.signed_total.unpriced} подписанным за всё время
          </p>
        </Card>
      </div>

      {finance.declined_this_month.count ? (
        <p className="text-sm text-slate-400">
          Отклонено в этом месяце: {finance.declined_this_month.count} на{" "}
          {formatRub(finance.declined_this_month.minor)}.
        </p>
      ) : null}

      <section>
        <h2 className="mb-2 text-base font-semibold uppercase tracking-wide text-slate-300">
          Договоры
        </h2>
        {finance.agreements.length === 0 ? (
          <Card>
            <p className="text-base text-slate-400">Договоров ещё нет.</p>
          </Card>
        ) : (
          <ul className="space-y-2">
            {finance.agreements.map((item) => (
              <Row key={item.agreement_id} item={item} onOpen={onOpen} />
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
