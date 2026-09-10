import { NextRequest } from "next/server";

import { coreGet } from "@/lib/lawyer-core";
import { requireLawyer } from "@/lib/lawyer-auth";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  const auth = requireLawyer(request);
  if (auth instanceof Response) {
    return auth;
  }
  const search = (request.nextUrl.searchParams.get("search") || "").slice(0, 120);
  const query = search ? `?search=${encodeURIComponent(search)}` : "";
  return coreGet(`/api/v1/lawyer/clients${query}`);
}
