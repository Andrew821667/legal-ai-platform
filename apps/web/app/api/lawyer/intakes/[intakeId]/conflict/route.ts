import { NextRequest } from "next/server";

import { corePatch } from "@/lib/lawyer-core";
import { requireLawyer } from "@/lib/lawyer-auth";

/**
 * Отметка о проверке конфликта интересов.
 *
 * Ядро отказывается создавать договор, пока проверка не пройдена, а новое
 * обращение всегда приходит непроверенным. Без этого маршрута юрист видел бы
 * блокировку в рабочем месте, а снимать её уходил в админ-панель.
 */

export const dynamic = "force-dynamic";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

// Отсюда отмечают исход проверки. Вернуть «не проверено» нельзя: это не
// решение юриста, а состояние обращения до того, как он на него посмотрел.
const ALLOWED = new Set(["clear", "potential", "conflict"]);

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ intakeId: string }> },
) {
  const auth = requireLawyer(request);
  if (auth instanceof Response) return auth;

  const { intakeId } = await params;
  if (!UUID.test(intakeId)) {
    return Response.json({ detail: "Некорректный идентификатор обращения" }, { status: 400 });
  }

  const body = (await request.json().catch(() => ({}))) as { conflict_status?: unknown };
  const status = String(body.conflict_status ?? "");
  if (!ALLOWED.has(status)) {
    return Response.json({ detail: "Неизвестный исход проверки" }, { status: 400 });
  }

  return corePatch(`/api/v1/legal-intakes/${intakeId}`, { conflict_status: status });
}
