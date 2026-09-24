import { NextRequest } from "next/server";

import { corePost } from "@/lib/lawyer-core";
import { requireLawyer } from "@/lib/lawyer-auth";
import { checkSupplementDraft } from "@/lib/supplement-draft";

/**
 * Допсоглашение к подписанному договору — черновиком.
 *
 * Сумму подписанного договора раньше меняла одна кнопка — в одну сторону.
 * Теперь новая стоимость и дополнительные работы уходят клиенту документом,
 * а сумма договора меняется, когда он подпишет. Кто составил — из
 * проверенной сессии, а не из тела запроса.
 */

export const dynamic = "force-dynamic";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

// Столько же, сколько у договора: два документа по одному делу не должны
// жить разный срок.
const EXPIRES_IN_DAYS = 7;

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

  const body = (await request.json().catch(() => ({}))) as Record<string, unknown>;
  const draft = checkSupplementDraft(body);
  if (!draft.ok) {
    return Response.json({ detail: draft.detail }, { status: 400 });
  }

  return corePost(`/api/v1/service-agreements/${agreementId}/supplements`, {
    ...draft.value,
    prepared_by_telegram_user_id: auth.telegramUserId,
    expires_in_days: EXPIRES_IN_DAYS,
  });
}
