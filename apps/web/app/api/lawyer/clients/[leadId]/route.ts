import { NextRequest } from "next/server";

import { coreGet } from "@/lib/lawyer-core";
import { requireLawyer } from "@/lib/lawyer-auth";

export const dynamic = "force-dynamic";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ leadId: string }> },
) {
  const auth = requireLawyer(request);
  if (auth instanceof Response) {
    return auth;
  }
  const { leadId } = await params;
  if (!UUID.test(leadId)) {
    // Не пропускаем произвольную строку в путь запроса к ядру.
    return Response.json({ detail: "Некорректный идентификатор клиента" }, { status: 400 });
  }
  return coreGet(`/api/v1/lawyer/clients/${leadId}`);
}
