import crypto from "node:crypto";

export type LeadChallengeMode = "off" | "adaptive" | "always";

export interface LeadSecurityPayload {
  name?: string;
  contact?: string;
  segment?: string;
  message?: string;
  offer?: string;
  utm_source?: string;
  utm_medium?: string;
  utm_campaign?: string;
  utm_content?: string;
  utm_term?: string;
  landing_page?: string;
}

export interface LeadSecurityConfig {
  honeypotField: string;
  minSubmitSeconds: number;
  ipMaxAttempts: number;
  ipWindowSeconds: number;
  contactMaxAttempts: number;
  contactWindowSeconds: number;
  challengeMode: LeadChallengeMode;
  turnstileSecretKey: string;
}

export interface LeadEvaluationInput {
  payload: Record<string, unknown>;
  normalizedContact: string;
  ip: string;
  userAgent: string;
  nowMs?: number;
}

export interface LeadEvaluationResult {
  action: "accept" | "silent_drop" | "rate_limit" | "duplicate";
  detail: string;
  status: number;
  reasonCodes: string[];
  riskScore: number;
  fingerprint: string;
  idempotencyKey: string;
  dayKey: string;
  ipKey: string;
  contactKey: string;
  requiresChallenge: boolean;
}

const DEFAULT_HONEYPOT_FIELD = "company_website";
const DEFAULT_MIN_SUBMIT_SECONDS = 4;
const DEFAULT_IP_MAX_ATTEMPTS = 6;
const DEFAULT_IP_WINDOW_SECONDS = 10 * 60;
const DEFAULT_CONTACT_MAX_ATTEMPTS = 3;
const DEFAULT_CONTACT_WINDOW_SECONDS = 24 * 60 * 60;

const ipAttemptStore = new Map<string, number[]>();
const contactAttemptStore = new Map<string, number[]>();
const acceptedFingerprintStore = new Map<string, number>();

function parsePositiveInt(raw: string | undefined, fallback: number): number {
  const parsed = Number(raw || "");
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return fallback;
  }
  return Math.round(parsed);
}

function parseChallengeMode(raw: string | undefined): LeadChallengeMode {
  const value = String(raw || "").trim().toLowerCase();
  if (value === "always") {
    return "always";
  }
  if (value === "adaptive") {
    return "adaptive";
  }
  return "off";
}

export function getLeadSecurityConfig(): LeadSecurityConfig {
  return {
    honeypotField: (process.env.LEAD_FORM_HONEYPOT_FIELD || DEFAULT_HONEYPOT_FIELD).trim() || DEFAULT_HONEYPOT_FIELD,
    minSubmitSeconds: parsePositiveInt(process.env.LEAD_FORM_MIN_SUBMIT_SECONDS, DEFAULT_MIN_SUBMIT_SECONDS),
    ipMaxAttempts: parsePositiveInt(process.env.LEAD_FORM_IP_MAX_ATTEMPTS, DEFAULT_IP_MAX_ATTEMPTS),
    ipWindowSeconds: parsePositiveInt(process.env.LEAD_FORM_IP_WINDOW_SECONDS, DEFAULT_IP_WINDOW_SECONDS),
    contactMaxAttempts: parsePositiveInt(process.env.LEAD_FORM_CONTACT_MAX_ATTEMPTS, DEFAULT_CONTACT_MAX_ATTEMPTS),
    contactWindowSeconds: parsePositiveInt(process.env.LEAD_FORM_CONTACT_WINDOW_SECONDS, DEFAULT_CONTACT_WINDOW_SECONDS),
    challengeMode: parseChallengeMode(process.env.LEAD_FORM_CHALLENGE_MODE),
    turnstileSecretKey: (process.env.TURNSTILE_SECRET_KEY || "").trim(),
  };
}

export function getLeadHoneypotFieldName(): string {
  return (
    process.env.NEXT_PUBLIC_LEAD_FORM_HONEYPOT_FIELD
    || process.env.LEAD_FORM_HONEYPOT_FIELD
    || DEFAULT_HONEYPOT_FIELD
  ).trim() || DEFAULT_HONEYPOT_FIELD;
}

export function getLeadPublicChallengeMode(): LeadChallengeMode {
  return parseChallengeMode(process.env.NEXT_PUBLIC_LEAD_FORM_CHALLENGE_MODE || process.env.LEAD_FORM_CHALLENGE_MODE);
}

export function getTurnstileSiteKey(): string {
  return (process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY || "").trim();
}

export function resolveLeadClientIp(headers: Headers): string {
  return (
    headers.get("x-forwarded-for")?.split(",")[0]?.trim()
    || headers.get("x-real-ip")
    || "unknown"
  );
}

export function normalizeLeadContact(input: string): string {
  return input.trim().toLowerCase().replace(/\s+/g, " ");
}

function cleanFingerprintValue(input: unknown, maxLen: number): string {
  if (typeof input !== "string") {
    return "";
  }
  return input.trim().slice(0, maxLen);
}

