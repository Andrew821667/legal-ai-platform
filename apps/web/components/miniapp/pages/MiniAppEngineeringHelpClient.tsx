"use client";

import { FormEvent, useEffect, useState } from "react";
import { AlertTriangle, Send } from "lucide-react";

import { useMiniAppState } from "@/components/miniapp/MiniAppStateProvider";
import { leadBotDeepLink } from "@/lib/links";
import { LEGAL_CLIENT_TYPES, type LegalClientType } from "@/lib/legalHelp";

/**
 * Обращение в инженерную практику — и в гибридную, автоматизацию юридической
 * функции — из мини-аппа. Та же форма, что у юридического обращения, но
 * вместо области права — категория задачи, и уходит оно с practice, по
 * которому ядро выберет шаблон договора и условия.
 */

const INIT_DATA_HEADER = "X-Telegram-Init-Data";

type Practice = "engineering" | "hybrid";

const PRACTICES: { value: Practice; label: string; hint: string }[] = [
  {
    value: "engineering",
    label: "Инженерная задача",
    hint: "бот, сайт, Mini App, внутренняя программа, AI-модуль, интеграция",
  },
  {
    value: "hybrid",
    label: "Автоматизация юридической функции",
    hint: "юристы разбирают процесс и правила, инженеры — систему",
  },
];

const CATEGORIES: Record<Practice, { value: string; label: string }[]> = {
  engineering: [
    { value: "telegram_bot", label: "Telegram-бот" },
    { value: "website", label: "Сайт" },
    { value: "miniapp", label: "Mini App" },
    { value: "internal_tool", label: "Внутренняя программа" },
    { value: "ai_module", label: "AI-модуль" },
    { value: "integration", label: "Интеграция с CRM/1С/ЭДО" },
    { value: "other", label: "Другое" },
  ],
  hybrid: [
    { value: "contracts_flow", label: "Договорная работа" },
    { value: "claims_flow", label: "Претензии и споры" },
    { value: "compliance", label: "Комплаенс" },
    { value: "document_flow", label: "Документооборот" },
    { value: "staff_consulting", label: "Консультирование сотрудников" },
    { value: "other", label: "Другое" },
  ],
};

const DESCRIPTION_HINT: Record<Practice, string> = {
  engineering:
    "Что нужно автоматизировать и как это делается сейчас — вручную, в таблице, в другой системе. Если есть срок или техническое задание, упомяните.",
  hybrid:
    "Какой юридический процесс хотите автоматизировать: что в него входит, как идёт сейчас, где теряется время или возникает риск.",
};

function readInitData(): string {
  if (typeof window === "undefined") return "";
  return String((window as any)?.Telegram?.WebApp?.initData || "").trim();
}

function readTelegramUser(): { first_name?: string; last_name?: string; username?: string } | null {
  if (typeof window === "undefined") return null;
  const user = (window as any)?.Telegram?.WebApp?.initDataUnsafe?.user;
  return user && typeof user === "object" ? user : null;
}

