import crypto from "node:crypto";
import { NextRequest, NextResponse } from "next/server";

const CORE_API_URL =
  process.env.CORE_API_URL || process.env.NEXT_PUBLIC_CORE_API_URL || "http://127.0.0.1:8000";
const CORE_API_BOT_KEY =
  process.env.CORE_API_BOT_KEY ||
  process.env.API_KEY_BOT ||
  process.env.CORE_API_ADMIN_KEY ||
  process.env.API_KEY_ADMIN ||
  "";

type LeadSegment = "inhouse" | "law_firm" | "entrepreneur" | "other";
type LeadOffer = "consultation" | "checklist" | "demo" | "unknown";

interface LeadRequestBody {
  name?: string;
  contact?: string;
  segment?: LeadSegment;
  message?: string;
  offer?: LeadOffer;
  utm_source?: string;
  utm_medium?: string;
  utm_campaign?: string;
  utm_content?: string;
  utm_term?: string;
  landing_page?: string;
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
  if (input === "consultation" || input === "checklist" || input === "demo") {
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
  if (!CORE_API_BOT_KEY) {
    return NextResponse.json(
      { detail: "CORE_API_BOT_KEY/API_KEY_BOT is not configured on web server" },
      { status: 500 },
    );
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
  const offer = toOffer(payload.offer);
  const segment = toSegment(payload.segment);

  if (!contact) {
    return NextResponse.json(
      { detail: "Укажите контакт: email, телефон или Telegram" },
      { status: 400 },
    );
  }

  const ip =
    request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ||
    request.headers.get("x-real-ip") ||
    "unknown";
  const userAgent = request.headers.get("user-agent") || "unknown";
  const landingPage = clean(payload.landing_page, 512);

  const notesParts = [
    `offer=${offer}`,
    `ip=${ip}`,
    `ua=${userAgent}`,
    landingPage ? `landing=${landingPage}` : undefined,
    message ? `message=${message}` : undefined,
  ].filter(Boolean);

  const day = new Date().toISOString().slice(0, 10);
  const idempotencyKey = `web-lead-${crypto
    .createHash("sha256")
    .update(`${contact}:${offer}:${day}`)
    .digest("hex")
    .slice(0, 48)}`;

  const corePayload = {
    source: "website_form",
    name,
    contact,
    segment,
    notes: notesParts.join("\n"),
    utm_source: clean(payload.utm_source, 255),
    utm_medium: clean(payload.utm_medium, 255),
    utm_campaign: clean(payload.utm_campaign, 255),
    utm_content: clean(payload.utm_content, 255),
    utm_term: clean(payload.utm_term, 255),
  };

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
