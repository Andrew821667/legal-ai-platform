import { NextRequest } from "next/server";

import { coreGet, corePost } from "@/lib/lawyer-core";
import { requireLawyer } from "@/lib/lawyer-auth";

/** Заготовки условий договора: список для практики обращения и сохранение новой. */

export const dynamic = "force-dynamic";

const PRACTICES = new Set(["legal", "engineering", "hybrid"]);

export async function GET(request: NextRequest) {
  const auth = requireLawyer(request);
  if (auth instanceof Response) return auth;
  const practice = request.nextUrl.searchParams.get("practice") || "";
  const query = PRACTICES.has(practice) ? `?practice=${practice}` : "";
  return coreGet(`/api/v1/lawyer/agreement-templates${query}`);
}

export async function POST(request: NextRequest) {
  const auth = requireLawyer(request);
  if (auth instanceof Response) return auth;
  const body = (await request.json().catch(() => ({}))) as Record<string, unknown>;
  const practice = typeof body.practice === "string" && PRACTICES.has(body.practice) ? body.practice : null;
  return corePost("/api/v1/lawyer/agreement-templates", { ...body, practice });
}
