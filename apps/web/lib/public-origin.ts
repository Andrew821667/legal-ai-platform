/**
 * Публичный адрес сайта, каким его видел браузер, — для абсолютных редиректов
 * из Route Handler'ов.
 *
 * `request.url` в self-hosted `next start` отражает адрес, на котором слушает
 * сам процесс (здесь — 0.0.0.0:3000), а не домен, с которым говорил браузер.
 * В проде это привело к редиректу на https://0.0.0.0:3000/lawyer —
 * недостижимому снаружи контейнера адресу. Caddy как reverse_proxy сам
 * добавляет X-Forwarded-*, поэтому настоящий домен берётся из них.
 *
 * Framework-free (принимает обычный Headers, а не NextRequest), чтобы
 * логику можно было проверить node --test без импорта next/server.
 */
export function publicOrigin(headers: Headers, fallbackHost: string): string {
  const proto = headers.get("x-forwarded-proto") || "https";
  const host =
    headers.get("x-forwarded-host") ||
    headers.get("host") ||
    process.env.NEXT_PUBLIC_SITE_URL ||
    fallbackHost;
  return host.startsWith("http") ? host : `${proto}://${host}`;
}
