import { NextRequest, NextResponse } from "next/server";

import { establishClientSession } from "../_lib/establish-session";
import { CLIENT_OAUTH_COOKIE, CLIENT_OAUTH_MAX_AGE_SECONDS, clientSessionSecret } from "@/lib/client-session";
import { publicOrigin } from "@/lib/public-origin";
import { openCookieValue } from "@/lib/signed-cookie";
import { exchangeCode, verifyIdToken } from "@/lib/telegram-login-oidc";
import { profileFromIdTokenClaims } from "@/lib/telegram-login-profile";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

type OauthCookiePayload = { state: string; nonce: string; verifier: string; next: string };

function denyTo(origin: string, reason: string): NextResponse {
  const response = NextResponse.redirect(new URL(`/cabinet?login=${reason}`, origin));
  // Кука обмена — одноразовая: неудачная попытка не должна оставлять её
  // валидной для повторной атаки тем же state/verifier.
  response.cookies.set(CLIENT_OAUTH_COOKIE, "", { httpOnly: true, secure: true, sameSite: "lax", path: "/cabinet", maxAge: 0 });
  return response;
}

export async function GET(request: NextRequest) {
  const origin = publicOrigin(request.headers, request.nextUrl.host);
  const params = request.nextUrl.searchParams;

  if (params.get("error")) {
    return denyTo(origin, "denied");
  }

  const code = params.get("code") || "";
  const state = params.get("state") || "";
  if (!code || !state) {
    return denyTo(origin, "state");
  }

  const cookieSecret = clientSessionSecret();
  if (!cookieSecret) {
    return denyTo(origin, "misconfigured");
  }

  const oauthCookie = openCookieValue<OauthCookiePayload>(
    request.cookies.get(CLIENT_OAUTH_COOKIE)?.value || "",
    cookieSecret,
    CLIENT_OAUTH_MAX_AGE_SECONDS,
  );
  if (!oauthCookie || oauthCookie.state !== state) {
    return denyTo(origin, "state");
  }

  const clientId = (process.env.TELEGRAM_OAUTH_CLIENT_ID || "").trim();
  const clientSecret = (process.env.TELEGRAM_OAUTH_CLIENT_SECRET || "").trim();
  if (!clientId || !clientSecret) {
    return denyTo(origin, "misconfigured");
  }
  const redirectUri =
    (process.env.TELEGRAM_OAUTH_REDIRECT_URI || "").trim() || `${origin}/cabinet/callback`;

  let idToken: string;
  try {
    const exchanged = await exchangeCode({
      code,
      redirectUri,
      codeVerifier: oauthCookie.verifier,
      clientId,
      clientSecret,
    });
    idToken = exchanged.idToken;
  } catch (error) {
    // eslint-disable-next-line no-console
    console.error("Telegram OAuth: обмен кода на токен не удался:", (error as Error).message);
    return denyTo(origin, "exchange");
  }

  let claims: Awaited<ReturnType<typeof verifyIdToken>>;
  try {
    claims = await verifyIdToken(idToken, { audience: clientId, nonce: oauthCookie.nonce });
  } catch (error) {
    // eslint-disable-next-line no-console
    console.error("Telegram OAuth: id_token не прошёл проверку:", (error as Error).message);
    return denyTo(origin, "token");
  }

  const profile = profileFromIdTokenClaims(claims);
  if (!profile) {
    return denyTo(origin, "profile");
  }

  return establishClientSession(profile, request, oauthCookie.next || "/cabinet");
}
