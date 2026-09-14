import { NextRequest } from "next/server";

import { requireLawyer } from "@/lib/lawyer-auth";
import { coreGet } from "@/lib/lawyer-core";

export const dynamic = "force-dynamic";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ consentId: string }> },
) {
  const auth = requireLawyer(request);
  if (auth instanceof Response) return auth;

  const { consentId } = await params;
  if (!UUID.test(consentId)) {
    return Response.json({ detail: "Некорректный идентификатор согласия" }, { status: 400 });
  }
  return coreGet(`/api/v1/lawyer/nda-consents/${consentId}/document`);
}
