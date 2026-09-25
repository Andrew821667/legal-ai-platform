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
  // Подпись NDA и согласие на ПДн определены через Telegram (п.6 NDA), и
  // ядро NDA сверяет владельца только по нему. Для входа через Яндекс ID —
  // после новой редакции соглашения.
  if (auth.accountId !== null) {
    return Response.json(
      {
        detail:
          "Подписать соглашение при входе через Яндекс ID пока нельзя — это появится в ближайшем обновлении. Если документ нужен срочно, напишите юристу.",
      },
      { status: 409 },
    );
  }
  const body = await request.json().catch(() => null);
  if (!body || typeof body !== "object") {
    return Response.json({ detail: "Некорректные данные." }, { status: 400 });
  }
  const data = body as Record<string, unknown>;
  const action = String(data.action || "sign");
  const paths: Record<string, string> = {
    "consent-preview": "/api/v1/nda/personal-data-consent/preview",
    "consent-accept": "/api/v1/nda/personal-data-consent/accept",
    "nda-preview": "/api/v1/nda/document/preview",
    sign: "/api/v1/nda/sign",
  };
  const path = paths[action];
  if (!path) {
    return Response.json({ detail: "Некорректное действие." }, { status: 400 });
  }
  const { action: _, ...payload } = data;
  return clientCorePost(path, {
    ...payload,
    telegram_user_id: auth.telegramUserId,
    channel: "miniapp",
  });
}
