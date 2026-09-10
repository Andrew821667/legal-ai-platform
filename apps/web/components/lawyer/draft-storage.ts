/**
 * Несохранённый ввод переживает уход с экрана.
 *
 * Текст, набранный между встречами, пропадал молча: свернул форму, промахнулся
 * пальцем по «К списку» — и написанного нет, без предупреждения и без следа.
 * Хранится у того, кто печатал, и только до отправки.
 */

export function readDraft<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    return raw === null ? fallback : (JSON.parse(raw) as T);
  } catch {
    // Приватный режим, переполненное или отключённое хранилище — форма
    // должна открыться в любом случае, просто пустой.
    return fallback;
  }
}

export function writeDraft(key: string, value: unknown): void {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // см. readDraft
  }
}

export function dropDraft(key: string): void {
  try {
    localStorage.removeItem(key);
  } catch {
    // см. readDraft
  }
}
