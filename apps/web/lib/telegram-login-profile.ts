/**
 * Единый интерфейс «проверенный профиль Telegram» — общая точка, в которую
 * сходятся два разных механизма подтверждения личности (OIDC id_token и
 * legacy-виджет). Дальше по стеку (mint сессии, кабинет) режим входа уже не
 * важен: и establish-session.ts, и весь /cabinet работают с одним и тем же
 * TelegramLoginProfile независимо от того, как он получен.
 */

export type TelegramLoginProfile = {
  telegramUserId: number;
  firstName: string;
  lastName?: string;
  username?: string;
  photoUrl?: string;
  /** "+" и только цифры. Только у OIDC при согласии на scope phone. */
  phone?: string;
  /** true только когда Telegram подтвердил phone (OIDC). У legacy всегда false. */
  phoneVerified: boolean;
  method: "oidc" | "legacy";
};

export type ClientProfileCookie = {
  fn: string;
  ln?: string;
  un?: string;
  photo?: string;
  phoneMasked?: string;
  method: "oidc" | "legacy";
};

function safeInt(value: unknown): number | null {
  const num = typeof value === "number" ? value : Number(value);
  return Number.isSafeInteger(num) && num > 0 ? num : null;
}

function normalizePhone(raw: unknown): string | undefined {
  if (typeof raw !== "string") return undefined;
  const digits = raw.replace(/[^\d]/g, "");
  return digits.length >= 10 ? `+${digits}` : undefined;
}

function splitName(name: string): { firstName: string; lastName?: string } {
  const trimmed = name.trim();
  if (!trimmed) return { firstName: "" };
  const spaceIndex = trimmed.indexOf(" ");
  if (spaceIndex === -1) return { firstName: trimmed };
  return { firstName: trimmed.slice(0, spaceIndex), lastName: trimmed.slice(spaceIndex + 1).trim() || undefined };
}

/**
 * claims_supported у oauth.telegram.org не перечисляет given_name/family_name
 * и id — маппинг защитный: предпочитаем given_name/family_name, но при их
 * отсутствии разбираем name; sub — основной источник id, id — запасной.
 */
export function profileFromIdTokenClaims(claims: Record<string, unknown>): TelegramLoginProfile | null {
  const telegramUserId = safeInt(claims.sub) ?? safeInt(claims.id);
  if (telegramUserId === null) return null;

  const givenName = typeof claims.given_name === "string" ? claims.given_name.trim() : "";
  const familyName = typeof claims.family_name === "string" ? claims.family_name.trim() : "";
  const fromName = typeof claims.name === "string" ? splitName(claims.name) : { firstName: "" };

  const firstName = givenName || fromName.firstName;
  const lastName = familyName || fromName.lastName;

  const phone = normalizePhone(claims.phone_number);
  const phoneVerified = Boolean(phone) && claims.phone_number_verified !== false;

  return {
    telegramUserId,
    firstName,
    lastName,
    username: typeof claims.preferred_username === "string" ? claims.preferred_username : undefined,
    photoUrl: typeof claims.picture === "string" ? claims.picture : undefined,
    phone,
    phoneVerified,
    method: "oidc",
  };
}

/** params уже проверены verifyTelegramLoginWidget — здесь только маппинг полей. */
export function profileFromWidgetParams(params: URLSearchParams): TelegramLoginProfile {
  return {
    telegramUserId: Number(params.get("id")),
    firstName: (params.get("first_name") || "").trim(),
    lastName: params.get("last_name")?.trim() || undefined,
    username: params.get("username")?.trim() || undefined,
    photoUrl: params.get("photo_url")?.trim() || undefined,
    phoneVerified: false,
    method: "legacy",
  };
}

function maskPhone(phone: string): string {
  const digits = phone.replace(/[^\d]/g, "");
  if (digits.length < 4) return "+•••";
  return `+${"•".repeat(Math.max(digits.length - 4, 3))}${digits.slice(-4)}`;
}

export function toProfileCookie(profile: TelegramLoginProfile): ClientProfileCookie {
  return {
    fn: profile.firstName,
    ln: profile.lastName,
    un: profile.username,
    photo: profile.photoUrl,
    phoneMasked: profile.phone ? maskPhone(profile.phone) : undefined,
    method: profile.method,
  };
}
