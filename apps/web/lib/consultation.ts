/**
 * Запись на платную консультацию — логика без React: время по Москве,
 * группировка по дням, разбор времени, которое открывает юрист, и тексты
 * статусов брони. Компоненты только рисуют.
 */

export const BOOKING_TOKEN = /^[A-Za-z0-9_-]{20,64}$/;

export type FreeSlot = { slot_id: string; starts_at: string; duration_min: number };

export type BookingStatus = "held" | "claimed" | "confirmed";

export type Booking = {
  slot_id: string;
  starts_at: string;
  duration_min: number;
  status: BookingStatus;
  price_minor: number | null;
  code: string | null;
  held_until: string | null;
  payment?: boolean;
};

const TZ = "Europe/Moscow";

export function dayKey(iso: string): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: TZ }).format(new Date(iso));
}

export function dayLabel(iso: string): string {
  const label = new Intl.DateTimeFormat("ru-RU", { timeZone: TZ, weekday: "short", day: "numeric", month: "long" }).format(
    new Date(iso),
  );
  // «Вс, 27 сентября»: заглавная только первая буква (CSS capitalize сделал бы «Сентября»).
  return label.charAt(0).toUpperCase() + label.slice(1);
}

export function timeLabel(iso: string): string {
  return new Intl.DateTimeFormat("ru-RU", { timeZone: TZ, hour: "2-digit", minute: "2-digit" }).format(new Date(iso));
}

export function whenLabel(iso: string): string {
  return `${dayLabel(iso)}, ${timeLabel(iso)} (МСК)`;
}

/** Свободное время по дням, дни и время по порядку. */
export function groupByDay(slots: FreeSlot[]): { day: string; label: string; slots: FreeSlot[] }[] {
  const groups = new Map<string, FreeSlot[]>();
  for (const slot of [...slots].sort((a, b) => a.starts_at.localeCompare(b.starts_at))) {
    const key = dayKey(slot.starts_at);
    groups.set(key, [...(groups.get(key) || []), slot]);
  }
  return [...groups.entries()].map(([day, items]) => ({ day, label: dayLabel(items[0].starts_at), slots: items }));
}

/** «10:00, 11:30 15» → ["10:00", "11:30", "15:00"]: без повторов, по порядку, только настоящее время. */
export function parseTimes(raw: string): string[] {
  const found = new Set<string>();
  for (const part of raw.split(/[\s,;]+/)) {
    const match = /^(\d{1,2})(?:[:.](\d{2}))?$/.exec(part.trim());
    if (!match) continue;
    const hours = Number(match[1]);
    const minutes = Number(match[2] || "0");
    if (hours > 23 || minutes > 59) continue;
    found.add(`${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}`);
  }
  return [...found].sort();
}

/** Дата «2026-10-01» и время «15:00» по Москве → ISO со смещением +03:00. */
export function moscowStarts(date: string, times: string[]): string[] {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) return [];
  return times.map((time) => `${date}T${time}:00+03:00`);
}

export function minutesLeft(heldUntil: string | null, now: Date = new Date()): number {
  if (!heldUntil) return 0;
  return Math.max(0, Math.ceil((new Date(heldUntil).getTime() - now.getTime()) / 60_000));
}

export function statusText(booking: Booking, now: Date = new Date()): string {
  switch (booking.status) {
    case "held": {
      const left = minutesLeft(booking.held_until, now);
      return left
        ? `Время закреплено за вами ещё ${left} мин. Оплатите и нажмите «Я оплатил».`
        : "Время бронирования истекло.";
    }
    case "claimed":
      return "Вы сообщили об оплате. Юрист сверит поступление и подтвердит запись — обычно в течение рабочего дня.";
    case "confirmed":
      return "Оплата получена, консультация подтверждена. Юрист свяжется с вами по контакту из заявки перед началом.";
  }
}
