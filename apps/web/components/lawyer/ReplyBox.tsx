"use client";

import { useState } from "react";

import { lawyerAction } from "./useTelegram";

/**
 * Ответ клиенту прямо из карточки.
 *
 * Ответ уходит в Telegram и только потом записывается в переписку: записанный,
 * но не доставленный, выглядел бы отправленным, и юрист решил бы, что клиент
 * его проигнорировал.
 */
export default function ReplyBox({
  agreementId,
  initData,
}: {
  agreementId: string;
  initData: string;
}) {
  const [text, setText] = useState("");
  const [state, setState] = useState<"idle" | "busy" | "sent">("idle");
  const [error, setError] = useState<string | null>(null);

  if (state === "sent") {
    return <p className="mt-2 text-sm text-emerald-300">Ответ отправлен клиенту.</p>;
  }

  return (
    <form
      className="mt-2 space-y-2"
      onSubmit={async (event) => {
        event.preventDefault();
        const value = text.trim();
        if (!value) return;
        setState("busy");
        setError(null);
        try {
          await lawyerAction(`/api/lawyer/agreements/${agreementId}/reply`, initData, {
            text: value,
          });
          setState("sent");
        } catch (err) {
          setError(err instanceof Error ? err.message : "Не получилось отправить");
          setState("idle");
        }
      }}
    >
      <textarea
        value={text}
        onChange={(event) => setText(event.target.value)}
        rows={3}
        placeholder="Ответ клиенту"
        className="w-full rounded-xl border border-slate-700 bg-slate-950 p-3 text-base text-white placeholder:text-slate-600"
      />
      <button
        type="submit"
        disabled={state === "busy" || !text.trim()}
        className="w-full rounded-xl bg-amber-500 px-4 py-3 text-base font-medium text-slate-950 disabled:opacity-50"
      >
        {state === "busy" ? "Отправляю…" : "Ответить"}
      </button>
      {error ? <p className="text-sm text-rose-300">{error}</p> : null}
    </form>
  );
}
