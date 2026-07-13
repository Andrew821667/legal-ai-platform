const FALLBACKS = {
  brand: "AI Verdict",
  operatorName: "Попов Андрей",
  operatorStatus: "самозанятый",
  siteUrl: "https://ai-verdict.ru",
  contactEmail: "a.popov.gv@gmail.com",
  contactPhone: "+7 909 233-09-09",
  contactTelegram: "@legal_ai_helper_new_bot",
  updatedAt: "13 июля 2026 года",
} as const;

function normalizeText(value: string | undefined): string | undefined {
  const trimmed = value?.trim();
  return trimmed ? trimmed : undefined;
}

function normalizeTelegramHandle(value: string): string {
  const trimmed = value.trim();
  if (!trimmed) {
    return FALLBACKS.contactTelegram;
  }
  return trimmed.startsWith("@") ? trimmed : `@${trimmed}`;
}

function normalizePhoneHref(value: string): string {
  const normalized = value.replace(/[^\d+]/g, "");
  return normalized.startsWith("+") ? normalized : `+${normalized}`;
}

const envOperatorName = normalizeText(process.env.NEXT_PUBLIC_OPERATOR_NAME);
const envOperatorStatus = normalizeText(process.env.NEXT_PUBLIC_OPERATOR_STATUS);
const envOperatorInn = normalizeText(process.env.NEXT_PUBLIC_OPERATOR_INN);
const envOperatorDetails = normalizeText(process.env.NEXT_PUBLIC_OPERATOR_DETAILS);
const envPrivacyContactEmail = normalizeText(process.env.NEXT_PUBLIC_PRIVACY_CONTACT_EMAIL);
const envContactPhone = normalizeText(process.env.NEXT_PUBLIC_CONTACT_PHONE);
const envContactTelegram = normalizeText(process.env.NEXT_PUBLIC_CONTACT_TELEGRAM);
const envSiteUrl = normalizeText(process.env.NEXT_PUBLIC_SITE_URL);

function publicSiteUrl(value: string | undefined): string {
  try {
    const url = new URL(value ?? FALLBACKS.siteUrl);
    const hostname = url.hostname.toLowerCase();
    if (["localhost", "127.0.0.1", "0.0.0.0", "::1"].includes(hostname)) {
      return FALLBACKS.siteUrl;
    }
    return url.origin;
  } catch {
    return FALLBACKS.siteUrl;
  }
}

export const LEGAL_BRAND = FALLBACKS.brand;
export const LEGAL_OPERATOR_NAME = envOperatorName ?? FALLBACKS.operatorName;
export const LEGAL_OPERATOR_STATUS = envOperatorStatus ?? FALLBACKS.operatorStatus;
export const LEGAL_OPERATOR_INN = envOperatorInn ?? "";
export const LEGAL_OPERATOR_DETAILS = envOperatorDetails ?? "";
export const LEGAL_SITE_URL = publicSiteUrl(envSiteUrl);
export const LEGAL_CONTACT_EMAIL = envPrivacyContactEmail ?? FALLBACKS.contactEmail;
export const LEGAL_CONTACT_PHONE = envContactPhone ?? FALLBACKS.contactPhone;
export const LEGAL_CONTACT_PHONE_HREF = normalizePhoneHref(LEGAL_CONTACT_PHONE);
export const LEGAL_CONTACT_TELEGRAM = normalizeTelegramHandle(envContactTelegram ?? FALLBACKS.contactTelegram);
export const LEGAL_CONTACT_TELEGRAM_URL = `https://t.me/${LEGAL_CONTACT_TELEGRAM.replace(/^@/, "")}`;
export const LEGAL_UPDATED_AT = FALLBACKS.updatedAt;
export const LEGAL_COPYRIGHT_YEAR = 2026;

const missingPublicDisclosureVars = [
  !envOperatorName && "NEXT_PUBLIC_OPERATOR_NAME",
  !envOperatorStatus && "NEXT_PUBLIC_OPERATOR_STATUS",
  !envPrivacyContactEmail && "NEXT_PUBLIC_PRIVACY_CONTACT_EMAIL",
  !envContactPhone && "NEXT_PUBLIC_CONTACT_PHONE",
  !envContactTelegram && "NEXT_PUBLIC_CONTACT_TELEGRAM",
  !envOperatorInn && "NEXT_PUBLIC_OPERATOR_INN",
  !envOperatorDetails && "NEXT_PUBLIC_OPERATOR_DETAILS",
].filter(Boolean) as string[];

let hasReportedWarnings = false;

export function reportLegalProfileWarnings(): void {
  if (typeof window !== "undefined" || hasReportedWarnings || missingPublicDisclosureVars.length === 0) {
    return;
  }

  console.warn(
    `[web-compliance] Missing public legal env vars: ${missingPublicDisclosureVars.join(
      ", ",
    )}. Web is using local fallback disclosure data until runtime env is filled.`,
  );
  hasReportedWarnings = true;
}

export const LEGAL_DOC_LINKS = {
  privacy: "/privacy",
  terms: "/terms",
  userAgreement: "/user-agreement",
  transborderConsent: "/transborder-consent",
  marketingConsent: "/marketing-consent",
  aiPolicy: "/ai-policy",
} as const;
