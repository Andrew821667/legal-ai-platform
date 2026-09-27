"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import {
  COOKIE_CONSENT_EVENT,
  cookieConsentMode,
  readCookieConsent,
  writeCookieConsent,
  type CookieConsent,
} from "@/lib/cookie-consent";

const MODE = cookieConsentMode(process.env.NEXT_PUBLIC_COOKIE_CONSENT_MODE);

/**
 * Баннер cookies веб-аналитики. Пока посетитель не выбрал, в режиме opt_in
 * счётчики не загружаются (см. AnalyticsGate). Справа снизу — кнопка
 * ассистента, поэтому на телефоне баннер оставляет ей место.
 */
export default function CookieConsentBanner() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    setVisible(readCookieConsent(window.localStorage) === null);
  }, []);

  const choose = (value: CookieConsent) => {
    writeCookieConsent(window.localStorage, value);
    window.dispatchEvent(new Event(COOKIE_CONSENT_EVENT));
    setVisible(false);
  };

  if (!visible) return null;
  return (
    <div
      role="dialog"
      aria-label="Cookies"
      className="fixed bottom-24 left-4 right-4 z-40 rounded-xl border border-slate-300 bg-white p-4 text-sm text-slate-700 shadow-lg sm:bottom-4 sm:right-auto sm:max-w-md"
    >
      <p>
        {MODE === "notice"
          ? "Мы используем cookies Яндекс Метрики и Google Analytics, чтобы понимать, какие страницы полезны. Можно отказаться."
          : "Разрешите cookies Яндекс Метрики и Google Analytics — так мы понимаем, какие страницы полезны. Без разрешения счётчики не включаются."}{" "}
        <Link href="/privacy#cookies" className="text-amber-700 underline underline-offset-2">
          Подробнее
        </Link>
      </p>
      <div className="mt-3 flex gap-2">
        <button
          type="button"
          onClick={() => choose("accepted")}
          className="rounded-lg bg-amber-600 px-4 py-2 font-semibold text-white hover:bg-amber-700"
        >
          {MODE === "notice" ? "Понятно" : "Принять"}
        </button>
        <button
          type="button"
          onClick={() => choose("declined")}
          className="rounded-lg border border-slate-300 px-4 py-2 font-semibold text-slate-700 hover:bg-slate-100"
        >
          Отказаться
        </button>
      </div>
    </div>
  );
}
