import crypto from "node:crypto";
import { NextRequest, NextResponse } from "next/server";

import { isTrustedAssistantOrigin, trustedHostsFor } from "@/lib/assistant-security";
import { CLIENT_SESSION_COOKIE, clientSessionSecret, verifyClientSessionToken } from "@/lib/client-session";
import { cabinetLeadFields, cabinetNoteTags, cabinetSourceContext, type CabinetLeadSession } from "@/lib/lead-cabinet";
import {
  evaluateLeadSubmission,
  getLeadSecurityConfig,
  normalizeLeadContact,
  recordLeadAttempt,
  rememberAcceptedLeadFingerprint,
  resolveLeadClientIp,
  verifyTurnstileToken,
} from "@/lib/lead-security";
import { addStarterOfferToMessage, getStarterOffer } from "@/lib/starter-offers";

const CORE_API_URL =
  process.env.CORE_API_URL || process.env.NEXT_PUBLIC_CORE_API_URL || "http://127.0.0.1:8000";
const CORE_API_BOT_KEY =
  process.env.CORE_API_BOT_KEY ||
  process.env.API_KEY_BOT ||
  process.env.CORE_API_ADMIN_KEY ||
  process.env.API_KEY_ADMIN ||
  "";

type LeadSegment = "inhouse" | "law_firm" | "entrepreneur" | "other";
type LeadOffer = "consultation" | "checklist" | "demo" | "sample_report" | "unknown";

interface LeadRequestBody {
  name?: string;
  contact?: string;
  consentAccepted?: boolean;
  segment?: LeadSegment;
  message?: string;
  offer?: LeadOffer;
  practice?: "legal" | "engineering" | "hybrid";
  starter_offer_id?: string;
  utm_source?: string;
  utm_medium?: string;
  utm_campaign?: string;
  utm_content?: string;
  utm_term?: string;
  landing_page?: string;
  turnstile_token?: string;
  _started_at_ms?: number | string;
  _honeypot?: string;
  [key: string]: unknown;
}

function clean(input: unknown, maxLen = 512): string | undefined {
  if (typeof input !== "string") return undefined;
  const value = input.trim();
  if (!value) return undefined;
  return value.slice(0, maxLen);
}

function toSegment(input: unknown): LeadSegment {
  if (input === "inhouse" || input === "law_firm" || input === "entrepreneur") {
    return input;
  }
  return "other";
}

function toOffer(input: unknown): LeadOffer {
  if (input === "consultation" || input === "checklist" || input === "demo" || input === "sample_report") {
    return input;
  }
  return "unknown";
}

function parseCoreError(raw: string): string {
  try {
    const parsed = raw ? (JSON.parse(raw) as { detail?: unknown }) : {};
    if (typeof parsed.detail === "string") return parsed.detail;
    if (parsed.detail) return JSON.stringify(parsed.detail);
  } catch {
    // ignore parse errors
  }
  return raw || "Core API request failed";
}

