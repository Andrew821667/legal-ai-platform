"use client";

import { useState } from "react";

import { formatRub } from "@/lib/money";
import { Card, Pill } from "./ui";
import type { Tone } from "./ui";
import { AGREEMENT_STATUS, label, shortDate } from "./labels";
import { lawyerAction } from "./useTelegram";
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
      <p className="text-lw-sm text-lw-muted">{title}</p>
      <p className="mt-1 text-lw-xl font-extrabold tabular-nums text-lw-ink">{formatRub(bucket.minor)}</p>
      <p className="mt-0.5 text-lw-sm text-lw-muted">
        {bucket.count === 0
          ? "нет договоров"
          : `${bucket.count} ${bucket.count === 1 ? "договор" : bucket.count < 5 ? "договора" : "договоров"}`}
        {bucket.unpriced ? (
          <span className="text-lw-warning"> · без суммы: {bucket.unpriced}</span>
        ) : null}
      </p>
      {note ? <p className="mt-1 text-lw-sm text-lw-muted">{note}</p> : null}
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
        className="w-full rounded-xl bg-lw-cell p-3 text-left transition-colors hover:bg-lw-blue-soft disabled:cursor-default"
      >
        <div className="flex items-baseline justify-between gap-3">
          <span className="min-w-0 truncate text-lw-base font-medium text-lw-ink">{item.client}</span>
          <span className="shrink-0 tabular-nums text-lw-base font-medium text-lw-ink">
            {item.amount_minor === null ? (
              <span className="text-lw-sm font-normal text-lw-warning">нет суммы</span>
            ) : (
              formatRub(item.amount_minor)
            )}
          </span>
        </div>
        <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-lw-sm text-lw-muted">
          <Pill tone={statusTone(item.status)}>{label(AGREEMENT_STATUS, item.status)}</Pill>
          <span className="min-w-0 truncate">{item.subject}</span>
          <span className="shrink-0">{shortDate(when)}</span>
        </div>
      </button>
    </li>
  );
}

/**
 * Выгрузка в CSV — для бухгалтерии и отчётности; ни одного экспорта в
 * системе не было, цифры переписывали с экрана. Внутри Telegram файл нельзя
 * скачать — бот присылает его в чат; снаружи, в Safari, — обычная ссылка.
 */
const PILL_BUTTON =
  "inline-flex items-center rounded-full bg-lw-primary-soft px-3 py-1.5 text-lw-sm font-semibold text-lw-primary transition-colors hover:bg-lw-blue-soft";

function ExportCsv({ initData, insideTelegram }: { initData: string; insideTelegram: boolean }) {
  const [state, setState] = useState<"idle" | "busy" | "sent">("idle");
  const [error, setError] = useState<string | null>(null);
  const url = "/api/lawyer/export/agreements";

  if (!insideTelegram) {
    return (
      <a href={url} download className={PILL_BUTTON}>
        Скачать CSV
      </a>
    );
  }
  return (
    <span className="inline-flex items-center gap-2 text-lw-sm">
      {state === "sent" ? (
        <span className="text-lw-success">CSV в чате с ботом</span>
      ) : (
        <button
          type="button"
          disabled={state === "busy"}
          onClick={async () => {
            setState("busy");
            setError(null);
            try {
              await lawyerAction(`${url}/send`, initData);
              setState("sent");
            } catch (err) {
              setError(err instanceof Error ? err.message : "Не удалось отправить");
              setState("idle");
            }
          }}
          className={`${PILL_BUTTON} disabled:opacity-60`}
        >
          {state === "busy" ? "Отправляю…" : "CSV в чат"}
        </button>
      )}
      {error ? <span className="text-lw-danger">{error}</span> : null}
    </span>
  );
}

export default function FinanceView({
  finance,
  onOpen,
  initData,
  insideTelegram,
}: {
  finance: Finance;
  onOpen: (leadId: string) => void;
  initData: string;
  insideTelegram: boolean;
}) {
  const month = monthName(finance.month_from);
  const unpriced =
    finance.signed_total.unpriced + finance.in_pipeline.unpriced + finance.drafts.unpriced;
  const prev = finance.signed_prev_month;

  return (
    <div className="space-y-4">
      {unpriced > 0 ? (
        <p className="rounded-xl bg-lw-warning-soft p-3 text-lw-sm text-lw-warning">
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
          <p className="text-lw-sm text-lw-muted">Средний чек</p>
          {/* Среднему копейки ни к чему — а с ними число не влезает в плитку. */}
          <p className="mt-1 text-lw-xl font-extrabold tabular-nums text-lw-ink">
            {formatRub(
              finance.average_signed_minor === null
                ? null
                : Math.round(finance.average_signed_minor / 100) * 100,
            )}
          </p>
          <p className="mt-0.5 text-lw-sm text-lw-muted">
            по {finance.signed_total.count - finance.signed_total.unpriced} подписанным за всё время
          </p>
        </Card>
      </div>

      {finance.declined_this_month.count ? (
        <p className="text-lw-sm text-lw-muted">
          Отклонено в этом месяце: {finance.declined_this_month.count} на{" "}
          {formatRub(finance.declined_this_month.minor)}.
        </p>
      ) : null}

      <section>
        <div className="mb-2 flex items-center justify-between gap-3">
          <h2 className="lw-eyebrow">Договоры</h2>
          {finance.agreements.length > 0 ? (
            <ExportCsv initData={initData} insideTelegram={insideTelegram} />
          ) : null}
        </div>
        {finance.agreements.length === 0 ? (
          <Card>
            <p className="text-lw-base text-lw-muted">Договоров ещё нет.</p>
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
