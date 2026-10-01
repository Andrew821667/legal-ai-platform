import { NextRequest } from "next/server";

import { requireClient } from "@/lib/client-auth";
import { clientCoreGet, clientCorePost } from "@/lib/client-core";
import { clientFields, clientQuery } from "@/lib/client-ref";

/**
 * Переписка по делу в кабинете: клиент пишет юристу и видит ответы — в том
 * числе без Telegram (вход через Яндекс ID). Раньше «Написать по делу» вела
 * в бота, который без VPN не открывается.
 */

export const dynamic = "force-dynamic";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const MAX_TEXT = 4000;

export async function GET(request: NextRequest, ctx: { params: Promise<{ intakeId: string }> }) {
  const auth = requireClient(request);
  if (auth instanceof Response) return auth;
  const { intakeId } = await ctx.params;
  if (!UUID.test(intakeId)) return Response.json({ detail: "Дело не найдено." }, { status: 404 });
  return clientCoreGet(`/api/v1/client-portal/cases/${intakeId}/messages?${clientQuery(auth)}`);
}

export async function POST(request: NextRequest, ctx: { params: Promise<{ intakeId: string }> }) {
  const auth = requireClient(request);
  if (auth instanceof Response) return auth;
  const { intakeId } = await ctx.params;
  if (!UUID.test(intakeId)) return Response.json({ detail: "Дело не найдено." }, { status: 404 });
  const body = (await request.json().catch(() => null)) as { text?: unknown } | null;
  const text = typeof body?.text === "string" ? body.text.trim() : "";
  if (!text) return Response.json({ detail: "Напишите сообщение." }, { status: 400 });
  if (text.length > MAX_TEXT) return Response.json({ detail: "Сообщение слишком длинное." }, { status: 400 });
  return clientCorePost(`/api/v1/client-portal/cases/${intakeId}/messages`, {
    ...clientFields(auth),
    text,
    channel: "cabinet",
  });
}
