"use client";

import { useState } from "react";

import { lawyerFetch } from "./useTelegram";

/**
 * Точный текст документа — тот, что видел и подписывал клиент.
 *
 * Карточка показывает условия по полям, и это реконструкция. При споре о
 * содержании нужен сам документ и хеш, под которым стоит подпись: он
 * доказывает, что текст не менялся после подписания, — но только рядом с
 * самим текстом. Грузится по запросу: длинный, а нужен редко.
 */

type Document = {
  document_version: string | null;
  document_hash: string;
  document_text: string | null;
};

export default function DocumentText({
  url,
  title,
  initData,
}: {
  url: string;
  title: string;
  initData: string;
}) {
  const [doc, setDoc] = useState<Document | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  return (
    <details
      className="mt-2 text-sm"
      onToggle={(event) => {
        if (!event.currentTarget.open || doc || busy) return;
        setBusy(true);
        setError(null);
        lawyerFetch<Document>(url, initData)
          .then(setDoc)
          .catch((err) => setError(err instanceof Error ? err.message : "Не удалось загрузить"))
          .finally(() => setBusy(false));
      }}
    >
      <summary className="cursor-pointer text-slate-400 underline underline-offset-2 hover:text-slate-200">
        {title}
      </summary>
      {busy ? <p className="mt-2 text-slate-400">Загружаю…</p> : null}
      {error ? <p className="mt-2 text-rose-300">{error}</p> : null}
      {doc ? (
        <div className="mt-2 rounded-xl border border-slate-800 bg-slate-950/60 p-3">
          <p className="mb-2 break-all font-mono text-xs text-slate-400">
            {doc.document_version ? `редакция ${doc.document_version} · ` : ""}
            sha256 {doc.document_hash}
          </p>
          <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed text-slate-200">
            {doc.document_text || "Текст не сохранён."}
          </pre>
        </div>
      ) : null}
    </details>
  );
}
