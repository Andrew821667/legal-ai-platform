import { NextRequest } from "next/server";

import { corePost } from "@/lib/lawyer-core";
import { requireLawyer } from "@/lib/lawyer-auth";

/** Убрать отправку из «Не доставлено». */

export const dynamic = "force-dynamic";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ deliveryId: string }> },
) {
  const auth = requireLawyer(request);
  if (auth instanceof Response) return auth;
  const { deliveryId } = await params;
  if (!UUID.test(deliveryId)) {
    return Response.json({ detail: "Некорректный идентификатор отправки" }, { status: 400 });
  }
  return corePost(`/api/v1/lawyer/deliveries/${deliveryId}/dismiss`);
}
