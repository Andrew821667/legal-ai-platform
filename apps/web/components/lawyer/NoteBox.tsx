"use client";

import { useState } from "react";

import { lawyerAction } from "./useTelegram";

/**
 * Заметка юриста по обращению — то, что не показывают клиенту.
 *
 * Свёрнута, пока пуста: на экране, где перечислены обстоятельства дела, поле
 * ввода без содержимого только отвлекает.
 */
export default function NoteBox({
  intakeId,
  initialNote,
  initData,
}: {
  intakeId: string;
  initialNote: string | null;
  initData: string;
}) {
  const [note, setNote] = useState(initialNote || "");
  const [open, setOpen] = useState(Boolean(initialNote));
  const [state, setState] = useState<"idle" | "busy" | "saved">("idle");
  const [error, setError] = useState<string | null>(null);

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="mt-2 text-xs text-slate-500 hover:text-slate-300"
      >
        + заметка
      </button>
    );
  }

  return (
    <div className="mt-2">
      <textarea
        value={note}
        onChange={(event) => {
          setNote(event.target.value);
          setState("idle");
        }}
        rows={3}
        placeholder="Заметка для себя — клиент её не видит"
        className="w-full rounded-lg border border-slate-700 bg-slate-950 p-2 text-xs text-slate-200 placeholder:text-slate-600"
      />
      <div className="mt-1 flex items-center gap-3">
        <button
          type="button"
          disabled={state === "busy"}
          onClick={async () => {
            setState("busy");
            setError(null);
            try {
              await lawyerAction(`/api/lawyer/intakes/${intakeId}/note`, initData, { note });
              setState("saved");
            } catch (err) {
              setError(err instanceof Error ? err.message : "Не получилось сохранить");
              setState("idle");
            }
          }}
          className="rounded-lg bg-slate-800 px-3 py-1.5 text-xs text-slate-200 hover:bg-slate-700 disabled:opacity-50"
        >
          {state === "busy" ? "Сохраняю…" : "Сохранить"}
        </button>
        {state === "saved" ? <span className="text-xs text-emerald-300">Сохранено</span> : null}
        {error ? <span className="text-xs text-rose-300">{error}</span> : null}
      </div>
    </div>
  );
}
