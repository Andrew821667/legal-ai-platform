import { coreGet } from "@/lib/lawyer-core";

/** Серверные помощники маршрутов документов; токен бота в браузер не попадает. */

export type DocumentMeta = {
  telegram_file_id: string;
  file_name: string | null;
  file_size: number | null;
  mime_type: string | null;
};

export function botToken(): string {
  return (process.env.LEAD_BOT_TOKEN || process.env.TELEGRAM_BOT_TOKEN || "").trim();
}

export async function documentMeta(documentId: string): Promise<DocumentMeta | Response> {
  const upstream = await coreGet(`/api/v1/lawyer/documents/${documentId}`);
  if (!upstream.ok) return upstream;
  return (await upstream.json()) as DocumentMeta;
}
