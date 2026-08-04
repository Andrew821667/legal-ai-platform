export type AssistantRole = "user" | "assistant";

export interface AssistantMessage {
  role: AssistantRole;
  message: string;
}

export interface AssistantPayload {
  sessionId: string;
  messages: AssistantMessage[];
}

export class AssistantPayloadError extends Error {
  status: number;

  constructor(message: string, status = 400) {
    super(message);
    this.status = status;
  }
}

const ipBuckets = new Map<string, number[]>();
const sessionBuckets = new Map<string, number[]>();

function positiveInt(raw: string | undefined, fallback: number): number {
  const value = Number(raw || "");
  return Number.isFinite(value) && value > 0 ? Math.round(value) : fallback;
}

function prune(store: Map<string, number[]>, key: string, now: number, windowMs: number): number[] {
  const rows = (store.get(key) || []).filter((ts) => now - ts <= windowMs);
  if (rows.length) {
    store.set(key, rows);
  } else {
    store.delete(key);
  }
  return rows;
}

function cleanMessage(input: unknown): AssistantMessage {
  if (!input || typeof input !== "object") {
    throw new AssistantPayloadError("Некорректное сообщение");
  }
  const row = input as Record<string, unknown>;
  if (row.role !== "user" && row.role !== "assistant") {
    throw new AssistantPayloadError("Недопустимая роль сообщения");
  }
  if (typeof row.message !== "string") {
    throw new AssistantPayloadError("Некорректный текст сообщения");
  }
  const message = row.message.trim();
  const limit = row.role === "user" ? 1600 : 5000;
  if (!message || message.length > limit) {
    throw new AssistantPayloadError(`Сообщение должно содержать от 1 до ${limit} символов`);
  }
  return { role: row.role, message };
}

export function normalizeAssistantPayload(input: unknown): AssistantPayload {
  if (!input || typeof input !== "object") {
    throw new AssistantPayloadError("Некорректный запрос");
  }
  const data = input as Record<string, unknown>;
  const sessionId = typeof data.session_id === "string" ? data.session_id.trim() : "";
  if (!/^[A-Za-z0-9_-]{8,80}$/.test(sessionId)) {
    throw new AssistantPayloadError("Некорректная сессия");
  }
  if (!Array.isArray(data.messages) || data.messages.length < 1 || data.messages.length > 12) {
    throw new AssistantPayloadError("История должна содержать от 1 до 12 сообщений");
  }
  const messages = data.messages.map(cleanMessage);
  if (messages.at(-1)?.role !== "user") {
    throw new AssistantPayloadError("Последнее сообщение должно быть от пользователя");
  }
  if (messages.reduce((sum, item) => sum + item.message.length, 0) > 9000) {
    throw new AssistantPayloadError("История диалога слишком длинная");
  }
  return { sessionId, messages };
}

export function recordAssistantRequest(
  ip: string,
  sessionId: string,
  now = Date.now(),
): { allowed: boolean; retryAfter: number } {
  const windowSeconds = positiveInt(process.env.WEB_ASSISTANT_RATE_WINDOW_SECONDS, 300);
  const ipLimit = positiveInt(process.env.WEB_ASSISTANT_IP_MAX_REQUESTS, 30);
  const sessionLimit = positiveInt(process.env.WEB_ASSISTANT_SESSION_MAX_REQUESTS, 15);
  const windowMs = windowSeconds * 1000;
  const ipRows = prune(ipBuckets, ip, now, windowMs);
  const sessionRows = prune(sessionBuckets, sessionId, now, windowMs);

  if (ipRows.length >= ipLimit || sessionRows.length >= sessionLimit) {
    const oldest = Math.min(ipRows[0] || now, sessionRows[0] || now);
    return { allowed: false, retryAfter: Math.max(1, Math.ceil((oldest + windowMs - now) / 1000)) };
  }

  ipRows.push(now);
  sessionRows.push(now);
  ipBuckets.set(ip, ipRows);
  sessionBuckets.set(sessionId, sessionRows);
  return { allowed: true, retryAfter: 0 };
}

export function isTrustedAssistantOrigin(origin: string | null, host: string): boolean {
  if (!origin) return false;
  try {
    return new URL(origin).host === host;
  } catch {
    return false;
  }
}

export function __resetAssistantSecurityStateForTests(): void {
  ipBuckets.clear();
  sessionBuckets.clear();
}
