import crypto from "node:crypto";
import { NextRequest, NextResponse } from "next/server";

import { verifyMiniAppRequest } from "@/lib/telegram-webapp-auth";

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

interface MiniAppLeadBody {
  telegram_user_id?: number | string;
  name?: string;
  contact?: string;
  consentAccepted?: boolean;
  segment?: LeadSegment;
  message?: string;
  offer?: LeadOffer;
  audience?: string;
  goal?: string;
  utm_source?: string;
  utm_medium?: string;
  utm_campaign?: string;
  utm_content?: string;
  utm_term?: string;
  landing_page?: string;
  [key: string]: unknown;
}

function clean(input: unknown, maxLen: number): string | undefined {
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
  if (
    input === "consultation" ||
    input === "checklist" ||
    input === "demo" ||
    input === "sample_report"
  ) {
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
    // ignore
  }
  return raw || "Core API request failed";
}

export async function POST(request: NextRequest) {
  if (!CORE_API_BOT_KEY) {
    return NextResponse.json(
      { detail: "CORE_API_BOT_KEY/API_KEY_BOT is not configured on web server" },
      { status: 500 },
    );
  }

  const auth = verifyMiniAppRequest(request);
  if (auth instanceof NextResponse) {
    return auth;
  }

  let payload: MiniAppLeadBody;
  try {
    payload = (await request.json()) as MiniAppLeadBody;
  } catch {
    return NextResponse.json({ detail: "Некорректный JSON" }, { status: 400 });
  }

  const contact = clean(payload.contact, 180);
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

  const requestedTelegramUserId = Number(payload.telegram_user_id);
  const telegramUserId =
    auth.verifiedTelegramUserId ??
    (Number.isFinite(requestedTelegramUserId) && requestedTelegramUserId > 0
      ? requestedTelegramUserId
      : null);
  if (
    auth.verifiedTelegramUserId !== null &&
    Number.isFinite(requestedTelegramUserId) &&
    requestedTelegramUserId > 0 &&
    requestedTelegramUserId !== auth.verifiedTelegramUserId
  ) {
    return NextResponse.json(
      { detail: "telegram_user_id does not match verified Telegram user" },
      { status: 403 },
    );
  }

  const name = clean(payload.name, 120);
  const message = clean(payload.message, 4000);
  const offer = toOffer(payload.offer);
  const segment = toSegment(payload.segment);
  const audience = clean(payload.audience, 32);
  const goal = clean(payload.goal, 255);
  const landingPage = clean(payload.landing_page, 512);
  const utmSource = clean(payload.utm_source, 255);
  const utmMedium = clean(payload.utm_medium, 255);
  const utmCampaign = clean(payload.utm_campaign, 255);
  const utmContent = clean(payload.utm_content, 255);
  const utmTerm = clean(payload.utm_term, 255);
  const consentAt = new Date().toISOString();

  const notesParts = [
    `offer=${offer}`,
    "consent=accepted",
    "consent_version=miniapp_pdn_v1",
    `consent_at=${consentAt}`,
    telegramUserId ? `telegram_user_id=${telegramUserId}` : undefined,
    auth.verifiedTelegramUserId
      ? `telegram_verified=1`
      : `telegram_verified=0`,
    audience ? `audience=${audience}` : undefined,
    goal ? `goal=${goal}` : undefined,
    landingPage ? `landing=${landingPage}` : undefined,
    message ? `message=${message}` : undefined,
  ].filter(Boolean);

  const corePayload = {
    source: "miniapp_form",
    name,
    contact,
    segment,
    telegram_user_id: telegramUserId,
    notes: notesParts.join("\n"),
    utm_source: utmSource || "miniapp",
    utm_medium: utmMedium || "telegram",
    utm_campaign: utmCampaign,
    utm_content: utmContent,
    utm_term: utmTerm,
  };

  const idempotencyKey = crypto
    .createHash("sha256")
    .update(`${telegramUserId || "anon"}|${contact}|${offer}|${Date.now()}`)
    .digest("hex")
    .slice(0, 32);

  if (auth.verifiedTelegramUserId !== null) {
    const userResponse = await fetch(`${CORE_API_URL}/api/v1/users`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-API-Key": CORE_API_BOT_KEY,
        "Idempotency-Key": `${idempotencyKey}:user`,
      },
      body: JSON.stringify({
        telegram_id: auth.verifiedTelegramUserId,
        name,
        consent_given: true,
        consent_date: consentAt,
        consent_revoked: false,
        last_interaction: consentAt,
      }),
      cache: "no-store",
    });
    const userRaw = await userResponse.text();
    if (!userResponse.ok) {
      return NextResponse.json({ detail: parseCoreError(userRaw) }, { status: userResponse.status });
    }
  }

  const response = await fetch(`${CORE_API_URL}/api/v1/leads`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": CORE_API_BOT_KEY,
      "Idempotency-Key": idempotencyKey,
    },
    body: JSON.stringify(corePayload),
    cache: "no-store",
  });

  const raw = await response.text();
  if (!response.ok) {
    return NextResponse.json({ detail: parseCoreError(raw) }, { status: response.status });
  }

  const data = raw ? JSON.parse(raw) : {};
  return NextResponse.json(
    {
      ok: true,
      lead_id: data.id,
      status: data.status,
      message: "Заявка принята. Мы свяжемся с вами в ближайшее время.",
    },
    { status: 200 },
  );
}
