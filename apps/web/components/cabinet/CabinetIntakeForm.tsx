"use client";

import { FormEvent, useEffect, useState } from "react";

import TurnstileWidget from "@/components/TurnstileWidget";
import { getLeadHoneypotFieldName } from "@/lib/lead-security";

const TURNSTILE_SITE_KEY = (process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY || "").trim();
const TURNSTILE_CHALLENGE_MODE = (process.env.NEXT_PUBLIC_LEAD_FORM_CHALLENGE_MODE || "off").trim().toLowerCase();
const HONEYPOT_FIELD_NAME = getLeadHoneypotFieldName();

/**
 * Форма «Передать задачу» внутри пустого состояния кабинета — тот же
 * /api/leads, что у обычной формы на сайте (LeadCaptureForm.tsx), но
 * без своего contact-поля с телефоном/email по умолчанию: personality уже
 * подтверждена Telegram-входом, сервер сам прикрепит telegram_user_id из
 * куки (см. lib/lead-cabinet.ts). Contact остаётся редактируемым — человек
 * может уточнить предпочтительный канал (например, номер для звонка).
 */
export default function CabinetIntakeForm({ prefillContact, onCreated }: { prefillContact?: string; onCreated: () => void }) {
  const [practice, setPractice] = useState("hybrid");
  const [message, setMessage] = useState("");
  const [contact, setContact] = useState(prefillContact || "");
  const [consentAccepted, setConsentAccepted] = useState(false);
  const [honeypotValue, setHoneypotValue] = useState("");
  const [challengeRequired, setChallengeRequired] = useState(TURNSTILE_CHALLENGE_MODE === "always");
  const [challengeToken, setChallengeToken] = useState("");
  const [startedAtMs] = useState(() => Date.now());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (prefillContact && !contact) setContact(prefillContact);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- только первичный prefill, дальше поле редактируется пользователем
  }, [prefillContact]);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setError("");
    if (!contact.trim()) {
      setError("Укажите контакт: телефон, email или Telegram.");
      return;
    }
    if (!consentAccepted) {
      setError("Нужно согласие на обработку персональных данных.");
      return;
    }
    if (message.trim().length < 20) {
      setError("Кратко опишите задачу, не менее 20 символов.");
      return;
    }
    if (challengeRequired && TURNSTILE_SITE_KEY && !challengeToken) {
      setError("Подтвердите, что заявку отправляет человек.");
      return;
    }

    setBusy(true);
    try {
      const response = await fetch("/api/leads", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          contact,
          message,
          offer: "consultation",
          practice,
          consentAccepted,
          turnstile_token: challengeToken,
          _started_at_ms: startedAtMs,
          [HONEYPOT_FIELD_NAME]: honeypotValue,
        }),
      });
      const data = (await response.json()) as { detail?: string; challenge_required?: boolean; lead_id?: string };
      if (!response.ok) {
        if (data.challenge_required) setChallengeRequired(true);
        throw new Error(data.detail || "Не удалось отправить заявку");
      }
      onCreated();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось отправить заявку");
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className="space-y-3 rounded-lg border border-slate-700 bg-slate-800/80 p-4">
      <label
        className="absolute left-[-10000px] top-auto h-px w-px overflow-hidden"
        aria-hidden="true"
      >
        <span>{HONEYPOT_FIELD_NAME}</span>
        <input type="text" tabIndex={-1} autoComplete="off" value={honeypotValue} onChange={(e) => setHoneypotValue(e.target.value)} />
      </label>

      <h3 className="font-semibold text-white">Передать задачу</h3>

      <label className="block">
        <span className="mb-1 block text-sm text-slate-300">Направление</span>
        <select value={practice} onChange={(e) => setPractice(e.target.value)} className="w-full rounded bg-slate-900 p-2 text-sm text-slate-100">
          <option value="hybrid">Автоматизация юридической работы</option>
          <option value="legal">Юридическая помощь</option>
          <option value="engineering">Разработка программ и интеграций</option>
        </select>
      </label>

      <label className="block">
        <span className="mb-1 block text-sm text-slate-300">Что нужно сделать</span>
        <textarea
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          rows={4}
          minLength={20}
          maxLength={4000}
          required
          placeholder="Опишите задачу и ожидаемый результат"
          className="w-full rounded bg-slate-900 p-2 text-sm text-slate-100"
        />
      </label>

      <label className="block">
        <span className="mb-1 block text-sm text-slate-300">Контакт для связи</span>
        <input
          type="text"
          value={contact}
          onChange={(e) => setContact(e.target.value)}
          required
          placeholder="Телефон, email или @telegram"
          className="w-full rounded bg-slate-900 p-2 text-sm text-slate-100"
        />
      </label>

      <label className="flex items-start gap-3 text-sm text-slate-300">
        <input type="checkbox" checked={consentAccepted} onChange={(e) => setConsentAccepted(e.target.checked)} className="mt-1 h-4 w-4" />
        <span>
          Согласен(на) на обработку персональных данных. <a href="/privacy" target="_blank" className="text-amber-300 underline">Политика конфиденциальности</a>.
        </span>
      </label>

      <TurnstileWidget siteKey={TURNSTILE_SITE_KEY} enabled={challengeRequired && !!TURNSTILE_SITE_KEY} onToken={setChallengeToken} />

      {error ? <p className="rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-100">{error}</p> : null}

      <button
        type="submit"
        disabled={busy || !consentAccepted}
        className="w-full rounded-lg bg-amber-500 p-3 text-sm font-semibold text-slate-950 disabled:opacity-50"
      >
        {busy ? "Отправка..." : "Отправить"}
      </button>
    </form>
  );
}
