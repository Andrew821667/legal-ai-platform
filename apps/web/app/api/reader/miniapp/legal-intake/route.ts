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

const clientTypes = new Set(["company", "entrepreneur", "individual", "unknown"]);
const legalAreas = new Set([
  "contracts", "disputes", "corporate", "employment", "tax_compliance",
  "real_estate", "it_ip_data", "family_inheritance", "debt_bankruptcy", "other",
]);
const urgencyLevels = new Set(["urgent", "high", "normal", "no_deadline"]);

type IntakeBody = {
  telegram_user_id?: number | string;
  name?: string;
  contact?: string;
  company?: string;
  client_type?: string;
  legal_area?: string;
  description?: string;
  urgency?: string;
  deadline?: string;
  region?: string;
  consentAccepted?: boolean;
};

function clean(input: unknown, maxLen: number): string | undefined {
  if (typeof input !== "string") return undefined;
  const value = input.trim();
  return value ? value.slice(0, maxLen) : undefined;
}

function choice(input: unknown, allowed: Set<string>, fallback: string): string {
  return typeof input === "string" && allowed.has(input) ? input : fallback;
}

function parseCoreError(raw: string): string {
  try {
    const data = raw ? (JSON.parse(raw) as { detail?: unknown }) : {};
    if (typeof data.detail === "string") return data.detail;
    if (data.detail) return JSON.stringify(data.detail);
  } catch {
    // Keep plain-text errors from core.
  }
  return raw || "Core API request failed";
}

export async function POST(request: NextRequest) {
  if (!CORE_API_BOT_KEY) {
    return NextResponse.json({ detail: "Core API key is not configured" }, { status: 500 });
  }
  const auth = verifyMiniAppRequest(request);
  if (auth instanceof NextResponse) return auth;

  let payload: IntakeBody;
  try {
    payload = (await request.json()) as IntakeBody;
  } catch {
    return NextResponse.json({ detail: "Некорректный JSON" }, { status: 400 });
  }

  const contact = clean(payload.contact, 255);
  const description = clean(payload.description, 4000);
  if (!contact) return NextResponse.json({ detail: "Укажите контакт для связи." }, { status: 400 });
  if (!description || description.length < 20) {
    return NextResponse.json({ detail: "Опишите задачу хотя бы в нескольких предложениях." }, { status: 400 });
  }
  if (payload.consentAccepted !== true) {
    return NextResponse.json({ detail: "Нужно согласие на обработку персональных данных." }, { status: 400 });
  }

  const requestedId = Number(payload.telegram_user_id);
  const telegramUserId = auth.verifiedTelegramUserId;
  if (telegramUserId === null) {
    return NextResponse.json({ detail: "Не удалось подтвердить пользователя Telegram." }, { status: 401 });
  }
  if (Number.isFinite(requestedId) && requestedId > 0 && requestedId !== telegramUserId) {
    return NextResponse.json({ detail: "Telegram user mismatch" }, { status: 403 });
  }

  const consentAt = new Date().toISOString();
  const contactKey = crypto.createHash("sha256").update(contact.toLowerCase()).digest("hex").slice(0, 16);
  const idempotencyKey = `miniapp-legal-${telegramUserId}-${contactKey}-${Date.now()}`;

  const userResponse = await fetch(`${CORE_API_URL}/api/v1/users`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": CORE_API_BOT_KEY,
      "Idempotency-Key": `${idempotencyKey}:user`,
    },
    body: JSON.stringify({
      telegram_id: telegramUserId,
      name: clean(payload.name, 120),
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

  const response = await fetch(`${CORE_API_URL}/api/v1/legal-intakes`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": CORE_API_BOT_KEY,
      "Idempotency-Key": idempotencyKey,
    },
    body: JSON.stringify({
      source: "miniapp_form",
      telegram_user_id: telegramUserId,
      name: clean(payload.name, 120),
      contact,
      company: clean(payload.company, 255),
      client_type: choice(payload.client_type, clientTypes, "unknown"),
      legal_area: choice(payload.legal_area, legalAreas, "other"),
      description,
      urgency: choice(payload.urgency, urgencyLevels, "no_deadline"),
      deadline: clean(payload.deadline, 255),
      region: clean(payload.region, 255),
      source_context: "miniapp_legal_help",
      consent_accepted: true,
      consent_version: "miniapp_legal_intake_v1",
      consent_at: consentAt,
      notes: "telegram_verified=1",
      utm_source: "miniapp",
      utm_medium: "telegram",
    }),
    cache: "no-store",
  });
  const raw = await response.text();
  if (!response.ok) {
    return NextResponse.json({ detail: parseCoreError(raw) }, { status: response.status });
  }

  const data = raw ? JSON.parse(raw) : {};
  return NextResponse.json({
    ok: true,
    intake_id: data.id,
    status: data.status,
    message: "Обращение принято. Юрист свяжется с вами после первичного рассмотрения.",
  });
}
