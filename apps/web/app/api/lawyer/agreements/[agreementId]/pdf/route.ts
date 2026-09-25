import { NextRequest } from "next/server";

import { coreGetFile } from "@/lib/lawyer-core";
import { requireLawyer } from "@/lib/lawyer-auth";

/** PDF договора или допсоглашения: точный текст и лист сведений о подписании. */

export const dynamic = "force-dynamic";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ agreementId: string }> },
) {
  const auth = requireLawyer(request);
  if (auth instanceof Response) return auth;
  const { agreementId } = await params;
  if (!UUID.test(agreementId)) {
    return Response.json({ detail: "Некорректный идентификатор договора" }, { status: 400 });
  }
  return coreGetFile(`/api/v1/service-agreements/${agreementId}/pdf`);
}
