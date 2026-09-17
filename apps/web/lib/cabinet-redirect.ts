/**
 * Защита от open redirect для параметра ?next= у /cabinet/login.
 *
 * next кладётся в подписанную куку client_oauth и используется только после
 * успешной проверки Telegram-логина — сам по себе он не incoming user input,
 * которому доверяют напрямую. Но подпись куки не ограничивает СОДЕРЖИМОЕ
 * next, а только то, что его не подменили в пути; отфильтровать протокол/хост
 * всё равно нужно на входе, иначе подписанная кука с
 * next="https://evil.example" увела бы после честного входа на чужой сайт.
 */

const SAFE_NEXT_PATTERN = /^\/(?!\/)[^\s\\]*$/;
const MAX_LENGTH = 512;
const DEFAULT_NEXT = "/cabinet";

export function safeNextPath(raw: string | null | undefined): string {
  const value = (raw || "").trim();
  if (!value) return DEFAULT_NEXT;
  if (value.length > MAX_LENGTH) return DEFAULT_NEXT;
  if (!SAFE_NEXT_PATTERN.test(value)) return DEFAULT_NEXT;
  return value;
}
