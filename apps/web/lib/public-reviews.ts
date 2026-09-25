/**
 * Отзывы клиентов для публичных страниц — только одобренные юристом и с
 * согласием клиента (ядро: core_api/client_reviews.py). Имя — только первое.
 *
 * Сайт не должен падать из-за отзывов: ядро недоступно или ответило странно —
 * секции просто нет.
 */

export type PublicReview = { name: string; score: number | null; text: string; date: string | null };

const CORE_API_URL =
  process.env.CORE_API_URL || process.env.NEXT_PUBLIC_CORE_API_URL || "http://127.0.0.1:8000";
const CORE_API_BOT_KEY = process.env.CORE_API_BOT_KEY || process.env.API_KEY_BOT || "";

/** Приводит ответ ядра к безопасному виду: мусор отбрасывается, текст обрезается. */
export function sanitizeReviews(raw: unknown, limit = 6): PublicReview[] {
  if (!Array.isArray(raw)) return [];
  const out: PublicReview[] = [];
  for (const item of raw) {
    if (!item || typeof item !== "object") continue;
    const row = item as Record<string, unknown>;
    const text = typeof row.text === "string" ? row.text.trim() : "";
    if (text.length < 2) continue;
    const score = typeof row.score === "number" && row.score >= 1 && row.score <= 5 ? Math.round(row.score) : null;
    const name = typeof row.name === "string" && row.name.trim() ? row.name.trim().slice(0, 40) : "Клиент";
    const date = typeof row.date === "string" && /^\d{4}-\d{2}-\d{2}$/.test(row.date) ? row.date : null;
    out.push({ name, score, text: text.length > 600 ? `${text.slice(0, 597)}…` : text, date });
    if (out.length >= limit) break;
  }
  return out;
}

export async function fetchPublicReviews(): Promise<PublicReview[]> {
  if (!CORE_API_BOT_KEY) return [];
  try {
    const response = await fetch(`${CORE_API_URL}/api/v1/reviews/public`, {
      headers: { "X-API-Key": CORE_API_BOT_KEY },
      next: { revalidate: 600 },
      signal: AbortSignal.timeout(5_000),
    });
    if (!response.ok) return [];
    return sanitizeReviews(await response.json());
  } catch {
    return [];
  }
}
