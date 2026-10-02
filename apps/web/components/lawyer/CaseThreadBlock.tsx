"use client";

import { useCallback, useEffect, useState } from "react";

import { dropDraft, readDraft, writeDraft } from "./draft-storage";
import { shortDate } from "./labels";
import { Card, SectionTitle } from "./ui";
import { lawyerAction, lawyerFetch } from "./useTelegram";

type Message = {
  id: string;
  intake_id: string | null;
  author: "client" | "lawyer";
  channel: string;
  text: string;
  created_at: string | null;
};

type Thread = { client_has_telegram: boolean; messages: Message[] };

/**
 * «Переписка» в карточке клиента: сообщения клиента из кабинета и бота и
 * ответы юриста. Ответ сохраняется всегда и виден клиенту в кабинете; клиенту
 * с Telegram он приходит ещё и туда. Раньше клиенту без Telegram ответить было
 * нечем.
 */
export default function CaseThreadBlock({
  leadId,
  initData,
  onChanged,
}: {
  leadId: string;
  initData: string;
  onChanged?: () => void;
}) {
  const draftKey = `lawyer.case-reply.${leadId}`;
  const [thread, setThread] = useState<Thread | null>(null);
  const [text, setText] = useState(() => readDraft(draftKey, ""));
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setThread(await lawyerFetch<Thread>(`/api/lawyer/clients/${leadId}/messages`, initData));
    } catch (err) {
      setNote(err instanceof Error ? err.message : "Не удалось загрузить переписку");
    }
  }, [leadId, initData]);

  useEffect(() => {
    void load();
  }, [load]);

  const send = async () => {
    const value = text.trim();
    if (!value) return;
    setBusy(true);
    setNote(null);
    try {
      const result = await lawyerAction<{ delivered: string[] }>(`/api/lawyer/clients/${leadId}/messages`, initData, {
        text: value,
      });
      dropDraft(draftKey);
      setText("");
      setNote(
        result.delivered.includes("telegram")
          ? "Отправлено: в кабинет клиента и в Telegram."
          : "Отправлено в личный кабинет клиента. Telegram у клиента нет — сообщите ему, что ответ в кабинете.",
      );
      await load();
      onChanged?.();
    } catch (err) {
      setNote(err instanceof Error ? err.message : "Не получилось отправить");
    } finally {
      setBusy(false);
    }
  };

  const messages = thread?.messages || [];
  return (
    <section>
      <SectionTitle count={messages.length}>Переписка</SectionTitle>
      <Card>
        {thread === null ? <p className="text-lw-sm text-lw-muted">Загружаю…</p> : null}
        {thread && messages.length === 0 ? (
          <p className="text-lw-sm text-lw-muted">
            Клиент пока не писал. Ответ отсюда увидит в личном кабинете
            {thread.client_has_telegram ? " и в Telegram" : ""}.
          </p>
        ) : null}
        <div className="space-y-2">
          {messages.map((message) => {
            const mine = message.author === "lawyer";
            return (
              <div key={message.id} className={mine ? "flex justify-end" : "flex justify-start"}>
                <div className={`max-w-[85%] whitespace-pre-wrap rounded-xl px-3 py-2 text-lw-base ${mine ? "bg-lw-primary-soft" : "bg-lw-cell"}`}>
                  <p className="mb-1 text-lw-sm text-lw-muted">
                    {mine ? "Вы" : "Клиент"} · {shortDate(message.created_at)}
                    {!mine && message.channel === "telegram" ? " · из Telegram" : ""}
                  </p>
                  {message.text}
                </div>
              </div>
            );
          })}
        </div>
        <div className="mt-3 space-y-2">
          <textarea
            value={text}
            onChange={(event) => {
              setText(event.target.value);
              writeDraft(draftKey, event.target.value);
            }}
            maxLength={4000}
            rows={3}
            placeholder="Ответ клиенту"
            className="lw-input w-full"
          />
          <div className="flex flex-wrap items-center gap-3">
            <button type="button" disabled={busy || !text.trim()} onClick={() => void send()} className="lw-btn !px-4 !py-2 !text-[15px]">
              {busy ? "Отправляю…" : "Ответить"}
            </button>
            {note ? <span className="text-lw-sm text-lw-muted">{note}</span> : null}
          </div>
        </div>
      </Card>
    </section>
  );
}
