"use client";

import { useState } from "react";

import { shortDate } from "./labels";
import { lawyerAction } from "./useTelegram";
import type { IntakeDocumentRow } from "./types";

/**
 * Присланный клиентом файл — и способ его открыть.
 *
 * Раньше здесь было только имя: ни посмотреть, ни скачать — за файлом
 * приходилось идти в чат с ботом. Внутри Telegram файл и теперь открывается
 * через чат — но одним касанием: бот пересылает его по идентификатору, и он
 * откроется нативным просмотрщиком. Снаружи, в Safari, — обычная ссылка:
 * файл идёт потоком, PDF и картинки браузер покажет сам.
 */

function fileSize(bytes: number | null): string {
  if (!bytes) return "";
  if (bytes < 1024) return `${bytes} Б`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} КБ`;
  return `${(bytes / (1024 * 1024)).toFixed(1).replace(".", ",")} МБ`;
}

export default function DocumentRow({
  doc,
  initData,
}: {
  doc: IntakeDocumentRow;
  initData: string;
}) {
  const [state, setState] = useState<"idle" | "busy" | "sent">("idle");
  const [error, setError] = useState<string | null>(null);
  const inTelegram = initData !== "";
  const url = `/api/lawyer/documents/${doc.document_id}`;

  return (
    <li className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1 text-sm">
      {inTelegram ? (
        <span className="min-w-0 truncate text-slate-200">{doc.file_name || "без имени"}</span>
      ) : (
        <a
          href={url}
          target="_blank"
          rel="noopener"
          className="min-w-0 truncate text-slate-100 underline underline-offset-2 hover:text-white"
        >
          {doc.file_name || "без имени"}
        </a>
      )}
      <span className="flex shrink-0 items-baseline gap-2 text-slate-400">
        {fileSize(doc.file_size) ? <span>{fileSize(doc.file_size)}</span> : null}
        <span>{shortDate(doc.created_at)}</span>
        {doc.nda_signed_at_upload ? null : <span className="text-amber-200">без NDA</span>}
        {inTelegram ? (
          state === "sent" ? (
            <span className="text-emerald-300">в чате</span>
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
                  setError(err instanceof Error ? err.message : "Не удалось переслать");
                  setState("idle");
                }
              }}
              className="text-slate-300 underline underline-offset-2 hover:text-white disabled:opacity-60"
            >
              {state === "busy" ? "пересылаю…" : "в чат"}
            </button>
          )
        ) : null}
      </span>
      {error ? <span className="w-full text-rose-300">{error}</span> : null}
    </li>
  );
}
