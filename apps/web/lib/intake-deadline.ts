/**
 * Срок по обращению, который проставляет юрист.
 *
 * С экрана приходит календарный день («2026-09-17»), а хранится момент
 * времени. Берём конец дня, а не полночь: срок «к 17-му» весь семнадцатый
 * день ещё не нарушен, а от полуночи счётчик показывал бы «просрочено» с
 * самого утра того дня, когда работать ещё можно.
 *
 * Часовой пояс — UTC. Практика в Москве, то есть запас получается на три часа
 * больше календарного дня; для напоминания это безобиднее, чем срезать вечер.
 */

const DAY = /^(\d{4})-(\d{2})-(\d{2})$/;

export type DeadlineCheck =
  | { ok: true; value: string | null }
  | { ok: false; detail: string };

export function normalizeDeadline(input: unknown): DeadlineCheck {
  if (input === null || input === undefined || input === "") {
    return { ok: true, value: null };
  }
  const match = DAY.exec(String(input));
  if (!match) {
    return { ok: false, detail: "Срок указывается датой в формате ГГГГ-ММ-ДД." };
  }
  const [, year, month, day] = match;
  const parsed = new Date(`${year}-${month}-${day}T00:00:00Z`);
  // Отсекает 31 февраля и подобное: Date такие даты молча переносит вперёд.
  if (
    Number.isNaN(parsed.getTime()) ||
    parsed.getUTCFullYear() !== Number(year) ||
    parsed.getUTCMonth() + 1 !== Number(month) ||
    parsed.getUTCDate() !== Number(day)
  ) {
    return { ok: false, detail: "Такой даты не существует." };
  }
  return { ok: true, value: `${year}-${month}-${day}T23:59:59Z` };
}
