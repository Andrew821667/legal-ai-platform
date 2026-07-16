"use client";

import { FormEvent, useEffect, useState } from "react";
import { AlertTriangle, Send } from "lucide-react";

import { useMiniAppState } from "@/components/miniapp/MiniAppStateProvider";
import { leadBotDeepLink } from "@/lib/links";
import {
  LEGAL_AREAS,
  LEGAL_CLIENT_TYPES,
  LEGAL_URGENCY_LEVELS,
  type LegalArea,
  type LegalClientType,
  type LegalUrgency,
} from "@/lib/legalHelp";

const INIT_DATA_HEADER = "X-Telegram-Init-Data";

function readInitData(): string {
  if (typeof window === "undefined") return "";
  return String((window as any)?.Telegram?.WebApp?.initData || "").trim();
}

function readTelegramUser(): { first_name?: string; last_name?: string; username?: string } | null {
  if (typeof window === "undefined") return null;
  const user = (window as any)?.Telegram?.WebApp?.initDataUnsafe?.user;
  return user && typeof user === "object" ? user : null;
}

export default function MiniAppLegalHelpClient() {
  const { state, ready, recordAction } = useMiniAppState();
  const [insideTelegram, setInsideTelegram] = useState<boolean | null>(null);
  const [name, setName] = useState("");
  const [contact, setContact] = useState("");
  const [company, setCompany] = useState("");
  const [clientType, setClientType] = useState<LegalClientType>("unknown");
  const [area, setArea] = useState<LegalArea>("other");
  const [description, setDescription] = useState("");
  const [urgency, setUrgency] = useState<LegalUrgency>("no_deadline");
  const [deadline, setDeadline] = useState("");
  const [region, setRegion] = useState("");
  const [consentAccepted, setConsentAccepted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  useEffect(() => {
    if (!ready) return;
    if (state.audience === "business") setClientType("company");
    const user = readTelegramUser();
    if (user) {
      setName([user.first_name, user.last_name].filter(Boolean).join(" "));
      if (user.username) setContact(`@${user.username}`);
    }
  }, [ready, state.audience]);

  useEffect(() => {
    const check = () => setInsideTelegram(Boolean(readInitData()));
    check();
    const timer = setTimeout(check, 1200);
    return () => clearTimeout(timer);
  }, []);

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setError("");
    setSuccess("");
    if (description.trim().length < 20) {
      setError("Кратко опишите ситуацию и ожидаемый результат.");
      return;
    }
    if (!contact.trim()) {
      setError("Укажите контакт для связи.");
      return;
    }
    if (!consentAccepted) {
      setError("Нужно согласие на обработку персональных данных.");
      return;
    }

    setSubmitting(true);
    try {
      const response = await fetch("/api/reader/miniapp/legal-intake", {
        method: "POST",
        headers: { "Content-Type": "application/json", [INIT_DATA_HEADER]: readInitData() },
        body: JSON.stringify({
          telegram_user_id: state.telegramUserId,
          name,
          contact,
          company: clientType === "company" || clientType === "entrepreneur" ? company : undefined,
          client_type: clientType,
          legal_area: area,
          description,
          urgency,
          deadline: urgency === "no_deadline" ? undefined : deadline,
          region,
          consentAccepted,
        }),
      });
      const data = (await response.json()) as { detail?: string; message?: string };
      if (!response.ok) throw new Error(data.detail || "Не удалось отправить обращение.");
      setSuccess(data.message || "Обращение принято.");
      setDescription("");
      setDeadline("");
      recordAction("miniapp_legal_intake_submitted", {
        eventType: "lead_intent",
        source: "miniapp.legal_help",
        screen: "legal_help",
        payload: { clientType, area, urgency },
      });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Не удалось отправить обращение.");
    } finally {
      setSubmitting(false);
    }
  };

  if (insideTelegram === false) {
    return (
      <section className="space-y-4">
        <article className="rounded-lg border border-sky-500/30 bg-sky-500/10 p-4">
          <h2 className="font-semibold text-white">Откройте юридическую помощь в Telegram</h2>
          <p className="mt-2 text-sm text-slate-300">Mini App подтверждает пользователя через Telegram. В обычном браузере используйте сайт или ассистента.</p>
          <div className="mt-4 grid gap-2">
            <a href="/legal-help#legal-help-form" className="rounded-lg border border-slate-700 px-4 py-2 text-center text-sm font-semibold text-slate-200">Открыть форму на сайте</a>
            <a href={leadBotDeepLink("legal_help")} className="rounded-lg bg-amber-500 px-4 py-2 text-center text-sm font-semibold text-slate-950">Открыть ассистента</a>
          </div>
        </article>
      </section>
    );
  }

  return (
    <section className="space-y-4">
      <header className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-4">
        <h2 className="font-semibold text-white">Юридическая помощь</h2>
        <p className="mt-2 text-sm text-slate-300">Опишите ситуацию. Обращение получит юрист, а не автоматический консультант.</p>
      </header>

      <form onSubmit={onSubmit} className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="block">
            <span className="mb-1 block text-xs text-slate-300">Кому нужна помощь</span>
            <select value={clientType} onChange={(event) => setClientType(event.target.value as LegalClientType)} className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2.5 text-sm text-slate-100">
              {LEGAL_CLIENT_TYPES.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
            </select>
          </label>
          <label className="block">
            <span className="mb-1 block text-xs text-slate-300">Направление</span>
            <select value={area} onChange={(event) => setArea(event.target.value as LegalArea)} className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2.5 text-sm text-slate-100">
              {LEGAL_AREAS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
            </select>
          </label>
        </div>

        <label className="block">
          <span className="mb-1 block text-xs text-slate-300">Ситуация и желаемый результат</span>
          <textarea required rows={5} value={description} onChange={(event) => setDescription(event.target.value)} className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2.5 text-sm text-slate-100" />
        </label>

        <label className="block">
          <span className="mb-1 block text-xs text-slate-300">Ближайший срок</span>
          <select value={urgency} onChange={(event) => setUrgency(event.target.value as LegalUrgency)} className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2.5 text-sm text-slate-100">
            {LEGAL_URGENCY_LEVELS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
          </select>
        </label>

        {urgency !== "no_deadline" && (
          <input value={deadline} onChange={(event) => setDeadline(event.target.value)} placeholder="Дата или событие" className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2.5 text-sm text-slate-100" />
        )}
        <input value={region} onChange={(event) => setRegion(event.target.value)} placeholder="Регион" className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2.5 text-sm text-slate-100" />
        <input value={name} onChange={(event) => setName(event.target.value)} placeholder="Имя" className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2.5 text-sm text-slate-100" />
        <input required value={contact} onChange={(event) => setContact(event.target.value)} placeholder="Телефон, email или @telegram" className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2.5 text-sm text-slate-100" />
        {(clientType === "company" || clientType === "entrepreneur") && (
          <input value={company} onChange={(event) => setCompany(event.target.value)} placeholder="Организация" className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2.5 text-sm text-slate-100" />
        )}

        <div className="flex gap-3 rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-slate-300">
          <AlertTriangle className="h-4 w-4 shrink-0 text-amber-300" />
          <p>Не отправляйте пароли, полные паспортные данные и банковские реквизиты.</p>
        </div>
        <label className="flex gap-3 text-xs text-slate-300">
          <input type="checkbox" checked={consentAccepted} onChange={(event) => setConsentAccepted(event.target.checked)} className="mt-0.5 h-4 w-4" />
          <span>Согласен на обработку данных для рассмотрения обращения и связи со мной.</span>
        </label>

        {error && <p className="rounded-lg border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-200">{error}</p>}
        {success && <p className="rounded-lg border border-emerald-500/40 bg-emerald-500/10 p-3 text-sm text-emerald-200">{success}</p>}
        <button type="submit" disabled={submitting} className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-amber-500 px-4 py-3 text-sm font-semibold text-slate-950 disabled:opacity-60">
          <Send className="h-4 w-4" />
          {submitting ? "Отправка..." : "Передать задачу юристу"}
        </button>
      </form>
    </section>
  );
}
