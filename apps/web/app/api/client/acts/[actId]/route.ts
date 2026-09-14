import { randomUUID } from "node:crypto";
import { NextRequest } from "next/server";

import { requireClient } from "@/lib/client-auth";
import { clientCoreGet, clientCorePost } from "@/lib/client-core";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function GET(request: NextRequest, ctx: { params: Promise<{ actId: string }> }) {
  const auth = requireClient(request);
  if (auth instanceof Response) return auth;
  const { actId } = await ctx.params;
  if (!UUID.test(actId)) return Response.json({ detail: "Акт не найден." }, { status: 404 });
  return clientCoreGet(`/api/v1/work-acts/${actId}/document?telegram_user_id=${auth.telegramUserId}`);
}

export async function POST(request: NextRequest, ctx: { params: Promise<{ actId: string }> }) {
  const auth = requireClient(request);
  if (auth instanceof Response) return auth;
  const { actId } = await ctx.params;
  if (!UUID.test(actId)) return Response.json({ detail: "Акт не найден." }, { status: 404 });
  const body = await request.json().catch(() => null) as Record<string, unknown> | null;
  const action = typeof body?.action === "string" ? body.action : "";
  if (!["viewed", "accept", "object", "claim-paid"].includes(action)) {
    return Response.json({ detail: "Неизвестное действие." }, { status: 400 });
  }
  const payload = {
    ...body,
    action: undefined,
    telegram_user_id: auth.telegramUserId,
    callback_id: `miniapp:${randomUUID()}`,
    channel: "miniapp",
  };
  const suffix = action === "claim-paid" ? "claim-paid" : `client/${action}`;
  return clientCorePost(`/api/v1/work-acts/${actId}/${suffix}`, payload);
}
