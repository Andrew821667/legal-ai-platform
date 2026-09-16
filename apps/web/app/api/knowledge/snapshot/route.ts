import { NextResponse } from "next/server";

import { buildKnowledgeSnapshot } from "@/lib/knowledgeSnapshot";

export const runtime = "nodejs";

/**
 * Снимок публичных знаний компании (услуги, FAQ, типовые сценарии,
 * методология) для RAG-контекста ассистента лид-бота.
 *
 * Без авторизации: весь этот контент уже публикуется открыто на страницах
 * сайта (/services/*, /guides/*, /cases, FAQ на главной) — здесь тот же
 * текст в плоском JSON для поиска, а не новая утечка данных.
 */
export async function GET() {
  const items = buildKnowledgeSnapshot();
  return NextResponse.json(
    { items, generatedAt: new Date().toISOString() },
    { status: 200, headers: { "Cache-Control": "public, max-age=1800" } },
  );
}
