"use client";

import { FormEvent, useMemo, useState } from "react";
import Link from "next/link";
import { AlertTriangle, Send } from "lucide-react";

import TurnstileWidget from "@/components/TurnstileWidget";
import {
  LEGAL_AREAS,
  LEGAL_CLIENT_TYPES,
  LEGAL_URGENCY_LEVELS,
  type LegalArea,
  type LegalClientType,
  type LegalUrgency,
} from "@/lib/legalHelp";

const HONEYPOT_FIELD_NAME =
  (process.env.NEXT_PUBLIC_LEAD_FORM_HONEYPOT_FIELD || "company_website").trim() || "company_website";
const TURNSTILE_SITE_KEY = (process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY || "").trim();
const CHALLENGE_MODE = (process.env.NEXT_PUBLIC_LEAD_FORM_CHALLENGE_MODE || "off").trim().toLowerCase();

type LegalHelpFormProps = {
  sourceContext: string;
  initialClientType?: LegalClientType;
  initialArea?: LegalArea;
};

export default function LegalHelpForm({
  sourceContext,
  initialClientType = "unknown",
  initialArea = "other",
}: LegalHelpFormProps) {
  const [name, setName] = useState("");
  const [contact, setContact] = useState("");
  const [company, setCompany] = useState("");
  const [clientType, setClientType] = useState<LegalClientType>(initialClientType);
  const [area, setArea] = useState<LegalArea>(initialArea);
  const [description, setDescription] = useState("");
  const [urgency, setUrgency] = useState<LegalUrgency>("no_deadline");
  const [deadline, setDeadline] = useState("");
  const [region, setRegion] = useState("");
  const [consentAccepted, setConsentAccepted] = useState(false);
  const [honeypot, setHoneypot] = useState("");
  const [challengeRequired, setChallengeRequired] = useState(CHALLENGE_MODE === "always");
  const [challengeToken, setChallengeToken] = useState("");
  const [startedAtMs] = useState(() => Date.now());
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const utm = useMemo(() => {
    if (typeof window === "undefined") return {};
    const params = new URLSearchParams(window.location.search);
    return {
      utm_source: params.get("utm_source") || undefined,
      utm_medium: params.get("utm_medium") || undefined,
      utm_campaign: params.get("utm_campaign") || undefined,
      utm_content: params.get("utm_content") || undefined,
      utm_term: params.get("utm_term") || undefined,
      landing_page: `${window.location.pathname}${window.location.search}`,
    };
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
      setError("Укажите телефон, email или Telegram для связи.");
      return;
    }
    if (!consentAccepted) {
      setError("Нужно согласие на обработку персональных данных.");
      return;
    }
    if (challengeRequired && TURNSTILE_SITE_KEY && !challengeToken) {
      setError("Подтвердите, что обращение отправляет человек.");
      return;
    }

    setSubmitting(true);
    try {
      const response = await fetch("/api/legal-intakes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name,
          contact,
          company: clientType === "company" || clientType === "entrepreneur" ? company : undefined,
          client_type: clientType,
          legal_area: area,
          description,
          urgency,
          deadline: urgency === "no_deadline" ? undefined : deadline,
          region,
          source_context: sourceContext,
          consentAccepted,
          turnstile_token: challengeToken,
          _started_at_ms: startedAtMs,
          [HONEYPOT_FIELD_NAME]: honeypot,
          ...utm,
        }),
      });
      const data = (await response.json()) as {
        detail?: string;
        message?: string;
        challenge_required?: boolean;
      };
      if (!response.ok) {
        if (data.challenge_required) setChallengeRequired(true);
        throw new Error(data.detail || "Не удалось отправить обращение.");
      }

      setSuccess(data.message || "Обращение принято.");
      setDescription("");
      setDeadline("");
      setChallengeToken("");
      if (CHALLENGE_MODE !== "always") setChallengeRequired(false);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Не удалось отправить обращение.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section id="legal-help-form" className="border-y border-slate-800 bg-slate-800/40">
      <div className="mx-auto max-w-5xl px-4 py-16 sm:px-6 lg:px-8">
        <div className="max-w-3xl">
          <p className="text-sm font-semibold text-amber-300">Первичное обращение</p>
          <h2 className="mt-2 text-3xl font-semibold text-white">Опишите юридическую задачу</h2>
          <p className="mt-3 text-slate-300">
            Юрист изучит описание, проверит возможность принять задачу и свяжется с вами для уточнения условий.
            Первичное обращение не заменяет консультацию и не означает автоматического принятия дела.
          </p>
        </div>

        <form onSubmit={onSubmit} className="mt-8 space-y-5 rounded-lg border border-slate-700 bg-slate-900/60 p-5 md:p-7">
          <label className="absolute left-[-10000px] h-px w-px overflow-hidden" aria-hidden="true">
            <span>{HONEYPOT_FIELD_NAME}</span>
            <input
              type="text"
              tabIndex={-1}
              autoComplete="off"
              value={honeypot}
              onChange={(event) => setHoneypot(event.target.value)}
            />
          </label>

          <div className="grid gap-4 md:grid-cols-2">
            <label className="block">
              <span className="mb-1 block text-sm font-medium text-slate-200">Кому нужна помощь</span>
              <select
                value={clientType}
                onChange={(event) => setClientType(event.target.value as LegalClientType)}
                className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-3 text-slate-100"
              >
                {LEGAL_CLIENT_TYPES.map((item) => (
                  <option key={item.value} value={item.value}>{item.label}</option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="mb-1 block text-sm font-medium text-slate-200">Направление</span>
              <select
                value={area}
                onChange={(event) => setArea(event.target.value as LegalArea)}
                className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-3 text-slate-100"
              >
                {LEGAL_AREAS.map((item) => (
                  <option key={item.value} value={item.value}>{item.label}</option>
                ))}
              </select>
            </label>
          </div>

          <label className="block">
            <span className="mb-1 block text-sm font-medium text-slate-200">Что произошло и какой результат нужен</span>
            <textarea
              required
              rows={6}
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="Кратко опишите обстоятельства, текущую стадию и ожидаемый результат"
              className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-3 text-slate-100 placeholder-slate-500"
            />
          </label>

          <div className="grid gap-4 md:grid-cols-2">
            <label className="block">
              <span className="mb-1 block text-sm font-medium text-slate-200">Ближайший срок</span>
              <select
                value={urgency}
                onChange={(event) => setUrgency(event.target.value as LegalUrgency)}
                className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-3 text-slate-100"
              >
                {LEGAL_URGENCY_LEVELS.map((item) => (
                  <option key={item.value} value={item.value}>{item.label}</option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="mb-1 block text-sm font-medium text-slate-200">Регион</span>
              <input
                value={region}
                onChange={(event) => setRegion(event.target.value)}
                placeholder="Например: Москва"
                className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-3 text-slate-100 placeholder-slate-500"
              />
            </label>
          </div>

          {urgency !== "no_deadline" && (
            <label className="block">
              <span className="mb-1 block text-sm font-medium text-slate-200">Дата или событие, к которому нужно успеть</span>
              <input
                value={deadline}
                onChange={(event) => setDeadline(event.target.value)}
                placeholder="Например: заседание 20 июля"
                className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-3 text-slate-100 placeholder-slate-500"
              />
            </label>
          )}

          <div className="grid gap-4 md:grid-cols-2">
            <label className="block">
              <span className="mb-1 block text-sm font-medium text-slate-200">Имя</span>
              <input
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="Как к вам обращаться"
                className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-3 text-slate-100 placeholder-slate-500"
              />
            </label>
            <label className="block">
              <span className="mb-1 block text-sm font-medium text-slate-200">Контакт</span>
              <input
                required
                value={contact}
                onChange={(event) => setContact(event.target.value)}
                placeholder="Телефон, email или @telegram"
                className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-3 text-slate-100 placeholder-slate-500"
              />
            </label>
          </div>

          {(clientType === "company" || clientType === "entrepreneur") && (
            <label className="block">
              <span className="mb-1 block text-sm font-medium text-slate-200">Организация</span>
              <input
                value={company}
                onChange={(event) => setCompany(event.target.value)}
                placeholder="Название или ИП"
                className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-3 text-slate-100 placeholder-slate-500"
              />
            </label>
          )}

          <div className="flex gap-3 rounded-lg border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-slate-200">
            <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-amber-300" />
            <p>Не указывайте в первичном обращении пароли, полные паспортные данные и реквизиты банковских карт. Документы запросим отдельно при необходимости.</p>
          </div>

          <label className="flex items-start gap-3 text-sm text-slate-300">
            <input
              type="checkbox"
              checked={consentAccepted}
              onChange={(event) => setConsentAccepted(event.target.checked)}
              className="mt-1 h-4 w-4 rounded border-slate-600 text-amber-500"
            />
            <span>
              Я согласен на обработку данных для рассмотрения обращения и связи со мной. Подробнее в{" "}
              <Link href="/privacy" className="text-amber-300 underline">политике конфиденциальности</Link>.
            </span>
          </label>

          <TurnstileWidget
            siteKey={TURNSTILE_SITE_KEY}
            enabled={challengeRequired && !!TURNSTILE_SITE_KEY}
            onToken={setChallengeToken}
          />

          {error && <p className="rounded-lg border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-200">{error}</p>}
          {success && <p className="rounded-lg border border-emerald-500/40 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-200">{success}</p>}

          <button
            type="submit"
            disabled={submitting}
            className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-amber-500 px-6 py-3 font-semibold text-slate-950 hover:bg-amber-400 disabled:opacity-60 md:w-auto"
          >
            <Send className="h-4 w-4" />
            {submitting ? "Отправка..." : "Передать задачу юристу"}
          </button>
        </form>
      </div>
    </section>
  );
}
