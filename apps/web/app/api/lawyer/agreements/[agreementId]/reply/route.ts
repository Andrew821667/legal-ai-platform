import { NextRequest } from "next/server";

import { corePost } from "@/lib/lawyer-core";
import { requireLawyer } from "@/lib/lawyer-auth";

export const dynamic = "force-dynamic";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const MAX_LENGTH = 4000;

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ agreementId: string }> },
) {
  const auth = requireLawyer(request);
  if (auth instanceof Response) return auth;

  const { agreementId } = await params;
  if (!UUID.test(agreementId)) {
    return Response.json({ detail: "Некорректный идентификатор договора" }, { status: 400 });
  }

  const body = (await request.json().catch(() => ({}))) as { text?: unknown };
  const text = String(body.text ?? "").trim();
  if (!text) {
    return Response.json({ detail: "Пустой ответ отправлять некуда" }, { status: 422 });
  }

  return corePost(`/api/v1/service-agreements/${agreementId}/replies/deliver`, {
    text: text.slice(0, MAX_LENGTH),
    telegram_user_id: auth.telegramUserId,
  });
}
