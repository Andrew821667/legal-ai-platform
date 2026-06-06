"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Check, LockKeyhole, MessageSquareText, Send, ShieldCheck } from "lucide-react";

import LegalDisclaimer from "@/components/LegalDisclaimer";
import TurnstileWidget from "@/components/TurnstileWidget";

type LeadOffer = "consultation" | "checklist" | "demo" | "sample_report" | "unknown";
type LeadSegment = "inhouse" | "law_firm" | "entrepreneur" | "other";

const HONEYPOT_FIELD_NAME =
  (process.env.NEXT_PUBLIC_LEAD_FORM_HONEYPOT_FIELD || "company_website").trim() || "company_website";
const TURNSTILE_SITE_KEY = (process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY || "").trim();
const TURNSTILE_CHALLENGE_MODE = ((process.env.NEXT_PUBLIC_LEAD_FORM_CHALLENGE_MODE || "off").trim().toLowerCase());

declare global {
  interface WindowEventMap {
    lead_offer_selected: CustomEvent<{ offer: LeadOffer }>;
  }
}

const offerLabels: Record<LeadOffer, string> = {
  consultation: "Бесплатная консультация",
  checklist: "Гайд по внедрению ИИ",
  demo: "Демонстрационный разбор договора",
  sample_report: "Пример отчета по договору",
  unknown: "Общий запрос",
};

