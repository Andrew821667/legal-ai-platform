"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import Link from "next/link";

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
  unknown: "Общий запрос / разработка под задачу",
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
    <section id="lead-form" className="py-20 bg-white">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="rounded-2xl border border-slate-200 shadow-lg bg-slate-50 p-6 md:p-10">
          <h2 className="text-3xl md:text-4xl font-bold text-slate-900 mb-3">
            Оставить заявку
          </h2>
          <p className="text-slate-600 mb-8">
            Запрос: <span className="font-semibold">{offerLabels[offer]}</span>. Ответим в Telegram
            или по телефону. Можно описать не только юридический процесс, но и любую смежную автоматизацию:
            бота, сайт, mini app, интеграцию, внутренний сервис или отдельную программу.
          </p>

          <LegalDisclaimer variant="panel" className="mb-6" />

          <form onSubmit={onSubmit} className="space-y-4">
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

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <label className="block">
                <span className="block text-sm font-medium text-slate-700 mb-1">Имя</span>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Андрей"
                  className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-slate-900 focus:outline-none focus:ring-2 focus:ring-amber-500/40"
                />
              </label>

              <label className="block">
                <span className="block text-sm font-medium text-slate-700 mb-1">
                  Контакт (обязательно)
                </span>
                <input
                  type="text"
                  required
                  value={contact}
                  onChange={(e) => setContact(e.target.value)}
                  placeholder="+7..., email, @telegram"
                  className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-slate-900 focus:outline-none focus:ring-2 focus:ring-amber-500/40"
                />
              </label>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <label className="block">
                <span className="block text-sm font-medium text-slate-700 mb-1">Сегмент</span>
                <select
                  value={segment}
                  onChange={(e) => setSegment(e.target.value as LeadSegment)}
                  className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-slate-900 focus:outline-none focus:ring-2 focus:ring-amber-500/40"
                >
                  <option value="other">Другое</option>
                  <option value="inhouse">Юридический отдел компании</option>
                  <option value="law_firm">Юридическая фирма</option>
                  <option value="entrepreneur">Предприниматель</option>
                </select>
              </label>

              <label className="block">
                <span className="block text-sm font-medium text-slate-700 mb-1">Тип запроса</span>
                <select
                  value={offer}
                  onChange={(e) => setOffer(e.target.value as LeadOffer)}
                  className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-slate-900 focus:outline-none focus:ring-2 focus:ring-amber-500/40"
                >
                  <option value="consultation">Консультация</option>
                  <option value="checklist">Гайд</option>
                  <option value="demo">Демонстрационный разбор договора</option>
                  <option value="sample_report">Пример отчета по договору</option>
                  <option value="unknown">Общий запрос / разработка под задачу</option>
                </select>
              </label>
            </div>

            <label className="block">
              <span className="block text-sm font-medium text-slate-700 mb-1">Комментарий</span>
              <textarea
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                rows={4}
                placeholder="Кратко опишите задачу: юридический процесс, интеграция, бот, сайт, mini app, внутренняя программа или другая автоматизация"
                className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-slate-900 focus:outline-none focus:ring-2 focus:ring-amber-500/40"
              />
            </label>

            <label className="flex items-start gap-3 rounded-lg border border-slate-200 bg-white px-4 py-3">
              <input
                type="checkbox"
                checked={consentAccepted}
                onChange={(e) => setConsentAccepted(e.target.checked)}
                className="mt-1 h-4 w-4 rounded border-slate-300 text-amber-600 focus:ring-amber-500"
              />
              <span className="text-sm text-slate-600">
                Я соглашаюсь на обработку персональных данных и, при использовании зарубежной
                инфраструктуры аналитики и хостинга, на возможную трансграничную передачу данных в
                объеме, необходимом для работы сайта. Подробнее:{" "}
                <Link href="/privacy" className="text-amber-700 underline">
                  политика конфиденциальности
                </Link>
                .
              </span>
            </label>

            <TurnstileWidget
              siteKey={TURNSTILE_SITE_KEY}
              enabled={challengeRequired && !!TURNSTILE_SITE_KEY}
              onToken={setChallengeToken}
            />

            {error && (
              <div className="rounded-lg border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-700">
                {error}
              </div>
            )}

            {success && (
              <div className="rounded-lg border border-green-300 bg-green-50 px-3 py-2 text-sm text-green-700">
                {success}
              </div>
            )}

            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full md:w-auto inline-flex items-center justify-center rounded-lg bg-amber-600 px-6 py-3 font-semibold text-white hover:bg-amber-700 disabled:opacity-60"
            >
              {isSubmitting ? "Отправка..." : "Отправить заявку"}
            </button>
          </form>

          <p className="text-xs text-slate-500 mt-4">
            Форму используем только для связи по вашему запросу и первичной квалификации задачи.
          </p>
        </div>
      </div>
    </section>
  );
}
