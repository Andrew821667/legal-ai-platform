"use client";

import { useState } from "react";

import { dropDraft, readDraft, writeDraft } from "./draft-storage";
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
  onSent,
}: {
  agreementId: string;
  initData: string;
  onSent: () => void;
}) {
  const draftKey = `lawyer.reply.${agreementId}`;
  const [text, setText] = useState(() => readDraft(draftKey, ""));
  const [state, setState] = useState<"idle" | "busy" | "sent">("idle");
  const [error, setError] = useState<string | null>(null);

  if (state === "sent") {
    return <p className="mt-2 text-lw-sm text-lw-success">Ответ отправлен клиенту.</p>;
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
          dropDraft(draftKey);
          setState("sent");
          onSent();
        } catch (err) {
          setError(err instanceof Error ? err.message : "Не получилось отправить");
          setState("idle");
        }
      }}
    >
      <textarea
        value={text}
        onChange={(event) => {
          setText(event.target.value);
          writeDraft(draftKey, event.target.value);
        }}
        rows={3}
        placeholder="Ответ клиенту"
        className="lw-input"
      />
      <button
        type="submit"
        disabled={state === "busy" || !text.trim()}
        className="lw-btn w-full"
      >
        {state === "busy" ? "Отправляю…" : "Ответить"}
      </button>
      {error ? <p className="text-lw-sm text-lw-danger">{error}</p> : null}
    </form>
  );
}