function hashKey(value: string): string {
  return crypto.createHash("sha256").update(value).digest("hex");
}

function pruneBucket(store: Map<string, number[]>, key: string, nowMs: number, windowMs: number): number[] {
  const rows = store.get(key) || [];
  const nextRows = rows.filter((ts) => nowMs - ts <= windowMs);
  if (nextRows.length > 0) {
    store.set(key, nextRows);
  } else {
    store.delete(key);
  }
  return nextRows;
}

function rememberAttempt(store: Map<string, number[]>, key: string, nowMs: number, windowMs: number): number {
  const rows = pruneBucket(store, key, nowMs, windowMs);
  rows.push(nowMs);
  store.set(key, rows);
  return rows.length;
}

function countAttempts(store: Map<string, number[]>, key: string, nowMs: number, windowMs: number): number {
  return pruneBucket(store, key, nowMs, windowMs).length;
}

function pruneAcceptedFingerprints(nowMs: number): void {
  const ttlMs = 24 * 60 * 60 * 1000;
  for (const [fingerprint, storedAtMs] of acceptedFingerprintStore) {
    if (nowMs - storedAtMs > ttlMs) {
      acceptedFingerprintStore.delete(fingerprint);
    }
  }
}

export function buildLeadFingerprint(
  payload: LeadSecurityPayload,
  normalizedContact: string,
  dayKey: string,
): string {
  return hashKey(
    JSON.stringify({
      day: dayKey,
      contact: normalizedContact,
      offer: cleanFingerprintValue(payload.offer, 40),
      segment: cleanFingerprintValue(payload.segment, 40),
      name: cleanFingerprintValue(payload.name, 120),
      message: cleanFingerprintValue(payload.message, 4000),
      landing_page: cleanFingerprintValue(payload.landing_page, 512),
      utm_source: cleanFingerprintValue(payload.utm_source, 255),
      utm_medium: cleanFingerprintValue(payload.utm_medium, 255),
      utm_campaign: cleanFingerprintValue(payload.utm_campaign, 255),
      utm_content: cleanFingerprintValue(payload.utm_content, 255),
      utm_term: cleanFingerprintValue(payload.utm_term, 255),
    }),
  ).slice(0, 48);
}

export function buildLeadIdempotencyKey(dayKey: string, fingerprint: string): string {
  return `web-lead-${hashKey(`${dayKey}:${fingerprint}`).slice(0, 48)}`;
}

function extractHoneypotValue(payload: Record<string, unknown>, fieldName: string): string {
  const direct = payload[fieldName];
  if (typeof direct === "string") {
    return direct.trim();
  }
  const fallback = payload._honeypot;
  if (typeof fallback === "string") {
    return fallback.trim();
  }
  return "";
}

function parseStartedAtMs(payload: Record<string, unknown>): number | null {
  const raw = payload._started_at_ms;
  const parsed = Number(typeof raw === "string" ? raw : raw ?? "");
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return null;
  }
  return Math.round(parsed);
}

function computeRiskScore(input: {
  startedAtMs: number | null;
  nowMs: number;
  userAgent: string;
  currentIpAttempts: number;
  currentContactAttempts: number;
  config: LeadSecurityConfig;
}): { riskScore: number; reasonCodes: string[] } {
  const reasons: string[] = [];
  let riskScore = 0;
  const userAgent = input.userAgent.toLowerCase();

  if (!input.startedAtMs) {
    riskScore += 1;
    reasons.push("missing_started_at");
  }

  if (input.startedAtMs && input.nowMs - input.startedAtMs < input.config.minSubmitSeconds * 1000) {
    riskScore += 3;
    reasons.push("submission_too_fast");
  }

  if (/(bot|crawler|spider|headless|playwright|puppeteer|curl|wget|python|axios|httpclient)/i.test(userAgent)) {
    riskScore += 3;
    reasons.push("suspicious_user_agent");
  }

  if (input.currentIpAttempts >= Math.max(1, Math.floor(input.config.ipMaxAttempts / 2))) {
    riskScore += 2;
    reasons.push("ip_attempts_elevated");
  }

  if (input.currentContactAttempts >= Math.max(1, input.config.contactMaxAttempts - 1)) {
    riskScore += 2;
    reasons.push("contact_attempts_elevated");
  }

  return { riskScore, reasonCodes: reasons };
}

