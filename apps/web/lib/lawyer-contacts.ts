/**
 * Контакты клиента для шапки карточки.
 *
 * У лида три поля — «контакт», телефон, email, — и часто это одно и то же
 * значение, записанное дважды (клиент оставил email, он же стал контактом).
 * Показываем каждое один раз и делаем ссылкой то, что распознаётся: письмо,
 * звонок, чат в Telegram. Карточку открывают перед разговором с клиентом —
 * контакт здесь нужен, чтобы по нему сразу написать, а не переписывать.
 */

export type ContactLink = { value: string; href: string | null };

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const PHONE = /^\+?[\d\s()-]{7,}$/;
const HANDLE = /^@[A-Za-z0-9_]{4,}$/;

export function contactHref(value: string): string | null {
  const trimmed = value.trim();
  if (EMAIL.test(trimmed)) return `mailto:${trimmed}`;
  if (HANDLE.test(trimmed)) return `https://t.me/${trimmed.slice(1)}`;
  if (PHONE.test(trimmed)) return `tel:${trimmed.replace(/[\s()-]/g, "")}`;
  return null;
}

/** Ключ для склейки дублей: регистр и разделители в телефоне не считаются. */
function contactKey(value: string): string {
  return value.toLowerCase().replace(/[\s()-]/g, "");
}

export function clientContacts(card: {
  contact: string | null;
  phone: string | null;
  email: string | null;
  telegram_user_id: number | null;
}): ContactLink[] {
  const result: ContactLink[] = [];
  const seen = new Set<string>();
  for (const raw of [card.contact, card.phone, card.email]) {
    const value = (raw || "").trim();
    if (!value || seen.has(contactKey(value))) continue;
    seen.add(contactKey(value));
    result.push({ value, href: contactHref(value) });
  }
  // Клиент из бота может не оставить ни телефона, ни @имени — но чат с ним
  // есть всегда: Telegram открывает профиль по идентификатору.
  if (card.telegram_user_id && !result.some((item) => item.href?.startsWith("https://t.me/"))) {
    result.push({ value: "Чат в Telegram", href: `tg://user?id=${card.telegram_user_id}` });
  }
  return result;
}
