export type LeadAttribution = {
  utm_source?: string;
  utm_medium?: string;
  utm_campaign?: string;
  utm_content?: string;
  utm_term?: string;
  landing_page?: string;
};

declare global {
  interface Window {
    gtag?: (...args: unknown[]) => void;
    ym?: (...args: unknown[]) => void;
  }
}

const STORAGE_KEY = "ai-verdict:first-touch";
const ATTR_PARAMS = [
  "utm_source",
  "utm_medium",
  "utm_campaign",
  "utm_content",
  "utm_term",
  "gclid",
  "yclid",
  "msclkid",
] as const;

function searchSource(host: string): string | undefined {
  if (/(^|\.)google\./.test(host)) return "google";
  if (/(^|\.)yandex\./.test(host)) return "yandex";
  if (/(^|\.)bing\.com$/.test(host)) return "bing";
  if (/(^|\.)search\.yahoo\./.test(host)) return "yahoo";
  if (/(^|\.)duckduckgo\.com$/.test(host)) return "duckduckgo";
  if (host === "go.mail.ru") return "mail.ru";
  if (/(^|\.)rambler\.ru$/.test(host)) return "rambler";
  return undefined;
}

function landingPath(url: URL): string {
  const params = new URLSearchParams();
  for (const key of ATTR_PARAMS) {
    const value = url.searchParams.get(key);
    if (value) params.set(key, value);
  }
  const query = params.toString();
  return `${url.pathname}${query ? `?${query}` : ""}`;
}

export function buildLeadAttribution(href: string, referrer = ""): LeadAttribution {
  const url = new URL(href);
  const data: LeadAttribution = {
    utm_source: url.searchParams.get("utm_source") || undefined,
    utm_medium: url.searchParams.get("utm_medium") || undefined,
    utm_campaign: url.searchParams.get("utm_campaign") || undefined,
    utm_content: url.searchParams.get("utm_content") || undefined,
    utm_term: url.searchParams.get("utm_term") || undefined,
    landing_page: landingPath(url),
  };

  if (data.utm_source || !referrer) return data;

  try {
    const ref = new URL(referrer);
    if (ref.origin === url.origin) return data;
    const host = ref.hostname.toLowerCase().replace(/^www\./, "");
    const source = searchSource(host);
    data.utm_source = source || host;
    data.utm_medium = source ? "organic" : "referral";
  } catch {
    // A malformed referrer must not prevent the lead form from working.
  }

  return data;
}

export function getLeadAttribution(): LeadAttribution {
  if (typeof window === "undefined") return {};

  try {
    const saved = window.sessionStorage.getItem(STORAGE_KEY);
    if (saved) return JSON.parse(saved) as LeadAttribution;
  } catch {
    // Continue without persistence when storage is unavailable.
  }

  const data = buildLeadAttribution(window.location.href, document.referrer);
  try {
    window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(data));
  } catch {
    // The current-page attribution is still useful without storage.
  }
  return data;
}

export function captureLeadAttribution(): void {
  getLeadAttribution();
}

export function trackLeadConversion(
  form: "general" | "legal_help",
  data: LeadAttribution,
): void {
  if (typeof window === "undefined") return;

  const params = {
    form,
    landing_page: data.landing_page,
    traffic_source: data.utm_source,
    traffic_medium: data.utm_medium,
  };

  window.gtag?.("event", "generate_lead", params);

  const rawId = process.env.NEXT_PUBLIC_YM_COUNTER_ID || "110733908";
  const counterId = Number(rawId);
  if (Number.isFinite(counterId)) {
    window.ym?.(counterId, "reachGoal", "lead_form_submit", params);
  }
}
