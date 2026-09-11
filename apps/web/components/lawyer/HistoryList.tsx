"use client";

import { useState } from "react";

import { formatRub } from "@/lib/money";
import { CONFLICT, HISTORY, INTAKE_STATUS, OUTREACH_REASON, label, shortDay } from "./labels";
import { lawyerFetch } from "./useTelegram";
import type { History, HistoryItem } from "./types";

/**
 * История дела — из журнала, который писался при каждом действии и ни разу
 * не читался обратно. Карточка показывает только текущее состояние; здесь
 * видно, кто отправил договор, когда клиент его открыл и почему сорвалось.
 *
 * Свёрнута и грузится по раскрытию: длинно, а нужно не всякий раз — в
 * отличие от остального в карточке, что открыто всегда.
 */

function when(iso: string | null): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** Что именно поменялось — по деталям события, человеческими словами. */
function explain(item: HistoryItem): string[] {
  const d = item.details;
  const out: string[] = [];
  switch (item.action) {
    case "legal_intake.update":
      if (typeof d.status === "string") out.push(`статус: ${label(INTAKE_STATUS, d.status)}`);
      if (typeof d.conflict_status === "string") {
        out.push(`проверка конфликта: ${label(CONFLICT, d.conflict_status).toLowerCase()}`);
      }
      if ("deadline_at" in d) {
        out.push(d.deadline_at ? `срок: до ${shortDay(String(d.deadline_at))}` : "срок снят");
      }
      if ("internal_note" in d) out.push("заметка обновлена");
      if (typeof d.assigned_to === "string") out.push(`ведёт: ${d.assigned_to}`);
      break;
    case "legal_intake.outreach":
      if (d.blocked_reason) {
        out.push(`связаться не удалось: ${label(OUTREACH_REASON, String(d.blocked_reason))}`);
      }
      break;
    case "legal_intake.document":
      if (d.nda_signed === false) out.push("без подписанного NDA");
      break;
    case "service_agreement.create":
      if (typeof d.revision === "number" && d.revision > 1) out.push(`редакция ${d.revision}`);
      break;
    case "service_agreement.amount":
      out.push(
        `${formatRub(typeof d.from === "number" ? d.from : null)} → ${formatRub(typeof d.to === "number" ? d.to : null)}`,
      );
      break;
    default:
      break;
  }
  return out;
}

export default function HistoryList({ leadId, initData }: { leadId: string; initData: string }) {
  const [history, setHistory] = useState<History | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  return (
    <details
      className="lw-card p-4"
      onToggle={(event) => {
        if (!event.currentTarget.open || history || busy) return;
        setBusy(true);
        setError(null);
        lawyerFetch<History>(`/api/lawyer/clients/${leadId}/history`, initData)
          .then(setHistory)
          .catch((err) => setError(err instanceof Error ? err.message : "Не удалось загрузить"))
          .finally(() => setBusy(false));
      }}
    >
      <summary className="lw-eyebrow cursor-pointer">
        История
      </summary>
      {busy ? <p className="mt-2 text-lw-sm text-lw-muted">Загружаю…</p> : null}
      {error ? <p className="mt-2 text-lw-sm text-lw-danger">{error}</p> : null}
      {history && history.items.length === 0 ? (
        <p className="mt-2 text-lw-sm text-lw-muted">Записей пока нет.</p>
      ) : null}
      {history && history.items.length > 0 ? (
        <ol className="mt-3 space-y-2">
          {history.items.map((item, index) => {
            const extra = explain(item);
            return (
              <li key={index} className="flex gap-3 text-lw-sm">
                <span className="w-24 shrink-0 tabular-nums text-lw-muted">{when(item.at)}</span>
                <span className="min-w-0 text-lw-ink">
                  {label(HISTORY, item.action)}
                  {item.agreement_number ? (
                    <span className="text-lw-muted"> · № {item.agreement_number}</span>
                  ) : null}
                  {extra.length ? (
                    <span className="block text-lw-muted">{extra.join(" · ")}</span>
                  ) : null}
                </span>
              </li>
            );
          })}
        </ol>
      ) : null}
    </details>
  );
}
