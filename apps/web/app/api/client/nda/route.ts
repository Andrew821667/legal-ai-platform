import { NextRequest } from "next/server";

import { requireClient } from "@/lib/client-auth";
import { clientCoreGet, clientCorePost } from "@/lib/client-core";

export async function GET(request: NextRequest) {
  const auth = requireClient(request);
  if (auth instanceof Response) return auth;
  return clientCoreGet("/api/v1/nda/document");
}

export async function POST(request: NextRequest) {
  const auth = requireClient(request);
  if (auth instanceof Response) return auth;
  const body = await request.json().catch(() => null);
  if (!body || typeof body !== "object") {
    return Response.json({ detail: "Некорректные данные." }, { status: 400 });
  }
  return clientCorePost("/api/v1/nda/sign", {
    ...body,
    telegram_user_id: auth.telegramUserId,
    channel: "miniapp",
  });
}
