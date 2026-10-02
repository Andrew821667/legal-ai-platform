import { NextRequest, NextResponse } from "next/server";

import { checkLawyerSessionCookie } from "@/lib/lawyer-access";
import { LAWYER_SESSION_COOKIE, allowedLawyerIds, lawyerSessionSecret } from "@/lib/lawyer-auth";
import { corePost } from "@/lib/lawyer-core";
import { verifyLawyerLoginToken } from "@/lib/lawyer-login-token";
import { mintLawyerSessionToken } from "@/lib/lawyer-session-token";
import { publicOrigin } from "@/lib/public-origin";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

/**
 * Автономный вход: ссылку сюда даёт только бот (кнопка в /admin и нижняя
 * кнопка «Рабочее пространство») — с одноразовым токеном входа
 * (lib/lawyer-login-token.ts). Здесь он проверяется, гасится в ядре и
 * меняется на httpOnly-куку сессии на 30 дней; сама кука в адресе не
 * бывает. Повторно та же ссылка не сработает.
 *
 * Если кука уже есть и действует — ссылку не гасим, просто пускаем: нижняя
 * кнопка Telegram открывает один и тот же адрес до следующего /admin.
 */
export async function GET(request: NextRequest) {
  const origin = publicOrigin(request.headers, request.nextUrl.host);
  const toWorkspace = (reason?: string) =>
    NextResponse.redirect(new URL(reason ? `/lawyer?login=${reason}` : "/lawyer", origin));
  const secret = lawyerSessionSecret();
  const allowedIds = allowedLawyerIds();
  if (!secret) {
    return NextResponse.json({ detail: "Сервер не настроен: нет секрета автономного входа" }, { status: 500 });
  }

  const existing = checkLawyerSessionCookie({
    cookie: request.cookies.get(LAWYER_SESSION_COOKIE)?.value || "",
    secret,
    allowedIds,
  });
  if (existing.ok) return toWorkspace();

  // Сюда приходят и из нижней кнопки Telegram: голый JSON в WebView
  // нечитаем. Рабочее место покажет, что делать, — обычно отправить /admin.
  const token = verifyLawyerLoginToken(request.nextUrl.searchParams.get("token") || "", secret);
  if (!token) return toWorkspace("stale");
  if (!allowedIds.includes(token.telegramUserId)) return toWorkspace("denied");

  const consumed = await corePost("/api/v1/lawyer/login-nonces", {
    nonce: token.nonce,
    telegram_user_id: token.telegramUserId,
    expires_at: new Date(token.expiresAt * 1000).toISOString(),
  });
  if (consumed.status === 409) return toWorkspace("used");
  if (!consumed.ok) return toWorkspace("unavailable");

  const response = toWorkspace();
  response.cookies.set(LAWYER_SESSION_COOKIE, mintLawyerSessionToken(token.telegramUserId, secret), {
    httpOnly: true,
    secure: true,
    sameSite: "lax",
    path: "/",
    // Не короче срока, который проверяет сервер на каждый запрос (30 дней):
    // токен всё равно будет отклонён после этого срока, здесь — только чтобы
    // браузер не выбросил куку раньше сервера.
    maxAge: 30 * 24 * 60 * 60,
  });
  return response;
}