export function evaluateLeadSubmission(
  input: LeadEvaluationInput,
  config: LeadSecurityConfig,
): LeadEvaluationResult {
  const nowMs = input.nowMs ?? Date.now();
  const dayKey = new Date(nowMs).toISOString().slice(0, 10);
  const fingerprint = buildLeadFingerprint(input.payload as LeadSecurityPayload, input.normalizedContact, dayKey);
  const idempotencyKey = buildLeadIdempotencyKey(dayKey, fingerprint);
  const ipKey = hashKey(`ip:${input.ip || "unknown"}`).slice(0, 32);
  const contactKey = hashKey(`contact:${input.normalizedContact}`).slice(0, 32);
  const honeypotValue = extractHoneypotValue(input.payload, config.honeypotField);
  const startedAtMs = parseStartedAtMs(input.payload);

  pruneAcceptedFingerprints(nowMs);
  const currentIpAttempts = countAttempts(ipAttemptStore, ipKey, nowMs, config.ipWindowSeconds * 1000);
  const currentContactAttempts = countAttempts(contactAttemptStore, contactKey, nowMs, config.contactWindowSeconds * 1000);
  const { riskScore, reasonCodes } = computeRiskScore({
    startedAtMs,
    nowMs,
    userAgent: input.userAgent,
    currentIpAttempts,
    currentContactAttempts,
    config,
  });

  if (honeypotValue) {
    return {
      action: "silent_drop",
      detail: "Заявка принята. Мы свяжемся с вами в ближайшее время.",
      status: 200,
      reasonCodes: [...reasonCodes, "honeypot_filled"],
      riskScore: riskScore + 5,
      fingerprint,
      idempotencyKey,
      dayKey,
      ipKey,
      contactKey,
      requiresChallenge: false,
    };
  }

  if (startedAtMs && nowMs - startedAtMs < config.minSubmitSeconds * 1000) {
    return {
      action: "silent_drop",
      detail: "Заявка принята. Мы свяжемся с вами в ближайшее время.",
      status: 200,
      reasonCodes: [...reasonCodes],
      riskScore,
      fingerprint,
      idempotencyKey,
      dayKey,
      ipKey,
      contactKey,
      requiresChallenge: false,
    };
  }

  if (currentIpAttempts + 1 > config.ipMaxAttempts) {
    return {
      action: "rate_limit",
      detail: "Слишком много заявок за короткий период. Повторите позже.",
      status: 429,
      reasonCodes: [...reasonCodes, "ip_rate_limited"],
      riskScore: riskScore + 2,
      fingerprint,
      idempotencyKey,
      dayKey,
      ipKey,
      contactKey,
      requiresChallenge: false,
    };
  }

  if (currentContactAttempts + 1 > config.contactMaxAttempts) {
    return {
      action: "rate_limit",
      detail: "Заявка с этим контактом уже отправлялась слишком часто. Повторите позже.",
      status: 429,
      reasonCodes: [...reasonCodes, "contact_rate_limited"],
      riskScore: riskScore + 2,
      fingerprint,
      idempotencyKey,
      dayKey,
      ipKey,
      contactKey,
      requiresChallenge: false,
    };
  }

  if (acceptedFingerprintStore.has(fingerprint)) {
    return {
      action: "duplicate",
      detail: "Заявка принята. Мы свяжемся с вами в ближайшее время.",
      status: 200,
      reasonCodes: [...reasonCodes, "duplicate_fingerprint"],
      riskScore,
      fingerprint,
      idempotencyKey,
      dayKey,
      ipKey,
      contactKey,
      requiresChallenge: false,
    };
  }

  const requiresChallenge = (
    config.challengeMode === "always"
    || (config.challengeMode === "adaptive" && Boolean(config.turnstileSecretKey) && riskScore >= 3)
  );

  return {
    action: "accept",
    detail: "Заявка принята. Мы свяжемся с вами в ближайшее время.",
    status: 200,
    reasonCodes,
    riskScore,
    fingerprint,
    idempotencyKey,
    dayKey,
    ipKey,
    contactKey,
    requiresChallenge,
  };
}

export function recordLeadAttempt(
  result: LeadEvaluationResult,
  config: LeadSecurityConfig,
  nowMs: number = Date.now(),
): void {
  if (result.action === "silent_drop") {
    return;
  }
  rememberAttempt(ipAttemptStore, result.ipKey, nowMs, config.ipWindowSeconds * 1000);
  rememberAttempt(contactAttemptStore, result.contactKey, nowMs, config.contactWindowSeconds * 1000);
}

export function rememberAcceptedLeadFingerprint(fingerprint: string, nowMs: number = Date.now()): void {
  pruneAcceptedFingerprints(nowMs);
  acceptedFingerprintStore.set(fingerprint, nowMs);
}

export async function verifyTurnstileToken(
  token: string,
  remoteIp: string,
  secretKey: string,
  fetchImpl: typeof fetch = fetch,
): Promise<boolean> {
  if (!token.trim() || !secretKey.trim()) {
    return false;
  }

  const response = await fetchImpl("https://challenges.cloudflare.com/turnstile/v0/siteverify", {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: new URLSearchParams({
      secret: secretKey,
      response: token,
      remoteip: remoteIp,
    }),
    cache: "no-store",
  });

  if (!response.ok) {
    return false;
  }

  const payload = await response.json() as { success?: boolean };
  return payload.success === true;
}

export function __resetLeadSecurityStateForTests(): void {
  ipAttemptStore.clear();
  contactAttemptStore.clear();
  acceptedFingerprintStore.clear();
}
