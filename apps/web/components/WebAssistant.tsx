"use client";

import {
  ArrowUpRight,
  LoaderCircle,
  MessageCircle,
  RotateCcw,
  Send,
  X,
} from "lucide-react";
import { KeyboardEvent, useEffect, useRef, useState } from "react";

type Role = "user" | "assistant";

interface ChatMessage {
  role: Role;
  message: string;
}

const STORAGE_KEY = "ai-verdict-web-assistant-v1";
const WELCOME: ChatMessage = {
  role: "assistant",
  message:
    "Здравствуйте. AI Verdict объединяет юридическую и инженерную практики, а на их стыке автоматизирует юридическую функцию. Опишите задачу — я помогу выбрать подходящий маршрут.",
};
const QUICK_PROMPTS = [
  "Автоматизировать юрфункцию",
  "Получить юридическую помощь",
  "Обсудить разработку и AI",
];

function newSessionId(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  return `session_${Array.from(bytes, (value) => value.toString(16).padStart(2, "0")).join("")}`;
}

function readSession(): { sessionId: string; messages: ChatMessage[] } {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    const data = raw ? JSON.parse(raw) as Record<string, unknown> : null;
    const sessionId = typeof data?.sessionId === "string" && /^[A-Za-z0-9_-]{8,80}$/.test(data.sessionId)
      ? data.sessionId
      : newSessionId();
    const messages = Array.isArray(data?.messages)
      ? data.messages
        .filter((item): item is ChatMessage => (
          item &&
          typeof item === "object" &&
          ((item as ChatMessage).role === "user" || (item as ChatMessage).role === "assistant") &&
          typeof (item as ChatMessage).message === "string" &&
          (item as ChatMessage).message.length > 0 &&
          (item as ChatMessage).message.length <= 5000
        ))
        .slice(-12)
      : [];
    return { sessionId, messages: messages.length ? messages : [WELCOME] };
  } catch {
    return { sessionId: newSessionId(), messages: [WELCOME] };
  }
}

