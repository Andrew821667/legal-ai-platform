import { NextRequest, NextResponse } from "next/server";
import { callReaderCoreCached, ensureReaderKey } from "../core";

type HighlightAudience = "lawyer" | "business" | "mixed";

type HighlightItem = {
  id: string;
  title: string;
  summary: string;
  rubric: string;
  kind: string;
  postedAt: string;
};

const AUDIENCE_KEYWORDS: Record<Exclude<HighlightAudience, "mixed">, string[]> = {
  lawyer: [
    "договор",
    "contract",
    "претензи",
    "суд",
    "litigation",
    "комплаенс",
    "privacy",
    "регулир",
    "compliance",
  ],
  business: [
    "бизнес",
    "операц",
    "sla",
    "внедрен",
    "процесс",
    "эффект",
    "эконом",
    "метрик",
    "управлен",
  ],
};

function normalizeAudience(raw: string): HighlightAudience {
  const value = raw.trim().toLowerCase();
  if (value === "lawyer" || value === "business") {
    return value;
  }
  return "mixed";
}

function trimSummary(text: string, limit: number = 170): string {
  const normalized = String(text || "").replace(/\s+/g, " ").trim();
  if (!normalized) {
    return "";
  }
  if (normalized.length <= limit) {
    return normalized;
  }
  const cut = normalized.lastIndexOf(" ", limit);
  if (cut < Math.floor(limit * 0.7)) {
    return `${normalized.slice(0, limit).trimEnd()}...`;
  }
  return `${normalized.slice(0, cut).trimEnd()}...`;
}

function scoreForAudience(row: any, audience: HighlightAudience): number {
  if (audience === "mixed") {
    return 0;
  }
  const haystack = `${row?.title || ""}\n${row?.text || ""}\n${row?.rubric || ""}`.toLowerCase();
  const keywords = AUDIENCE_KEYWORDS[audience];
  let score = 0;
  for (const token of keywords) {
    if (haystack.includes(token)) {
      score += 1;
    }
  }
  return score;
}

function mapHighlight(row: any): HighlightItem {
  return {
    id: String(row?.id || ""),
    title: String(row?.title || "Без заголовка").trim(),
    summary: trimSummary(String(row?.text || "")),
    rubric: String(row?.rubric || ""),
    kind: String(row?.publication_kind || row?.format_type || "daily"),
    postedAt: String(row?.posted_at || row?.publish_at || ""),
  };
}

export async function GET(request: NextRequest) {
  if (!ensureReaderKey()) {
    return NextResponse.json(
      { detail: "CORE_API_BOT_KEY/API_KEY_BOT/API_KEY_NEWS is not configured on web server" },
      { status: 500 },
    );
  }

  const audience = normalizeAudience(String(request.nextUrl.searchParams.get("audience") || "mixed"));
  const requestedLimit = Number(request.nextUrl.searchParams.get("limit") || "3");
  const limit = Number.isFinite(requestedLimit)
    ? Math.max(1, Math.min(8, Math.round(requestedLimit)))
    : 3;

  try {
    const { response, data, cacheState } = await callReaderCoreCached(
      `/api/v1/scheduled-posts?limit=60&status=posted&newest_first=True`,
      { method: "GET" },
      { ttlMs: 120000, staleMs: 600000 },
    );
    if (!response.ok) {
      return NextResponse.json(data, { status: response.status });
    }

    const rows = Array.isArray(data) ? data : [];
    const scored = rows
      .map((row: any) => ({
        row,
        score: scoreForAudience(row, audience),
      }))
      .sort((left, right) => {
        if (right.score !== left.score) {
          return right.score - left.score;
        }
        return String(right.row?.posted_at || right.row?.publish_at || "").localeCompare(
          String(left.row?.posted_at || left.row?.publish_at || ""),
        );
      });

    const selected: any[] = [];
    for (const item of scored) {
      if (selected.length >= limit) {
        break;
      }
      if (audience !== "mixed" && item.score <= 0 && selected.length >= Math.max(1, limit - 1)) {
        continue;
      }
      selected.push(item.row);
    }

    if (selected.length < limit) {
      for (const row of rows) {
        if (selected.length >= limit) {
          break;
        }
        const id = String(row?.id || "");
        if (!id || selected.some((candidate) => String(candidate?.id || "") === id)) {
          continue;
        }
        selected.push(row);
      }
    }

    const highlights = selected.slice(0, limit).map(mapHighlight);
    const headers: Record<string, string> = {};
    if (cacheState === "hit" || cacheState === "stale") {
      headers["X-Reader-Core-Cache"] = cacheState;
    }
    return NextResponse.json({ highlights }, { headers });
  } catch (error: any) {
    return NextResponse.json(
      { detail: error?.message || "Failed to fetch reader highlights" },
      { status: 500 },
    );
  }
}