export default function MiniAppEngineeringHelpClient() {
  const { state, ready, recordAction } = useMiniAppState();
  const [insideTelegram, setInsideTelegram] = useState<boolean | null>(null);
  const [practice, setPractice] = useState<Practice>("engineering");
  const [category, setCategory] = useState("telegram_bot");
  const [clientType, setClientType] = useState<LegalClientType>("company");
  const [name, setName] = useState("");
  const [contact, setContact] = useState("");
  const [company, setCompany] = useState("");
  const [description, setDescription] = useState("");
  const [consentAccepted, setConsentAccepted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  useEffect(() => {
    if (!ready) return;
    const user = readTelegramUser();
    if (user) {
      setName([user.first_name, user.last_name].filter(Boolean).join(" "));
      if (user.username) setContact(`@${user.username}`);
    }
  }, [ready]);

  useEffect(() => {
    const check = () => setInsideTelegram(Boolean(readInitData()));
    check();
    const timer = setTimeout(check, 1200);
    return () => clearTimeout(timer);
  }, []);

  const choosePractice = (next: Practice) => {
    setPractice(next);
    setCategory(CATEGORIES[next][0].value);
  };

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setError("");
    setSuccess("");
    if (description.trim().length < 20) {
      setError("Опишите задачу хотя бы в нескольких предложениях.");
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
          practice,
          category,
          description,
          urgency: "no_deadline",
          consentAccepted,
        }),
      });
      const data = (await response.json()) as { detail?: string; message?: string };
      if (!response.ok) throw new Error(data.detail || "Не удалось отправить задачу.");
      setSuccess(data.message || "Задача принята.");
      setDescription("");
      recordAction("miniapp_engineering_intake_submitted", {
        eventType: "lead_intent",
        source: "miniapp.engineering_help",
        screen: "engineering_help",
        payload: { practice, category, clientType },
      });
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Не удалось отправить задачу.");
    } finally {
      setSubmitting(false);
    }
  };

  if (insideTelegram === false) {
    return (
      <section className="space-y-4">
        <article className="rounded-lg border border-sky-500/30 bg-sky-500/10 p-4">
          <h2 className="font-semibold text-white">Откройте инженерную практику в Telegram</h2>
          <p className="mt-2 text-sm text-slate-300">Mini App подтверждает пользователя через Telegram. В обычном браузере используйте ассистента.</p>
          <div className="mt-4 grid gap-2">
            <a href={leadBotDeepLink("engineering_help")} className="rounded-lg bg-amber-500 px-4 py-2 text-center text-sm font-semibold text-slate-950">Открыть ассистента</a>
          </div>
        </article>
      </section>
    );
  }

  return (
    <section className="space-y-4">
      <header className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-4">
        <h2 className="font-semibold text-white">Инженерная практика</h2>
        <p className="mt-2 text-sm text-slate-300">Опишите задачу. Её получит команда, которая делает боты, сайты, Mini App, внутренние программы и интеграции — и оценит срок и стоимость.</p>
      </header>

      <form onSubmit={onSubmit} className="space-y-4">
        <div className="grid gap-2">
          {PRACTICES.map((item) => (
            <button
              key={item.value}
              type="button"
              aria-pressed={practice === item.value}
              onClick={() => choosePractice(item.value)}
              className={`rounded-lg border bg-slate-800 px-3 py-2.5 text-left text-sm transition-colors ${
                practice === item.value
                  ? "border-amber-500 text-white ring-2 ring-amber-500"
                  : "border-slate-700 text-slate-200"
              }`}
            >
              <span className="block font-semibold">{item.label}</span>
              <span className="block text-xs text-slate-400">{item.hint}</span>
            </button>
          ))}
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          <label className="block">
            <span className="mb-1 block text-xs text-slate-300">{practice === "engineering" ? "Что нужно сделать" : "Какой процесс"}</span>
            <select value={category} onChange={(event) => setCategory(event.target.value)} className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2.5 text-sm text-slate-100">
              {CATEGORIES[practice].map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
            </select>
          </label>
          <label className="block">
            <span className="mb-1 block text-xs text-slate-300">От чьего имени</span>
            <select value={clientType} onChange={(event) => setClientType(event.target.value as LegalClientType)} className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2.5 text-sm text-slate-100">
              {LEGAL_CLIENT_TYPES.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
            </select>
          </label>
        </div>

        <label className="block">
          <span className="mb-1 block text-xs text-slate-300">Задача и как это устроено сейчас</span>
          <textarea required rows={5} value={description} onChange={(event) => setDescription(event.target.value)} placeholder={DESCRIPTION_HINT[practice]} className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2.5 text-sm text-slate-100" />
        </label>

        <input value={name} onChange={(event) => setName(event.target.value)} placeholder="Имя" className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2.5 text-sm text-slate-100" />
        <input required value={contact} onChange={(event) => setContact(event.target.value)} placeholder="Телефон, email или @telegram" className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2.5 text-sm text-slate-100" />
        {(clientType === "company" || clientType === "entrepreneur") && (
          <input value={company} onChange={(event) => setCompany(event.target.value)} placeholder="Организация" className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2.5 text-sm text-slate-100" />
        )}

        <div className="flex gap-3 rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-slate-300">
          <AlertTriangle className="h-4 w-4 shrink-0 text-amber-300" />
          <p>Не отправляйте пароли, ключи доступа и банковские реквизиты. Доступы к системам попросим отдельно, когда договоримся.</p>
        </div>
        <label className="flex gap-3 text-xs text-slate-300">
          <input type="checkbox" checked={consentAccepted} onChange={(event) => setConsentAccepted(event.target.checked)} className="mt-0.5 h-4 w-4" />
          <span>Согласен на обработку данных для рассмотрения задачи и связи со мной.</span>
        </label>

        {error && <p className="rounded-lg border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-200">{error}</p>}
        {success && <p className="rounded-lg border border-emerald-500/40 bg-emerald-500/10 p-3 text-sm text-emerald-200">{success}</p>}
        <button type="submit" disabled={submitting} className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-amber-500 px-4 py-3 text-sm font-semibold text-slate-950 disabled:opacity-60">
          <Send className="h-4 w-4" />
          {submitting ? "Отправка..." : practice === "engineering" ? "Передать задачу инженерам" : "Передать задачу команде"}
        </button>
      </form>
    </section>
  );
}
