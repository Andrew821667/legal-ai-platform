/**
 * Шим над generic-модулем session-token.ts.
 *
 * Раньше HMAC-токен автономного входа был реализован прямо здесь и был
 * специфичен для юриста. С появлением личного кабинета клиента (та же схема,
 * свой секрет CLIENT_SESSION_SECRET, свой maxAge 7д) формат вынесен в
 * session-token.ts как generic mintSessionToken/verifySessionToken. Этот файл
 * остаётся, чтобы не трогать lawyer-auth.ts, lawyer-access.ts и существующие
 * тесты (lawyer-session-token.test.mjs, lawyer-auth.test.mjs) — они продолжают
 * импортировать прежние имена.
 */
export {
  mintSessionToken as mintLawyerSessionToken,
  verifySessionToken as verifyLawyerSessionToken,
  type SessionTokenResult,
} from "./session-token.ts";
