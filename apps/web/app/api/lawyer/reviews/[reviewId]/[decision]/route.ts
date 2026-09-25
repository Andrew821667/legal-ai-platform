import { NextRequest } from "next/server";

import { corePost } from "@/lib/lawyer-core";
import { requireLawyer } from "@/lib/lawyer-auth";

/** Юрист решает, показывать ли отзыв клиента на сайте (ядро: client_reviews). */

export const dynamic = "force-dynamic";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ reviewId: string; decision: string }> },
) {
  const auth = requireLawyer(request);
  if (auth instanceof Response) return auth;
  const { reviewId, decision } = await params;
  if (!UUID.test(reviewId) || (decision !== "approve" && decision !== "hide")) {
    return Response.json({ detail: "Некорректный запрос" }, { status: 400 });
  }
  return corePost(`/api/v1/lawyer/reviews/${reviewId}/${decision}`, undefined);
}
