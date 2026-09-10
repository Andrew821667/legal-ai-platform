import { NextRequest } from "next/server";

import { corePatch } from "@/lib/lawyer-core";
import { requireLawyer } from "@/lib/lawyer-auth";

export const dynamic = "force-dynamic";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const MAX_LENGTH = 4000;

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

  const body = (await request.json().catch(() => ({}))) as { note?: unknown };
  // Пустую заметку принимаем: так она стирается.
  const note = String(body.note ?? "").slice(0, MAX_LENGTH);

  return corePatch(`/api/v1/legal-intakes/${intakeId}`, { internal_note: note });
}
