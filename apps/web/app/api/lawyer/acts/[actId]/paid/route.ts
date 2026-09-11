import { NextRequest } from "next/server";

import { corePatch } from "@/lib/lawyer-core";
import { requireLawyer } from "@/lib/lawyer-auth";

/**
 * Юрист подтверждает: деньги пришли.
 *
 * У самозанятого без ИП нет банковского API, чтобы проверить зачисление
 * программно — деньги в любом случае идёт переводом, и видит их только сам
 * юрист. Работает и до клика клиента «Я оплатил(а)», и после него.
 */

export const dynamic = "force-dynamic";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ actId: string }> },
) {
  const auth = requireLawyer(request);
  if (auth instanceof Response) return auth;

  const { actId } = await params;
  if (!UUID.test(actId)) {
    return Response.json({ detail: "Некорректный идентификатор акта" }, { status: 400 });
  }
  const body = (await request.json().catch(() => ({}))) as { note?: unknown };
  const note = typeof body.note === "string" && body.note.trim() ? body.note.trim().slice(0, 500) : null;

  return corePatch(`/api/v1/work-acts/${actId}/paid`, {
    paid_by_telegram_user_id: auth.telegramUserId,
    note,
  });
}