export async function POST(request: NextRequest) {
  const securityConfig = getLeadSecurityConfig();

  if (!CORE_API_BOT_KEY) {
    return NextResponse.json(
      { detail: "CORE_API_BOT_KEY/API_KEY_BOT is not configured on web server" },
      { status: 500 },
    );
  }

  // Личный кабинет (/cabinet) шлёт эту же форму залогиненным — сервер сам
  // достаёт telegram_user_id из куки, клиент его не передаёт (иначе можно
  // было бы приписать заявку чужому аккаунту). Анонимная форма на обычных
  // страницах сайта куки не имеет — session остаётся null, и весь путь ниже
  // не меняется по сравнению с тем, что было.
  const clientSecret = clientSessionSecret();
  const session: CabinetLeadSession = clientSecret
    ? verifyClientSessionToken(request.cookies.get(CLIENT_SESSION_COOKIE)?.value || "", clientSecret)
    : null;
  if (session) {
    // SameSite=Lax уже не отправляет эту куку на cross-site form-POST;
    // Origin-проверка — независимый от браузера второй слой, применяем её
    // только когда кука вообще есть, не трогая анонимный путь.
    if (!isTrustedAssistantOrigin(request.headers.get("origin"), trustedHostsFor(request))) {
      return NextResponse.json({ detail: "Недопустимый источник запроса" }, { status: 403 });
    }
  }

  let payload: LeadRequestBody;
  try {
    payload = (await request.json()) as LeadRequestBody;
  } catch {
    return NextResponse.json({ detail: "Некорректный JSON" }, { status: 400 });
  }

  const name = clean(payload.name, 120);
  const contact = clean(payload.contact, 180);
  const message = clean(payload.message, 4000);
  const starterOffer = getStarterOffer(payload.starter_offer_id, "engineering");
  const messageWithOffer = addStarterOfferToMessage(
    message || "",
    starterOffer?.id,
    "engineering",
  ).slice(0, 4000);
  const offer = toOffer(payload.offer);
  const segment = toSegment(payload.segment);
  const isCase = offer === "consultation" || offer === "unknown";
  const practice = payload.practice || "hybrid";
  if (isCase && !["legal", "engineering", "hybrid"].includes(practice)) {
    return NextResponse.json({ detail: "Выберите направление задачи." }, { status: 400 });
  }
  if (isCase && (!message || message.length < 20)) {
    return NextResponse.json({ detail: "Кратко опишите задачу, не менее 20 символов." }, { status: 400 });
  }
  const turnstileToken = clean(payload.turnstile_token, 2048) || "";

  if (!contact) {
    return NextResponse.json(
      { detail: "Укажите контакт: email, телефон или Telegram" },
      { status: 400 },
    );
  }
  if (payload.consentAccepted !== true) {
    return NextResponse.json(
      { detail: "Нужно согласие на обработку персональных данных." },
      { status: 400 },
    );
  }

  const normalizedContact = normalizeLeadContact(contact);
  const ip = resolveLeadClientIp(request.headers);
  const userAgent = request.headers.get("user-agent") || "unknown";
  const landingPage = clean(payload.landing_page, 512);
  const utmSource = clean(payload.utm_source, 255);
  const utmMedium = clean(payload.utm_medium, 255);
  const utmCampaign = clean(payload.utm_campaign, 255);
  const utmContent = clean(payload.utm_content, 255);
  const utmTerm = clean(payload.utm_term, 255);
  const nowMs = Date.now();

  const leadProtection = evaluateLeadSubmission(
    {
      payload: payload as Record<string, unknown>,
      normalizedContact,
      ip,
      userAgent,
      nowMs,
    },
    securityConfig,
  );

  recordLeadAttempt(leadProtection, securityConfig, nowMs);

  if (leadProtection.action === "silent_drop" || leadProtection.action === "duplicate") {
    return NextResponse.json(
      {
        ok: true,
        deduped: leadProtection.action === "duplicate",
        message: leadProtection.detail,
      },
      { status: 200 },
    );
  }

  if (leadProtection.action === "rate_limit") {
    return NextResponse.json(
      {
        detail: leadProtection.detail,
        reason_codes: leadProtection.reasonCodes,
      },
      { status: leadProtection.status },
    );
  }

  if (leadProtection.requiresChallenge) {
    if (!securityConfig.turnstileSecretKey) {
      return NextResponse.json(
        { detail: "Challenge protection is not configured on server" },
        { status: 500 },
      );
    }

    const isTurnstileValid = await verifyTurnstileToken(turnstileToken, ip, securityConfig.turnstileSecretKey);
    if (!isTurnstileValid) {
      return NextResponse.json(
        {
          detail: "Нужна дополнительная проверка формы. Подтвердите, что вы не бот, и отправьте заявку снова.",
          challenge_required: true,
          reason_codes: leadProtection.reasonCodes,
        },
        { status: 403 },
      );
    }
  }

  const ipHash = crypto.createHash("sha256").update(ip).digest("hex").slice(0, 12);
  const userAgentHash = crypto.createHash("sha256").update(userAgent).digest("hex").slice(0, 12);
  const consentAt = new Date().toISOString();
  const notesParts = [
    `offer=${offer}`,
    starterOffer ? `starter_offer=${starterOffer.id}` : undefined,
    "consent=accepted",
    "consent_version=website_pdn_transborder_v1",
    `consent_at=${consentAt}`,
    "transborder_consent=accepted",
    `ip_hash=${ipHash}`,
    `ua_hash=${userAgentHash}`,
    landingPage ? `landing=${landingPage}` : undefined,
    messageWithOffer ? `message=${messageWithOffer}` : undefined,
    leadProtection.reasonCodes.length > 0 ? `security_flags=${leadProtection.reasonCodes.join(",")}` : undefined,
    ...cabinetNoteTags(session),
  ].filter(Boolean);

  const corePayload = {
    source: "website_form",
    name,
    contact,
    segment,
    notes: notesParts.join("\n"),
    utm_source: utmSource,
    utm_medium: utmMedium,
    utm_campaign: utmCampaign,
    utm_content: utmContent,
    utm_term: utmTerm,
    ...cabinetLeadFields(session),
  };

  const casePayload = {
    ...corePayload,
    notes: corePayload.notes.slice(0, 4000),
    practice,
    category: practice === "legal" ? null : "other",
    legal_area: "other",
    client_type: segment === "entrepreneur" ? "entrepreneur" : segment === "other" ? "unknown" : "company",
    description: messageWithOffer,
    source_context: cabinetSourceContext(session, (landingPage || "/").slice(0, 255)),
    consent_accepted: true,
    consent_version: "website_pdn_transborder_v1",
    consent_at: consentAt,
  };
  const response = await fetch(`${CORE_API_URL}/api/v1/${isCase ? "legal-intakes" : "leads"}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": CORE_API_BOT_KEY,
      "Idempotency-Key": leadProtection.idempotencyKey,
    },
    body: JSON.stringify(isCase ? casePayload : corePayload),
    cache: "no-store",
    signal: AbortSignal.timeout(15000),
  });

  const raw = await response.text();
  if (!response.ok) {
    return NextResponse.json({ detail: parseCoreError(raw) }, { status: response.status });
  }

  rememberAcceptedLeadFingerprint(leadProtection.fingerprint, nowMs);
  const data = raw ? JSON.parse(raw) : {};
  return NextResponse.json(
    {
      ok: true,
      lead_id: isCase ? data.lead_id : data.id,
      intake_id: isCase ? data.id : undefined,
      status: data.status,
      message: "Заявка принята. Мы свяжемся с вами в ближайшее время.",
    },
    { status: 200 },
  );
}