export default function WebAssistant() {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([WELCOME]);
  const [input, setInput] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState("");
  const sessionId = useRef("");
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const stored = readSession();
    sessionId.current = stored.sessionId;
    setMessages(stored.messages);
  }, []);

  useEffect(() => {
    if (!sessionId.current) return;
    try {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify({
        sessionId: sessionId.current,
        messages: messages.slice(-12),
      }));
    } catch {
      // The dialog still works when browser storage is disabled.
    }
  }, [messages]);

  useEffect(() => {
    if (!isOpen) return;
    endRef.current?.scrollIntoView({ block: "end" });
    inputRef.current?.focus();
  }, [isOpen, messages, isSending]);

  async function sendMessage(text = input) {
    const message = text.trim();
    if (!message || isSending) return;

    const nextMessages = [...messages, { role: "user" as const, message }].slice(-12);
    setMessages(nextMessages);
    setInput("");
    setError("");
    setIsSending(true);

    try {
      if (!sessionId.current) sessionId.current = newSessionId();
      const response = await fetch("/api/assistant/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId.current,
          messages: nextMessages,
        }),
      });
      const data = await response.json() as { reply?: unknown; detail?: unknown };
      if (!response.ok || typeof data.reply !== "string" || !data.reply.trim()) {
        throw new Error(typeof data.detail === "string" ? data.detail : "Ассистент временно недоступен");
      }
      const reply = data.reply.trim();
      setMessages((current) => [
        ...current,
        { role: "assistant" as const, message: reply },
      ].slice(-12));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Ассистент временно недоступен");
    } finally {
      setIsSending(false);
    }
  }

  function resetDialog() {
    sessionId.current = newSessionId();
    setMessages([WELCOME]);
    setInput("");
    setError("");
    try {
      sessionStorage.removeItem(STORAGE_KEY);
    } catch {
      // Storage can be disabled by the browser without blocking a new dialog.
    }
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      void sendMessage();
    }
  }

  if (!isOpen) {
    return (
      <button
        type="button"
        onClick={() => setIsOpen(true)}
        className="fixed bottom-4 right-4 z-[60] inline-flex h-12 w-12 items-center justify-center rounded-lg bg-slate-950 p-0 text-sm font-semibold text-white shadow-[0_12px_36px_rgba(15,23,42,0.28)] transition hover:bg-slate-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber-600 sm:w-auto sm:gap-2 sm:px-4"
        aria-label="Открыть ассистента AI Verdict"
        title="Ассистент AI Verdict"
      >
        <MessageCircle className="h-5 w-5 text-amber-400" aria-hidden="true" />
        <span className="hidden sm:inline">Ассистент</span>
      </button>
    );
  }

  return (
    <section
      className="fixed inset-x-3 bottom-3 z-[70] flex h-[min(680px,calc(100dvh-1.5rem))] flex-col overflow-hidden rounded-lg border border-slate-300 bg-slate-100 shadow-[0_20px_60px_rgba(15,23,42,0.28)] sm:inset-x-auto sm:right-4 sm:w-[390px]"
      role="dialog"
      aria-label="Ассистент AI Verdict"
      data-nosnippet
    >
      <header className="flex h-16 shrink-0 items-center justify-between border-b border-slate-300 bg-slate-950 px-4 text-white">
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold">AI Verdict</p>
          <p className="truncate text-xs text-slate-300">Профильный ассистент</p>
        </div>
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={resetDialog}
            className="grid h-9 w-9 place-items-center rounded-md text-slate-300 transition hover:bg-slate-800 hover:text-white focus-visible:outline-2 focus-visible:outline-amber-500"
            aria-label="Начать диалог заново"
            title="Начать заново"
          >
            <RotateCcw className="h-4 w-4" aria-hidden="true" />
          </button>
          <button
            type="button"
            onClick={() => setIsOpen(false)}
            className="grid h-9 w-9 place-items-center rounded-md text-slate-300 transition hover:bg-slate-800 hover:text-white focus-visible:outline-2 focus-visible:outline-amber-500"
            aria-label="Закрыть ассистента"
            title="Закрыть"
          >
            <X className="h-5 w-5" aria-hidden="true" />
          </button>
        </div>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto px-3 py-4" aria-live="polite">
        <div className="space-y-3">
          {messages.map((item, index) => (
            <div
              key={`${item.role}-${index}`}
              className={`flex ${item.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <p className={`max-w-[88%] whitespace-pre-wrap break-words rounded-lg px-3 py-2.5 text-sm leading-5 ${
                item.role === "user"
                  ? "bg-slate-950 text-white"
                  : "border border-slate-300 bg-white text-slate-800"
              }`}>
                {item.message}
              </p>
            </div>
          ))}

          {messages.length === 1 && (
            <div className="flex flex-wrap gap-2 pt-1">
              {QUICK_PROMPTS.map((prompt) => (
                <button
                  key={prompt}
                  type="button"
                  onClick={() => void sendMessage(prompt)}
                  className="rounded-md border border-slate-400 bg-white px-3 py-2 text-left text-xs font-medium text-slate-800 transition hover:border-amber-600 hover:text-amber-800 focus-visible:outline-2 focus-visible:outline-amber-600"
                >
                  {prompt}
                </button>
              ))}
            </div>
          )}

          {isSending && (
            <div className="flex justify-start">
              <div className="inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-600">
                <LoaderCircle className="h-4 w-4 animate-spin" aria-hidden="true" />
                Формирую ответ
              </div>
            </div>
          )}
          <div ref={endRef} />
        </div>
      </div>

      <div className="shrink-0 border-t border-slate-300 bg-white p-3">
        {error && <p className="mb-2 text-xs font-medium text-red-700" role="alert">{error}</p>}
        <div className="flex items-end gap-2">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={handleKeyDown}
            rows={2}
            maxLength={1600}
            placeholder="Опишите задачу"
            className="min-h-12 max-h-28 flex-1 resize-y rounded-md border border-slate-400 bg-white px-3 py-2 text-sm text-slate-950 outline-none placeholder:text-slate-500 focus:border-amber-700 focus:ring-2 focus:ring-amber-200"
            aria-label="Сообщение ассистенту"
          />
          <button
            type="button"
            onClick={() => void sendMessage()}
            disabled={!input.trim() || isSending}
            className="grid h-12 w-12 shrink-0 place-items-center rounded-md bg-amber-700 text-white transition hover:bg-amber-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber-700 disabled:cursor-not-allowed disabled:bg-slate-300"
            aria-label="Отправить сообщение"
            title="Отправить"
          >
            {isSending
              ? <LoaderCircle className="h-5 w-5 animate-spin" aria-hidden="true" />
              : <Send className="h-5 w-5" aria-hidden="true" />}
          </button>
        </div>
        <div className="mt-2 flex items-center justify-between gap-3">
          <p className="text-[11px] leading-4 text-slate-600">Не отправляйте документы и чувствительные данные.</p>
          <a
            href="/#lead-form"
            className="inline-flex shrink-0 items-center gap-1 text-xs font-semibold text-amber-800 hover:text-amber-950 focus-visible:outline-2 focus-visible:outline-amber-700"
          >
            Передать задачу
            <ArrowUpRight className="h-3.5 w-3.5" aria-hidden="true" />
          </a>
        </div>
      </div>
    </section>
  );
}
