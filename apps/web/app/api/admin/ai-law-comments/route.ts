import { NextRequest, NextResponse } from "next/server";
import { revalidatePath } from "next/cache";

import { auditAdminSessionEvent, requireAdminSession } from "@/lib/admin-session";
import {
  getAiLawEditorialComment,
  listAiLawEditorialComments,
  normalizeAiLawComment,
  saveAiLawComment,
} from "@/lib/aiLawEditorialStore";
import { SEO_SITE_URL } from "@/lib/seo";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

type IndexNowResult = "accepted" | "failed" | "skipped";
const INDEXNOW_KEY = "b4fe13ccb289b2cb74669ac21583f8af224efe317e2f9a79c23b2bb57d5e1fe4";
const INDEXNOW_KEY_NAME = `${INDEXNOW_KEY}.txt`;

async function notifyIndexNow(slug: string): Promise<IndexNowResult> {
  if (process.env.INDEXNOW_DISABLED === "1") return "skipped";
  try {
    const baseUrl = SEO_SITE_URL.replace(/\/$/, "");
    const response = await fetch("https://yandex.com/indexnow", {
      method: "POST",
      headers: { "Content-Type": "application/json; charset=utf-8" },
      body: JSON.stringify({
        host: new URL(baseUrl).hostname,
        key: INDEXNOW_KEY,
        keyLocation: `${baseUrl}/${INDEXNOW_KEY_NAME}`,
        urlList: [`${baseUrl}/ai-law`, `${baseUrl}/ai-law/${slug}`],
      }),
      signal: AbortSignal.timeout(8_000),
    });
    return response.ok ? "accepted" : "failed";
  } catch (error) {
    console.error("[ai-law-editorial] IndexNow notification failed", error);
    return "failed";
  }
}

export async function GET(request: NextRequest) {
  const unauthorized = requireAdminSession(request);
  if (unauthorized) return unauthorized;
  return NextResponse.json({ comments: listAiLawEditorialComments() });
}

export async function PUT(request: NextRequest) {
  const unauthorized = requireAdminSession(request);
  if (unauthorized) return unauthorized;

  try {
    const payload = await request.json() as { comment?: unknown };
    const draft = normalizeAiLawComment(payload.comment);
    const existing = getAiLawEditorialComment(draft.slug);
    if (
      draft.status === "published"
      && existing?.status !== "verified"
      && existing?.status !== "published"
    ) {
      return NextResponse.json(
        { detail: "Сначала сохраните материал со статусом «Проверено»" },
        { status: 409 },
      );
    }

    const today = new Date().toISOString().slice(0, 10);
    if ((draft.status === "verified" || draft.status === "published") && !draft.reviewedAt) {
      draft.reviewedAt = today;
    }
    if (draft.status === "published" && !draft.publishedAt) {
      draft.publishedAt = today;
    }

    const comment = saveAiLawComment(draft);
    revalidatePath("/ai-law");
    revalidatePath(`/ai-law/${comment.slug}`);
    revalidatePath("/miniapp/content");
    revalidatePath("/sitemap.xml");

    const indexNow = comment.status === "published"
      ? await notifyIndexNow(comment.slug)
      : "skipped";
    auditAdminSessionEvent(
      request,
      "ai_law_comment_save",
      "success",
      `${comment.slug}:${comment.status}:${indexNow}`,
    );
    return NextResponse.json({ comment, indexNow });
  } catch (error) {
    const detail = error instanceof Error ? error.message : "Не удалось сохранить материал";
    auditAdminSessionEvent(request, "ai_law_comment_save", "failed", detail.slice(0, 300));
    return NextResponse.json({ detail }, { status: 400 });
  }
}
