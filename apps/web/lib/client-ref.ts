/**
 * Кто клиент — в виде параметров для ядра.
 *
 * Клиент приходит либо с Telegram (мини-апп, вход через Telegram), либо с
 * учётной записью (вход через Яндекс ID). Ядро принимает одно из двух:
 * telegram_user_id или client_account_id (core_api/client_principal.py).
 */

export type ClientIdentity = { telegramUserId: number | null; accountId: string | null };

export function clientFields(ctx: ClientIdentity): { telegram_user_id: number } | { client_account_id: string } {
  if (ctx.telegramUserId !== null) return { telegram_user_id: ctx.telegramUserId };
  if (ctx.accountId) return { client_account_id: ctx.accountId };
  throw new Error("client identity is empty");
}

export function clientQuery(ctx: ClientIdentity): string {
  const fields = clientFields(ctx);
  return "telegram_user_id" in fields
    ? `telegram_user_id=${fields.telegram_user_id}`
    : `client_account_id=${encodeURIComponent(fields.client_account_id)}`;
}

/** Ключ для лимитов: не пересекается между Telegram и учётными записями. */
export function clientKey(ctx: ClientIdentity): string {
  return ctx.telegramUserId !== null ? `tg:${ctx.telegramUserId}` : `acc:${ctx.accountId}`;
}
