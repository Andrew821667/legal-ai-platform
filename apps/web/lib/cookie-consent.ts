/**
 * Согласие на cookies веб-аналитики (Яндекс Метрика, Google Analytics).
 *
 * opt_in (по умолчанию) — счётчики включаются только после «Принять».
 * notice — счётчики работают сразу, баннер уведомляет и даёт отказаться.
 * Выбор хранится у посетителя в браузере; без хранилища — как «не выбрано».
 */
export type CookieConsent = "accepted" | "declined";
export type CookieConsentMode = "opt_in" | "notice";

export const COOKIE_CONSENT_KEY = "ai_verdict_cookie_consent";
export const COOKIE_CONSENT_EVENT = "ai-verdict:cookie-consent";

type StorageLike = Pick<Storage, "getItem" | "setItem">;

export function cookieConsentMode(raw: string | undefined): CookieConsentMode {
  return (raw || "").trim().toLowerCase() === "notice" ? "notice" : "opt_in";
}

export function readCookieConsent(storage: StorageLike | null | undefined): CookieConsent | null {
  try {
    const value = storage?.getItem(COOKIE_CONSENT_KEY);
    return value === "accepted" || value === "declined" ? value : null;
  } catch {
    return null;
  }
}

export function writeCookieConsent(storage: StorageLike | null | undefined, value: CookieConsent): void {
  try {
    storage?.setItem(COOKIE_CONSENT_KEY, value);
  } catch {
    // Приватный режим или запрет хранилища: выбор действует до перезагрузки.
  }
}

export function analyticsAllowed(mode: CookieConsentMode, consent: CookieConsent | null): boolean {
  if (consent === "declined") return false;
  return consent === "accepted" || mode === "notice";
}