export default function LeadCaptureForm() {
  const [name, setName] = useState("");
  const [contact, setContact] = useState("");
  const [segment, setSegment] = useState<LeadSegment>("other");
  const [message, setMessage] = useState("");
  const [offer, setOffer] = useState<LeadOffer>("consultation");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [consentAccepted, setConsentAccepted] = useState(false);
  const [honeypotValue, setHoneypotValue] = useState("");
  const [challengeRequired, setChallengeRequired] = useState(TURNSTILE_CHALLENGE_MODE === "always");
  const [challengeToken, setChallengeToken] = useState("");
  const [startedAtMs] = useState(() => Date.now());

  useEffect(() => {
    const handler = (event: CustomEvent<{ offer: LeadOffer }>) => {
      setOffer(event.detail?.offer || "unknown");
      const target = document.getElementById("lead-form");
      target?.scrollIntoView({ behavior: "smooth", block: "start" });
    };
    window.addEventListener("lead_offer_selected", handler as EventListener);
    return () => window.removeEventListener("lead_offer_selected", handler as EventListener);
  }, []);

  const utm = useMemo(() => {
    if (typeof window === "undefined") {
      return {
        utm_source: undefined,
        utm_medium: undefined,
        utm_campaign: undefined,
        utm_content: undefined,
        utm_term: undefined,
        landing_page: undefined,
      };
    }
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

    if (!contact.trim()) {
      setError("Укажите контакт: email, телефон или Telegram.");
      return;
    }
    if (!consentAccepted) {
      setError("Нужно согласие на обработку персональных данных.");
      return;
    }
    if (challengeRequired && !TURNSTILE_SITE_KEY) {
      setError("Форма временно требует дополнительную проверку, но challenge не настроен на сайте.");
      return;
    }
    if (challengeRequired && TURNSTILE_SITE_KEY && !challengeToken) {
      setError("Подтвердите, что заявку отправляет человек.");
      return;
    }

    setIsSubmitting(true);
    try {
      const response = await fetch("/api/leads", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name,
          contact,
          segment,
          message,
          offer,
          consentAccepted,
          turnstile_token: challengeToken,
          _started_at_ms: startedAtMs,
          [HONEYPOT_FIELD_NAME]: honeypotValue,
          ...utm,
        }),
      });
      const data = (await response.json()) as {
        detail?: string;
        message?: string;
        challenge_required?: boolean;
      };
      if (!response.ok) {
        if (data.challenge_required) {
          setChallengeRequired(true);
        }
        throw new Error(data.detail || "Не удалось отправить заявку");
      }
      setSuccess(data.message || "Заявка отправлена.");
      setMessage("");
      setChallengeToken("");
      if (TURNSTILE_CHALLENGE_MODE !== "always") {
        setChallengeRequired(false);
      }
    } catch (e: unknown) {
      const text = e instanceof Error ? e.message : "Ошибка отправки заявки";
      setError(text);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <section id="lead-form" className="bg-slate-950 py-16 md:py-20">
      <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
        <div className="grid overflow-hidden rounded-lg border border-slate-700 bg-slate-900 lg:grid-cols-[0.82fr_1.18fr]">
          <div className="border-b border-slate-700 p-6 sm:p-8 lg:border-b-0 lg:border-r lg:p-10">
            <div className="flex h-11 w-11 items-center justify-center rounded-md bg-amber-400 text-slate-950">
              <MessageSquareText size={22} aria-hidden="true" />
            </div>
            <p className="mt-7 text-xs font-semibold uppercase text-amber-300">Прямой контакт</p>
            <h2 className="mt-2 text-3xl font-bold text-white md:text-4xl">
              Обсудить задачу
            </h2>
            <p className="mt-4 max-w-md text-base leading-7 text-slate-300">
              Текущий запрос: <span className="font-semibold text-white">{offerLabels[offer]}</span>.
              Ответим в Telegram, по телефону или email.
            </p>

            <div className="mt-8 space-y-4 border-t border-slate-700 pt-7">
              <div className="flex gap-3">
                <ShieldCheck className="mt-0.5 shrink-0 text-emerald-400" size={20} aria-hidden="true" />
                <div>
                  <p className="text-sm font-semibold text-white">Согласие фиксируется на сервере</p>
                  <p className="mt-1 text-sm leading-6 text-slate-400">Дата и версия документов сохраняются вместе с заявкой.</p>
                </div>
              </div>
              <div className="flex gap-3">
                <LockKeyhole className="mt-0.5 shrink-0 text-sky-400" size={20} aria-hidden="true" />
                <div>
                  <p className="text-sm font-semibold text-white">Без скрытой подписки</p>
                  <p className="mt-1 text-sm leading-6 text-slate-400">Контакт используется для ответа по вашему запросу.</p>
                </div>
              </div>
            </div>

            <LegalDisclaimer variant="panel" className="mt-8" />
          </div>

          <form onSubmit={onSubmit} className="space-y-6 bg-white p-6 sm:p-8 lg:p-10">
            <div>
              <p className="text-xs font-semibold uppercase text-slate-500">Шаг 1 из 2</p>
              <h3 className="mt-1 text-xl font-bold text-slate-950">Контакт и задача</h3>
            </div>

            <label
              className="absolute left-[-10000px] top-auto h-px w-px overflow-hidden"
              aria-hidden="true"
            >
              <span>{HONEYPOT_FIELD_NAME}</span>
              <input
                type="text"
                tabIndex={-1}
                autoComplete="off"
                value={honeypotValue}
                onChange={(e) => setHoneypotValue(e.target.value)}
              />
            </label>

            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <label className="block">
                <span className="mb-2 block text-sm font-semibold text-slate-700">Имя</span>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Андрей"
                  className="w-full rounded-md border border-slate-300 bg-white px-3.5 py-3 text-slate-950 outline-none transition focus:border-slate-950 focus:ring-2 focus:ring-slate-950/10"
                />
              </label>

              <label className="block">
                <span className="mb-2 block text-sm font-semibold text-slate-700">
                  Контакт <span className="text-red-600">*</span>
                </span>
                <input
                  type="text"
                  required
                  value={contact}
                  onChange={(e) => setContact(e.target.value)}
                  placeholder="+7..., email, @telegram"
                  className="w-full rounded-md border border-slate-300 bg-white px-3.5 py-3 text-slate-950 outline-none transition focus:border-slate-950 focus:ring-2 focus:ring-slate-950/10"
                />
              </label>
            </div>

            <div>
              <span className="mb-2 block text-sm font-semibold text-slate-700">Тип запроса</span>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                {([
                  ["consultation", "Консультация"],
                  ["demo", "Разбор"],
                  ["checklist", "Гайд"],
                  ["sample_report", "Отчёт"],
                ] as const).map(([value, label]) => (
                  <button
                    key={value}
                    type="button"
                    onClick={() => setOffer(value)}
                    className={`min-h-11 rounded-md border px-3 py-2 text-sm font-semibold transition ${
                      offer === value
                        ? "border-slate-950 bg-slate-950 text-white"
                        : "border-slate-300 bg-white text-slate-700 hover:border-slate-500"
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>

            <div className="grid grid-cols-1 gap-4 md:grid-cols-[0.42fr_0.58fr]">
              <label className="block">
                <span className="mb-2 block text-sm font-semibold text-slate-700">Кто вы</span>
                <select
                  value={segment}
                  onChange={(e) => setSegment(e.target.value as LeadSegment)}
                  className="w-full rounded-md border border-slate-300 bg-white px-3.5 py-3 text-slate-950 outline-none transition focus:border-slate-950 focus:ring-2 focus:ring-slate-950/10"
                >
                  <option value="other">Другое</option>
                  <option value="inhouse">Юридический отдел</option>
                  <option value="law_firm">Юридическая фирма</option>
                  <option value="entrepreneur">Предприниматель</option>
                </select>
              </label>
              <label className="block">
                <span className="mb-2 block text-sm font-semibold text-slate-700">Комментарий</span>
              <textarea
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                rows={3}
                placeholder="Кратко опишите задачу"
                  className="w-full resize-none rounded-md border border-slate-300 bg-white px-3.5 py-3 text-slate-950 outline-none transition focus:border-slate-950 focus:ring-2 focus:ring-slate-950/10"
              />
              </label>
            </div>

            <label
              className={`flex cursor-pointer items-start gap-4 rounded-md border p-4 transition ${
                consentAccepted
                  ? "border-emerald-500 bg-emerald-50"
                  : "border-amber-400 bg-amber-50 hover:border-amber-500"
              }`}
            >
              <input
                type="checkbox"
                checked={consentAccepted}
                onChange={(e) => setConsentAccepted(e.target.checked)}
                className="sr-only"
              />
              <span
                className={`mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded border ${
                  consentAccepted
                    ? "border-emerald-600 bg-emerald-600 text-white"
                    : "border-amber-500 bg-white text-transparent"
                }`}
              >
                <Check size={16} strokeWidth={3} aria-hidden="true" />
              </span>
              <span>
                <span className="block text-sm font-bold text-slate-950">
                  {consentAccepted ? "Согласие принято" : "Требуется ваше согласие"}
                </span>
                <span className="mt-1 block text-sm leading-6 text-slate-600">
                  Разрешаю обработку персональных данных и необходимую трансграничную передачу.
                  Условия описаны в{" "}
                  <Link href="/privacy" target="_blank" className="font-semibold text-slate-950 underline">
                    политике конфиденциальности
                  </Link>
                  .
                </span>
              </span>
            </label>

            <TurnstileWidget
              siteKey={TURNSTILE_SITE_KEY}
              enabled={challengeRequired && !!TURNSTILE_SITE_KEY}
              onToken={setChallengeToken}
            />

            {error && (
              <div role="alert" className="rounded-md border border-red-300 bg-red-50 px-4 py-3 text-sm font-medium text-red-800">
                {error}
              </div>
            )}

            {success && (
              <div role="status" className="rounded-md border border-emerald-300 bg-emerald-50 px-4 py-3 text-sm font-medium text-emerald-800">
                {success}
              </div>
            )}

            <div className="flex flex-col gap-3 border-t border-slate-200 pt-1 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-xs leading-5 text-slate-500">
                Отправка доступна после принятия политики.
              </p>
              <button
                type="submit"
                disabled={isSubmitting || !consentAccepted}
                className="inline-flex min-h-12 w-full items-center justify-center gap-2 rounded-md bg-amber-500 px-6 py-3 text-sm font-bold text-slate-950 transition hover:bg-amber-400 disabled:cursor-not-allowed disabled:bg-slate-200 disabled:text-slate-500 sm:w-auto"
              >
                {isSubmitting ? "Отправляем..." : "Отправить заявку"}
                {!isSubmitting && <Send size={17} aria-hidden="true" />}
              </button>
            </div>
          </form>
        </div>
      </div>
    </section>
  );
}
