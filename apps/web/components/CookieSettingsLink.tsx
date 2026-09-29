"use client";

import { COOKIE_CONSENT_EVENT, COOKIE_CONSENT_KEY } from "@/lib/cookie-consent";

/** Сбросить выбор по cookies: баннер появится снова после перезагрузки. */
export default function CookieSettingsLink({ className }: { className?: string }) {
  const reset = () => {
    try {
      window.localStorage.removeItem(COOKIE_CONSENT_KEY);
    } catch {
      // хранилище недоступно — выбор и так не сохранялся
    }
    window.dispatchEvent(new Event(COOKIE_CONSENT_EVENT));
    window.location.reload();
  };
  return (
    <button type="button" onClick={reset} className={className}>
      Настройки cookies
    </button>
  );
}
