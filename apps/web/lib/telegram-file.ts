/**
 * Файлы, которые клиент прислал боту.
 *
 * Байты живут в Telegram, и достать их может только бот своим токеном:
 * getFile → временный путь → скачивание. Токен здесь и остаётся — в ошибках
 * его быть не должно, они уходят юристу на экран.
 *
 * Внутри Telegram скачивать незачем: бот может переслать файл в чат по
 * тому же идентификатору — мгновенно, без байтов через нас, и откроется он
 * нативным просмотрщиком. Скачивание нужно снаружи, в Safari.
 */

// Локальный Bot API server (официальный) снимает лимит в 20 МБ — адрес
// подменяется переменной окружения; по умолчанию — облако Telegram.
const API = (process.env.TELEGRAM_API_BASE || "https://api.telegram.org").replace(/\/+$/, "");

// Bot API отдаёт файлы до 20 МБ; крупнее — только через Telegram-клиент.
export const MAX_FILE_BYTES = 20 * 1024 * 1024;

type Fetch = typeof fetch;

export class TelegramFileError extends Error {}

async function call(
  token: string,
  method: string,
  payload: Record<string, unknown>,
  fetchImpl: Fetch,
): Promise<Record<string, unknown>> {
  let response: Response;
  try {
    response = await fetchImpl(`${API}/bot${token}/${method}`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
      cache: "no-store",
    });
  } catch {
    throw new TelegramFileError("Telegram не отвечает");
  }
  const body = (await response.json().catch(() => ({}))) as {
    ok?: boolean;
    result?: Record<string, unknown>;
    description?: string;
  };
  if (!response.ok || !body.ok || !body.result) {
    // Описание от Telegram — без токена, но и без нужды показывать его
    // дословно: юристу важно, что файл недоступен, а не почему по-английски.
    throw new TelegramFileError(
      /file is too big/i.test(body.description || "")
        ? "Файл больше 20 МБ — откройте его в Telegram"
        : "Файл недоступен в Telegram",
    );
  }
  return body.result;
}

/** Временный путь к файлу — действует около часа, скачивать сразу. */
export async function getTelegramFilePath(
  token: string,
  fileId: string,
  fetchImpl: Fetch = fetch,
): Promise<string> {
  const result = await call(token, "getFile", { file_id: fileId }, fetchImpl);
  const path = result.file_path;
  if (typeof path !== "string" || !path) {
    throw new TelegramFileError("Файл недоступен в Telegram");
  }
  return path;
}

export function telegramFileUrl(token: string, filePath: string): string {
  return `${API}/file/bot${token}/${filePath}`;
}

/** Переслать файл в чат по идентификатору — без скачивания и загрузки. */
export async function sendTelegramDocument(
  token: string,
  chatId: number,
  fileId: string,
  caption: string,
  fetchImpl: Fetch = fetch,
): Promise<void> {
  await call(token, "sendDocument", { chat_id: chatId, document: fileId, caption }, fetchImpl);
}

/**
 * Заголовок с именем файла, переживающий кириллицу.
 *
 * `filename=` понимают все, но только в ASCII; `filename*=` (RFC 5987) несёт
 * настоящее имя. Оба сразу — иначе Safari сохранит «договор.pdf» как
 * «document.pdf», а старые клиенты не поймут второе.
 */
export function contentDisposition(fileName: string | null, inline: boolean): string {
  const name = (fileName || "document").replace(/[\r\n"\\]/g, "_").slice(0, 200);
  const ext = /\.[A-Za-z0-9]{1,8}$/.exec(name)?.[0] ?? "";
  const ascii = /^[\x20-\x7e]+$/.test(name) ? name : `document${ext}`;
  const encoded = encodeURIComponent(name).replace(/['()*]/g, (c) => `%${c.charCodeAt(0).toString(16).toUpperCase()}`);
  return `${inline ? "inline" : "attachment"}; filename="${ascii}"; filename*=UTF-8''${encoded}`;
}

/** Что браузер покажет сам, а что честнее сразу скачать. */
export function showsInline(mimeType: string | null): boolean {
  return /^(application\/pdf|image\/(png|jpeg|gif|webp)|text\/plain)$/.test(mimeType || "");
}
