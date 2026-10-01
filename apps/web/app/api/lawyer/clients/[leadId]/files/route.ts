import { NextRequest } from "next/server";

import { checkUpload } from "@/lib/client-upload";
import { coreGet, corePostForm } from "@/lib/lawyer-core";
import { requireLawyer } from "@/lib/lawyer-auth";

/**
 * Файлы по делу клиента: что прислал клиент из кабинета и что юрист передал
 * ему — заключение, претензию, план. Файл ложится в кабинет клиента; в
 * Telegram клиенту — только уведомление, без имени файла и без самого файла.
 */

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function GET(request: NextRequest, { params }: { params: Promise<{ leadId: string }> }) {
  const auth = requireLawyer(request);
  if (auth instanceof Response) return auth;
  const { leadId } = await params;
  if (!UUID.test(leadId)) return Response.json({ detail: "Некорректный идентификатор клиента" }, { status: 400 });
  return coreGet(`/api/v1/lawyer/clients/${leadId}/files`);
}

export async function POST(request: NextRequest, { params }: { params: Promise<{ leadId: string }> }) {
  const auth = requireLawyer(request);
  if (auth instanceof Response) return auth;
  const { leadId } = await params;
  if (!UUID.test(leadId)) return Response.json({ detail: "Некорректный идентификатор клиента" }, { status: 400 });
  const form = await request.formData().catch(() => null);
  const file = form?.get("file");
  if (!(file instanceof File)) return Response.json({ detail: "Выберите файл." }, { status: 400 });
  const check = checkUpload({ name: file.name, size: file.size });
  if (!check.ok) return Response.json({ detail: check.detail }, { status: 400 });
  const upstream = new FormData();
  upstream.set("file", new Blob([await file.arrayBuffer()], { type: file.type || "application/octet-stream" }), check.name);
  const intakeId = String(form?.get("intake_id") || "");
  if (UUID.test(intakeId)) upstream.set("intake_id", intakeId);
  const note = String(form?.get("note") || "").trim().slice(0, 1000);
  if (note) upstream.set("note", note);
  return corePostForm(`/api/v1/lawyer/clients/${leadId}/files`, upstream);
}
