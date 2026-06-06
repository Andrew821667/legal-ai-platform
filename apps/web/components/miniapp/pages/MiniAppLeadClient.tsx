"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { Check, Send, ShieldCheck } from "lucide-react";
import { useMiniAppState, type MiniAppAudience } from "@/components/miniapp/MiniAppStateProvider";
import { leadBotDeepLink } from "@/lib/links";

type LeadOffer = "consultation" | "checklist" | "demo" | "sample_report" | "unknown";
type LeadSegment = "inhouse" | "law_firm" | "entrepreneur" | "other";

const TELEGRAM_INIT_DATA_HEADER = "X-Telegram-Init-Data";

const offerLabels: Record<LeadOffer, string> = {
  consultation: "Бесплатная консультация",
  checklist: "Гайд по внедрению ИИ",
  demo: "Демонстрационный разбор договора",
  sample_report: "Пример отчёта по договору",
  unknown: "Общий запрос",
};

const audienceToSegment: Record<MiniAppAudience, LeadSegment> = {
  lawyer: "law_firm",
  business: "inhouse",
  mixed: "other",
};

type TelegramUserInfo = {
  first_name?: string;
  last_name?: string;
  username?: string;
};

function readTelegramUser(): TelegramUserInfo | null {
  if (typeof window === "undefined") {
    return null;
  }
  const raw = (window as any)?.Telegram?.WebApp?.initDataUnsafe?.user;
  if (!raw || typeof raw !== "object") {
    return null;
  }
  return raw as TelegramUserInfo;
}

function readInitData(): string {
  if (typeof window === "undefined") {
    return "";
  }
  return String((window as any)?.Telegram?.WebApp?.initData || "").trim();
}

