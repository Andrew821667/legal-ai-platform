/**
 * Документ, который клиент загружает в кабинете: какой можно и какой нельзя.
 *
 * Раньше кабинет отвечал «отправьте файл в чат бота по этому обращению» —
 * лишний шаг и путаница, к какому делу файл. Файл хранится у нас, в базе,
 * зашифрованным (core_api/routers/client_files.py), и в Telegram не уходит:
 * серверы Telegram за рубежом. Предел — 20 МБ, тот же, что у ядра; тот же
 * список и для файлов, которые юрист присылает клиенту.
 */

export const MAX_UPLOAD_BYTES = 20 * 1024 * 1024;

const ALLOWED = new Set([
  "pdf", "doc", "docx", "rtf", "odt", "txt",
  "xls", "xlsx", "csv", "ods",
  "jpg", "jpeg", "png", "heic", "webp",
  "zip",
]);

export type UploadCheck = { ok: true; name: string } | { ok: false; detail: string };

export function checkUpload(file: { name: string; size: number }): UploadCheck {
  const name = (file.name || "").replace(/[\r\n"\\/]/g, "_").trim().slice(0, 200);
  const ext = /\.([A-Za-z0-9]{1,5})$/.exec(name)?.[1]?.toLowerCase() ?? "";
  if (!name || !ext) return { ok: false, detail: "У файла нет расширения — выберите документ, скан или фото." };
  if (!ALLOWED.has(ext)) {
    return { ok: false, detail: `Файлы .${ext} не принимаются. Подойдут PDF, Word, Excel, фото или ZIP-архив.` };
  }
  if (file.size <= 0) return { ok: false, detail: "Файл пустой." };
  if (file.size > MAX_UPLOAD_BYTES) {
    return { ok: false, detail: "Файл больше 20 МБ — разбейте его или отправьте архивом поменьше." };
  }
  return { ok: true, name };
}
