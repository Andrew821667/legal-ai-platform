"use client";

import { useEffect, useState } from "react";

import YandexMetrika from "@/components/YandexMetrika";
import {
  COOKIE_CONSENT_EVENT,
  analyticsAllowed,
  cookieConsentMode,
  readCookieConsent,
  type CookieConsent,
} from "@/lib/cookie-consent";

const MODE = cookieConsentMode(process.env.NEXT_PUBLIC_COOKIE_CONSENT_MODE);

/**
 * Счётчик Яндекс Метрики — если посетитель не отказался (в режиме opt_in — только
 * после согласия). Google Analytics убран: данные посетителей не уходят за рубеж.
 */
export default function AnalyticsGate({ ymId }: { ymId?: string }) {
  const [consent, setConsent] = useState<CookieConsent | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const sync = () => setConsent(readCookieConsent(typeof window === "undefined" ? null : window.localStorage));
    sync();
    setReady(true);
    window.addEventListener(COOKIE_CONSENT_EVENT, sync);
    return () => window.removeEventListener(COOKIE_CONSENT_EVENT, sync);
  }, []);

  if (!ready || !analyticsAllowed(MODE, consent)) return null;
  return ymId ? <YandexMetrika counterId={ymId} /> : null;
}