export default function MiniAppLeadPage() {
  const { state, ready, recordAction } = useMiniAppState();

  const [contact, setContact] = useState("");
  const [name, setName] = useState("");
  const [offer, setOffer] = useState<LeadOffer>("consultation");
  const [message, setMessage] = useState("");
  const [segment, setSegment] = useState<LeadSegment>("other");
  const [consentAccepted, setConsentAccepted] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  // null while we wait for the Telegram WebApp object to load, then bool
  const [insideTelegram, setInsideTelegram] = useState<boolean | null>(null);

  useEffect(() => {
    if (!ready) {
      return;
    }
    setSegment(audienceToSegment[state.audience]);

    const tgUser = readTelegramUser();
    if (tgUser && !name) {
      const parts = [tgUser.first_name, tgUser.last_name].filter(Boolean) as string[];
      if (parts.length > 0) {
        setName(parts.join(" "));
      }
    }
    if (tgUser?.username && !contact) {
      setContact(`@${tgUser.username}`);
    }
  }, [ready, state.audience, name, contact]);

  // Detect whether we're actually inside a Telegram WebView. The Telegram
  // script populates window.Telegram.WebApp.initData; if it's empty we're
  // in a regular browser and the POST will 401 — show a friendly nudge
  // instead of letting the user fill the form for nothing.
  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const check = () => setInsideTelegram(Boolean(readInitData()));
    check();
    // Telegram injects initData a moment after page load on some clients
    const timeoutId = setTimeout(check, 1200);
    return () => clearTimeout(timeoutId);
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
      utm_source: params.get("utm_source") || "miniapp",
      utm_medium: params.get("utm_medium") || "telegram",
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
      setError("Укажите контакт: телефон, email или Telegram.");
      return;
    }
    if (!consentAccepted) {
      setError("Подтвердите согласие на обработку персональных данных.");
      return;
    }

    setIsSubmitting(true);
    try {
      const initData = readInitData();
      const headers: Record<string, string> = {
        "Content-Type": "application/json",
      };
      if (initData) {
        headers[TELEGRAM_INIT_DATA_HEADER] = initData;
      }

      const response = await fetch("/api/reader/miniapp/lead", {
        method: "POST",
        headers,
        body: JSON.stringify({
          telegram_user_id: state.telegramUserId,
          contact,
          name,
          consentAccepted,
          segment,
          offer,
          message,
          audience: state.audience,
          goal: state.goal,
          ...utm,
        }),
      });

      const data = (await response.json()) as { detail?: string; message?: string };
      if (!response.ok) {
        throw new Error(data.detail || "Не удалось отправить заявку");
      }

      setSuccess(data.message || "Заявка отправлена. Мы свяжемся в ближайшее время.");
      setMessage("");

      recordAction("miniapp_lead_submitted", {
        eventType: "lead_intent",
        source: "miniapp",
        screen: "lead",
        payload: { offer, segment },
      });
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Ошибка отправки заявки");
    } finally {
      setIsSubmitting(false);
    }
  };

  if (insideTelegram === false) {
    return (
      <section className="space-y-5">
        <header className="rounded-xl border border-sky-500/40 bg-sky-500/10 p-4">
          <h2 className="text-base font-semibold text-sky-200">Откройте через Telegram</h2>
          <p className="mt-2 text-sm text-slate-300">
            Эта страница — Mini App внутри Telegram, она требует авторизации
            через клиент Telegram. В обычном браузере отправить заявку отсюда
            не получится.
          </p>
          <p className="mt-3 text-sm text-slate-300">
            Если вы хотите оставить заявку прямо сейчас — откройте бота:
          </p>
          <a
            href={leadBotDeepLink("web_miniapp_lead_fallback")}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-3 inline-flex items-center justify-center rounded-lg bg-sky-500 px-4 py-2 text-sm font-semibold text-slate-950 transition-colors hover:bg-sky-400"
          >
            Открыть @legal_ai_helper_new_bot
          </a>
          <p className="mt-3 text-xs text-slate-400">
            Или используйте обычную{" "}
            <a href="/#lead-form" className="text-amber-300 underline">
              форму на сайте
            </a>{" "}
            — она работает в любом браузере и без авторизации.
          </p>
        </header>
      </section>
    );
  }

  return (
    <section className="space-y-5">
      <header className="border-b border-slate-700 pb-5">
        <div className="flex items-start gap-3">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-amber-400 text-slate-950">
            <Send size={19} aria-hidden="true" />
          </span>
          <div>
            <h2 className="text-lg font-bold text-white">Отправить запрос</h2>
            <p className="mt-1 text-sm leading-6 text-slate-400">
              Менеджер получит контакт и контекст задачи. Тип:{" "}
              <span className="font-semibold text-amber-300">{offerLabels[offer]}</span>.
            </p>
          </div>
        </div>
      </header>

      <form onSubmit={onSubmit} className="space-y-5">
        <label className="block">
          <span className="block text-xs font-medium text-slate-300 mb-1">Имя</span>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Андрей"
            className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2.5 text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-amber-500/40"
          />
        </label>

        <label className="block">
          <span className="block text-xs font-medium text-slate-300 mb-1">
            Контакт (обязательно)
          </span>
          <input
            type="text"
            required
            value={contact}
            onChange={(e) => setContact(e.target.value)}
            placeholder="+7..., email, @telegram"
            className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2.5 text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-amber-500/40"
          />
        </label>

        <label className="block">
          <span className="block text-xs font-medium text-slate-300 mb-1">Тип запроса</span>
          <select
            value={offer}
            onChange={(e) => setOffer(e.target.value as LeadOffer)}
            className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2.5 text-slate-100 focus:outline-none focus:ring-2 focus:ring-amber-500/40"
          >
            <option value="consultation">Консультация</option>
            <option value="checklist">Гайд</option>
            <option value="demo">Демонстрационный разбор договора</option>
            <option value="sample_report">Пример отчёта по договору</option>
            <option value="unknown">Общий запрос</option>
          </select>
        </label>

        <label className="block">
          <span className="block text-xs font-medium text-slate-300 mb-1">Сегмент</span>
          <select
            value={segment}
            onChange={(e) => setSegment(e.target.value as LeadSegment)}
            className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2.5 text-slate-100 focus:outline-none focus:ring-2 focus:ring-amber-500/40"
          >
            <option value="other">Другое</option>
            <option value="inhouse">Юридический отдел компании</option>
            <option value="law_firm">Юридическая фирма</option>
            <option value="entrepreneur">Предприниматель</option>
          </select>
        </label>

        <label className="block">
          <span className="block text-xs font-medium text-slate-300 mb-1">Комментарий</span>
          <textarea
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            rows={3}
            placeholder="Кратко опишите задачу"
            className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2.5 text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-amber-500/40"
          />
        </label>

        <label
          className={`flex cursor-pointer items-start gap-3 rounded-md border p-4 transition ${
            consentAccepted
              ? "border-emerald-500 bg-emerald-500/10"
              : "border-amber-400 bg-amber-400/10"
          }`}
        >
          <input
            type="checkbox"
            checked={consentAccepted}
            onChange={(event) => setConsentAccepted(event.target.checked)}
            className="sr-only"
          />
          <span
            className={`mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded border ${
              consentAccepted
                ? "border-emerald-400 bg-emerald-400 text-slate-950"
                : "border-amber-400 bg-slate-900 text-transparent"
            }`}
          >
            <Check size={16} strokeWidth={3} aria-hidden="true" />
          </span>
          <span>
            <span className="flex items-center gap-2 text-sm font-bold text-white">
              <ShieldCheck size={16} className="text-emerald-400" aria-hidden="true" />
              {consentAccepted ? "Согласие принято" : "Разрешить обработку данных"}
            </span>
            <span className="mt-1 block text-xs leading-5 text-slate-400">
              Контакт используется для ответа по заявке.{" "}
              <a href="/privacy" target="_blank" rel="noopener noreferrer" className="font-semibold text-amber-300 underline">
                Политика ПД
              </a>
            </span>
          </span>
        </label>

        {error && (
          <div className="rounded-lg border border-red-500/50 bg-red-500/10 px-3 py-2 text-sm text-red-300">
            {error}
          </div>
        )}

        {success && (
          <div className="rounded-lg border border-emerald-500/50 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-300">
            {success}
          </div>
        )}

        <button
          type="submit"
          disabled={isSubmitting || !consentAccepted}
          className="inline-flex min-h-12 w-full items-center justify-center gap-2 rounded-md bg-amber-400 px-4 py-3 text-sm font-bold text-slate-950 transition-colors hover:bg-amber-300 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-400"
        >
          {isSubmitting ? "Отправка..." : "Отправить заявку"}
          {!isSubmitting && <Send size={17} aria-hidden="true" />}
        </button>
      </form>
    </section>
  );
}
