import { parseAllowedIds } from "./lawyer-access.ts";

/**
 * Администратор (юрист практики) в личном кабинете клиента.
 *
 * Кабинет — для клиентов: NDA, паспорт, реквизиты договора. Владелец, вошедший
 * сюда через Telegram или через Яндекс ID с привязанным Telegram, — не клиент:
 * его опознаём по тому же списку, что пускает в рабочее место юриста
 * (ADMIN_TELEGRAM_ID, LAWYER_TELEGRAM_IDS), и клиентских форм не показываем.
 * Доступа к рабочему месту это не даёт — туда по-прежнему вход из бота.
 */
export function staffTelegramIds(env: Record<string, string | undefined> = process.env): number[] {
  return parseAllowedIds(env.ADMIN_TELEGRAM_ID, env.LAWYER_TELEGRAM_IDS);
}

export function isStaffTelegramId(telegramUserId: number | null | undefined, staff: number[] = staffTelegramIds()): boolean {
  return typeof telegramUserId === "number" && staff.includes(telegramUserId);
}
