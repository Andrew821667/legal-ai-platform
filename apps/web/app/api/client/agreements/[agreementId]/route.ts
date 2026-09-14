import { randomUUID } from "node:crypto";
import { NextRequest } from "next/server";

import { requireClient } from "@/lib/client-auth";
import { clientCoreGet, clientCorePost } from "@/lib/client-core";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function GET(request: NextRequest, ctx: { params: Promise<{ agreementId: string }> }) {
  const auth = requireClient(request);
  if (auth instanceof Response) return auth;
  const { agreementId } = await ctx.params;
  if (!UUID.test(agreementId)) return Response.json({ detail: "Договор не найден." }, { status: 404 });
  return clientCoreGet(
    `/api/v1/service-agreements/${agreementId}?telegram_user_id=${auth.telegramUserId}`,
  );
}

export async function POST(request: NextRequest, ctx: { params: Promise<{ agreementId: string }> }) {
  const auth = requireClient(request);
  if (auth instanceof Response) return auth;
  const { agreementId } = await ctx.params;
  if (!UUID.test(agreementId)) return Response.json({ detail: "Договор не найден." }, { status: 404 });
  const body = await request.json().catch(() => null) as Record<string, unknown> | null;
  const action = typeof body?.action === "string" ? body.action : "";
  const payload = {
    ...body,
    action: undefined,
    telegram_user_id: auth.telegramUserId,
    callback_id: `miniapp:${randomUUID()}`,
    channel: "miniapp",
  };
  const paths: Record<string, string> = {
    viewed: "viewed",
    details: "client-details",
    sign: "sign",
    decline: "decline",
    question: "questions",
  };
  if (!paths[action]) return Response.json({ detail: "Неизвестное действие." }, { status: 400 });
  return clientCorePost(`/api/v1/service-agreements/${agreementId}/${paths[action]}`, payload);
}
