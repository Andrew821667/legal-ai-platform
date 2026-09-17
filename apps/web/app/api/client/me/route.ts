import { NextRequest, NextResponse } from "next/server";

import { requireClient } from "@/lib/client-auth";
import { CLIENT_PROFILE_COOKIE, CLIENT_SESSION_MAX_AGE_SECONDS, clientSessionSecret } from "@/lib/client-session";
import { openCookieValue } from "@/lib/signed-cookie";
import type { ClientProfileCookie } from "@/lib/telegram-login-profile";

export const dynamic = "force-dynamic";

/**
 * Мягкая проверка входа — для бейджа в чате ассистента и prefill формы
 * «Передать задачу». В отличие от остальных /api/client/*, отсутствие
 * сессии здесь не ошибка: страница/виджет просто показывает анонимный вид.
 */
export async function GET(request: NextRequest) {
  const auth = requireClient(request);
  if (auth instanceof NextResponse) {
    return NextResponse.json({ signed_in: false });
  }

  let profile: ClientProfileCookie | null = null;
  if (auth.via === "cookie") {
    const secret = clientSessionSecret();
    const raw = request.cookies.get(CLIENT_PROFILE_COOKIE)?.value || "";
    profile = secret ? openCookieValue<ClientProfileCookie>(raw, secret, CLIENT_SESSION_MAX_AGE_SECONDS) : null;
  }

  return NextResponse.json({
    signed_in: true,
    telegram_user_id: auth.telegramUserId,
    via: auth.via,
    profile: profile
      ? {
          first_name: profile.fn,
          last_name: profile.ln ?? null,
          username: profile.un ?? null,
          photo_url: profile.photo ?? null,
        }
      : null,
  });
}
