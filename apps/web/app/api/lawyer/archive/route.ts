import { NextRequest } from "next/server";

import { coreGet } from "@/lib/lawyer-core";
import { requireLawyer } from "@/lib/lawyer-auth";

/** Клиенты в архиве — со счётом того, что пропадёт при удалении. */

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  const auth = requireLawyer(request);
  if (auth instanceof Response) return auth;
  return coreGet("/api/v1/lawyer/archive");
}
