/**
 * Деньги в рабочем месте: копейки в базе, рубли на экране.
 *
 * Хранится целое число копеек — с ним складывать безопасно. На экране —
 * «10 000 ₽»: без разделителя разрядов «10000 руб» в инструменте, где на кону
 * реальные деньги клиентов, читается как черновик.
 */

export function formatRub(minor: number | null | undefined): string {
  if (minor === null || minor === undefined) return "—";
  const rubles = Math.trunc(minor / 100);
  const kopecks = Math.abs(minor % 100);
  const whole = new Intl.NumberFormat("ru-RU").format(rubles).replace(/ /g, " ");
  return kopecks ? `${whole},${String(kopecks).padStart(2, "0")} ₽` : `${whole} ₽`;
}

export type RublesCheck = { ok: true; minor: number | null } | { ok: false; detail: string };

/**
 * Разбирает то, что юрист набрал в поле суммы: «10 000», «10000,50», «10 000 ₽».
 * Пусто — это «не указана», а не ноль.
 */
export function parseRublesInput(input: unknown): RublesCheck {
  const raw = String(input ?? "").trim();
  if (!raw) return { ok: true, minor: null };
  const cleaned = raw.replace(/[\s ]/g, "").replace(/₽|руб\.?|р\.?$/i, "");
  const match = /^(\d+)(?:[.,](\d{1,2}))?$/.exec(cleaned);
  if (!match) {
    return { ok: false, detail: "Сумма — это число: например, 10 000 или 12 500,50." };
  }
  const rubles = Number(match[1]);
  const kopecks = Number((match[2] || "0").padEnd(2, "0"));
  if (rubles > 100_000_000_000) {
    return { ok: false, detail: "Сумма слишком велика." };
  }
  return { ok: true, minor: rubles * 100 + kopecks };
}
