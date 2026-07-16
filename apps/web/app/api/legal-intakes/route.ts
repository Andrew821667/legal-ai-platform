import crypto from "node:crypto";
import { NextRequest, NextResponse } from "next/server";

import {
  evaluateLeadSubmission,
  getLeadSecurityConfig,
  normalizeLeadContact,
  recordLeadAttempt,
  rememberAcceptedLeadFingerprint,
  resolveLeadClientIp,
  verifyTurnstileToken,
} from "@/lib/lead-security";

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
  "contracts",
  "disputes",
  "corporate",
  "employment",
  "tax_compliance",
  "real_estate",
  "it_ip_data",
  "family_inheritance",
  "debt_bankruptcy",
  "other",
]);
const urgencyLevels = new Set(["urgent", "high", "normal", "no_deadline"]);

type IntakeBody = {
  name?: string;
  contact?: string;
  company?: string;
  client_type?: string;
  legal_area?: string;
  description?: string;
  urgency?: string;
  deadline?: string;
  region?: string;
  source_context?: string;
  consentAccepted?: boolean;
  utm_source?: string;
  utm_medium?: string;
  utm_campaign?: string;
  utm_content?: string;
  utm_term?: string;
  landing_page?: string;
  turnstile_token?: string;
  _started_at_ms?: number | string;
  [key: string]: unknown;
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
    // Keep the original response when core returned plain text.
  }
  return raw || "Core API request failed";
}

export async function POST(request: NextRequest) {
  if (!CORE_API_BOT_KEY) {
    return NextResponse.json({ detail: "Core API key is not configured" }, { status: 500 });
  }

  let payload: IntakeBody;
  try {
    payload = (await request.json()) as IntakeBody;
  } catch {
    return NextResponse.json({ detail: "Некорректный JSON" }, { status: 400 });
  }

  const contact = clean(payload.contact, 255);
  const description = clean(payload.description, 4000);
  if (!contact) {
    return NextResponse.json({ detail: "Укажите контакт для связи." }, { status: 400 });
  }
  if (!description || description.length < 20) {
    return NextResponse.json({ detail: "Опишите задачу хотя бы в нескольких предложениях." }, { status: 400 });
  }
  if (payload.consentAccepted !== true) {
    return NextResponse.json({ detail: "Нужно согласие на обработку персональных данных." }, { status: 400 });
  }

  const cfg = getLeadSecurityConfig();
  const normalizedContact = normalizeLeadContact(contact);
  const ip = resolveLeadClientIp(request.headers);
  const userAgent = request.headers.get("user-agent") || "unknown";
  const nowMs = Date.now();
  const protection = evaluateLeadSubmission(
    { payload: payload as Record<string, unknown>, normalizedContact, ip, userAgent, nowMs },
    cfg,
  );
  recordLeadAttempt(protection, cfg, nowMs);

  if (protection.action === "silent_drop" || protection.action === "duplicate") {
    return NextResponse.json({
      ok: true,
      deduped: protection.action === "duplicate",
      message: "Обращение принято. Мы свяжемся после первичного рассмотрения задачи.",
    });
  }
  if (protection.action === "rate_limit") {
    return NextResponse.json({ detail: protection.detail }, { status: protection.status });
  }
  if (protection.requiresChallenge) {
    const token = clean(payload.turnstile_token, 2048) || "";
    if (!cfg.turnstileSecretKey) {
      return NextResponse.json({ detail: "Проверка формы временно недоступна." }, { status: 500 });
    }
    if (!(await verifyTurnstileToken(token, ip, cfg.turnstileSecretKey))) {
      return NextResponse.json(
        { detail: "Подтвердите, что обращение отправляет человек.", challenge_required: true },
        { status: 403 },
      );
    }
  }

  const consentAt = new Date().toISOString();
  const landing = clean(payload.landing_page, 512) || request.nextUrl.pathname;
  const ipHash = crypto.createHash("sha256").update(ip).digest("hex").slice(0, 12);
  const uaHash = crypto.createHash("sha256").update(userAgent).digest("hex").slice(0, 12);
  const notes = `ip_hash=${ipHash}\nua_hash=${uaHash}`;

  const coreResponse = await fetch(`${CORE_API_URL}/api/v1/legal-intakes`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": CORE_API_BOT_KEY,
      "Idempotency-Key": protection.idempotencyKey,
    },
    body: JSON.stringify({
      source: "website_form",
      name: clean(payload.name, 120),
      contact,
      company: clean(payload.company, 255),
      client_type: choice(payload.client_type, clientTypes, "unknown"),
      legal_area: choice(payload.legal_area, legalAreas, "other"),
      description,
      urgency: choice(payload.urgency, urgencyLevels, "no_deadline"),
      deadline: clean(payload.deadline, 255),
      region: clean(payload.region, 255),
      source_context: clean(payload.source_context, 255) || landing,
      consent_accepted: true,
      consent_version: "website_legal_intake_v1",
      consent_at: consentAt,
      notes,
      utm_source: clean(payload.utm_source, 255),
      utm_medium: clean(payload.utm_medium, 255),
      utm_campaign: clean(payload.utm_campaign, 255),
      utm_content: clean(payload.utm_content, 255),
      utm_term: clean(payload.utm_term, 255),
    }),
    cache: "no-store",
  });
  const raw = await coreResponse.text();
  if (!coreResponse.ok) {
    return NextResponse.json({ detail: parseCoreError(raw) }, { status: coreResponse.status });
  }

  rememberAcceptedLeadFingerprint(protection.fingerprint, nowMs);
  const data = raw ? JSON.parse(raw) : {};
  return NextResponse.json({
    ok: true,
    intake_id: data.id,
    status: data.status,
    message: "Обращение принято. Юрист изучит описание и свяжется с вами для уточнения задачи.",
  });
}
