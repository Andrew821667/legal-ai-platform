import { NextRequest } from "next/server";

import { requireClient } from "@/lib/client-auth";
import { clientCoreGetFile } from "@/lib/client-core";
import { clientQuery } from "@/lib/client-ref";

/** Файл по делу — клиенту, только свой: владение проверяет ядро. */

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function GET(request: NextRequest, ctx: { params: Promise<{ fileId: string }> }) {
  const auth = requireClient(request);
  if (auth instanceof Response) return auth;
  const { fileId } = await ctx.params;
  if (!UUID.test(fileId)) return Response.json({ detail: "Файл не найден." }, { status: 404 });
  return clientCoreGetFile(`/api/v1/client-portal/files/${fileId}?${clientQuery(auth)}`);
}
