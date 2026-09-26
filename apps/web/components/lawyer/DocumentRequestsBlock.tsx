"use client";

import { useState } from "react";

import {
  collectTitles,
  commonDocuments,
  deliveryNote,
  waitingSummary,
} from "@/lib/document-requests";
import type { DocumentRequestResponse, DocumentRequestRow, DocumentRequestStatus } from "@/lib/document-requests";
import { lawyerAction } from "./useTelegram";

/**
 * «Запросить документы» в обращении: юрист отмечает, что нужно, клиент
 * получает список в Telegram и видит его в «Моих делах», а здесь видно,
 * что пришло и чего не хватает.
 *
 * Загруженный клиентом в пункт файл закрывает его сам. Присланное в чат
 * без привязки юрист отмечает кнопкой «Получен».
 */

const STATUS_LABEL: Record<DocumentRequestStatus, string> = {
  open: "ждём",
  received: "получен",
  cancelled: "не нужен",
};

export default function DocumentRequestsBlock({
  intakeId,
  practice,
  rows,
  initData,
  onChanged,
}: {
  intakeId: string;
  practice: string | null;
  rows: DocumentRequestRow[];
  initData: string;
  onChanged: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [selected, setSelected] = useState<string[]>([]);
  const [custom, setCustom] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);

  const summary = waitingSummary(rows);
  const titles = collectTitles(selected, custom);

  const toggle = (title: string) =>
    setSelected((current) => (current.includes(title) ? current.filter((t) => t !== title) : [...current, title]));

  const send = async () => {
    setBusy(true);
    setMessage(null);
    try {
      const response = await lawyerAction<DocumentRequestResponse>(
        `/api/lawyer/intakes/${intakeId}/document-requests`,
        initData,
        { titles, note: note.trim() || null },
      );
      setMessage({ ok: true, text: deliveryNote(response) });
      setSelected([]);
      setCustom("");
      setNote("");
      setOpen(false);
      onChanged();
    } catch (err) {
      setMessage({ ok: false, text: err instanceof Error ? err.message : "Не удалось запросить документы" });
    } finally {
      setBusy(false);
    }
  };

  const mark = async (row: DocumentRequestRow, status: DocumentRequestStatus) => {
    try {
      await lawyerAction(`/api/lawyer/document-requests/${row.request_id}`, initData, { status }, "PATCH");
      onChanged();
    } catch (err) {
      setMessage({ ok: false, text: err instanceof Error ? err.message : "Не удалось отметить" });
    }
  };

  const visible = rows.filter((row) => row.status !== "cancelled");

  return (
    <div className="mt-3 border-t border-lw-border pt-3">
      <div className="mb-2 flex items-baseline justify-between gap-2">
        <p className="text-lw-sm uppercase tracking-wide text-lw-muted">
          Запрошенные документы{summary ? ` · ${summary}` : ""}
        </p>
        {open ? null : (
          <button type="button" onClick={() => setOpen(true)} className="text-lw-sm text-lw-primary underline underline-offset-2">
            {visible.length ? "запросить ещё" : "запросить у клиента"}
          </button>
        )}
      </div>

      {visible.length ? (
        <ul className="space-y-1.5">
          {visible.map((row) => (
            <li key={row.request_id} className="flex flex-wrap items-baseline justify-between gap-2 text-lw-sm">
              <span className={row.status === "received" ? "text-lw-muted line-through" : "text-lw-ink"}>
                {row.title}
              </span>
              <span className="flex items-baseline gap-2">
                <span className={row.status === "open" ? "text-lw-warning" : "text-lw-success"}>
                  {STATUS_LABEL[row.status]}
                </span>
                {row.status === "open" ? (
                  <>
                    <button type="button" onClick={() => void mark(row, "received")} className="text-lw-primary underline underline-offset-2">
                      получен
                    </button>
                    <button type="button" onClick={() => void mark(row, "cancelled")} className="text-lw-muted underline underline-offset-2">
                      не нужен
                    </button>
                  </>
                ) : row.document_id ? null : (
                  <button type="button" onClick={() => void mark(row, "open")} className="text-lw-muted underline underline-offset-2">
                    вернуть
                  </button>
                )}
              </span>
            </li>
          ))}
        </ul>
      ) : null}

      {open ? (
        <div className="mt-2 rounded-xl bg-lw-cell p-3">
          <div className="flex flex-wrap gap-1.5">
            {commonDocuments(practice).map((title) => (
              <button
                key={title}
                type="button"
                onClick={() => toggle(title)}
                className={`rounded-full px-2.5 py-1 text-lw-sm ${
                  selected.includes(title) ? "bg-lw-primary text-white" : "bg-white text-lw-ink hover:bg-lw-blue-soft"
                }`}
              >
                {title}
              </button>
            ))}
          </div>
          <textarea
            value={custom}
            onChange={(event) => setCustom(event.target.value)}
            rows={2}
            placeholder="Другие документы — каждый с новой строки"
            className="lw-input mt-2"
          />
          <textarea
            value={note}
            onChange={(event) => setNote(event.target.value)}
            rows={2}
            maxLength={1000}
            placeholder="Пояснение клиенту (необязательно): например, «подойдут фото, главное — читаемо»"
            className="lw-input mt-2"
          />
          <div className="mt-2 flex gap-2">
            <button type="button" onClick={() => void send()} disabled={busy || titles.length === 0} className="lw-btn flex-1">
              {busy ? "Отправляю…" : titles.length ? `Запросить (${titles.length})` : "Отметьте документы"}
            </button>
            <button type="button" onClick={() => setOpen(false)} className="lw-btn-quiet">
              Отмена
            </button>
          </div>
        </div>
      ) : null}

      {message ? (
        <p className={`mt-2 text-lw-sm ${message.ok ? "text-lw-muted" : "text-lw-danger"}`}>{message.text}</p>
      ) : null}
    </div>
  );
}
