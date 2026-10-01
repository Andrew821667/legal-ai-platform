import { NextRequest } from "next/server";

import { coreDelete, coreGetFile } from "@/lib/lawyer-core";
import { requireLawyer } from "@/lib/lawyer-auth";

/** Файл по делу: скачать или удалить (например, отправлен не тому клиенту). */

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function GET(request: NextRequest, { params }: { params: Promise<{ fileId: string }> }) {
  const auth = requireLawyer(request);
  if (auth instanceof Response) return auth;
  const { fileId } = await params;
  if (!UUID.test(fileId)) return Response.json({ detail: "Файл не найден." }, { status: 404 });
  return coreGetFile(`/api/v1/lawyer/files/${fileId}`);
}

export async function DELETE(request: NextRequest, { params }: { params: Promise<{ fileId: string }> }) {
  const auth = requireLawyer(request);
  if (auth instanceof Response) return auth;
  const { fileId } = await params;
  if (!UUID.test(fileId)) return Response.json({ detail: "Файл не найден." }, { status: 404 });
  return coreDelete(`/api/v1/lawyer/files/${fileId}`);
}
