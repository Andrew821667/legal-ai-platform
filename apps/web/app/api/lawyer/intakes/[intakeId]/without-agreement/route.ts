import { NextRequest } from "next/server";

import { corePatch } from "@/lib/lawyer-core";
import { requireLawyer } from "@/lib/lawyer-auth";

/**
 * Вести обращение без отдельного договора.
 *
 * Развилка после NDA: клиент подписал соглашение о конфиденциальности, а
 * договор об оказании услуг для этого дела не нужен — консультация, разовый
 * документ, доверительные отношения. В боте этот шаг был, а в рабочем месте
 * — нет: юрист видел «Составить договор» и ничего больше.
 *
 * Условия проверяет ядро и отвечает 409 с причиной: обращение закрыто, по
 * нему уже есть договор, NDA не подписан, конфликт не проверен.
 */

export const dynamic = "force-dynamic";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

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
  return corePatch(`/api/v1/legal-intakes/${intakeId}`, { without_agreement: true });
}
