"use client";

import { useEffect, useState } from "react";

import GoogleAnalytics from "@/components/GoogleAnalytics";
import YandexMetrika from "@/components/YandexMetrika";
import {
  COOKIE_CONSENT_EVENT,
  analyticsAllowed,
  cookieConsentMode,
  readCookieConsent,
  type CookieConsent,
} from "@/lib/cookie-consent";

const MODE = cookieConsentMode(process.env.NEXT_PUBLIC_COOKIE_CONSENT_MODE);

/** Счётчики — только когда посетитель разрешил (или в уведомительном режиме не отказался). */
export default function AnalyticsGate({ gaId, ymId }: { gaId?: string; ymId?: string }) {
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
  return (
    <>
      {gaId ? <GoogleAnalytics measurementId={gaId} /> : null}
      {ymId ? <YandexMetrika counterId={ymId} /> : null}
    </>
  );
}
