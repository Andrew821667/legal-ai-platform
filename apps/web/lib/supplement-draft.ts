/**
 * Допсоглашение к подписанному договору — что юрист вводит в рабочем месте.
 *
 * Ограничения повторяют схему ядра (`SupplementCreate`), как и у договора:
 * иначе юрист получил бы разбор Pydantic на английском вместо подсказки.
 * Сроки и оплата необязательны — пустые значат «как в договоре», и так и
 * написано в документе.
 */

import { parseRublesInput } from "./money.ts";

export type SupplementField = {
  key: string;
  label: string;
  hint: string;
  min: number;
  max: number;
  rows: number;
};

export const SUPPLEMENT_FIELDS: readonly SupplementField[] = [
  {
    key: "scope_text",
    label: "Дополнительные работы",
    hint: "Что добавляется к договору",
    min: 10,
    max: 6000,
    rows: 4,
  },
  {
    key: "schedule_text",
    label: "Сроки",
    hint: "Сроки дополнительных работ; пусто — как в договоре",
    min: 0,
    max: 2000,
    rows: 2,
  },
  {
    key: "price_text",
    label: "Новая стоимость по договору",
    hint: "Общая стоимость с учётом дополнительных работ",
    min: 2,
    max: 500,
    rows: 1,
  },
  {
    key: "payment_terms",
    label: "Оплата",
    hint: "Например, доплата в течение 5 дней; пусто — как в договоре",
    min: 0,
    max: 2000,
    rows: 2,
  },
];

export type SupplementCheck =
  | { ok: true; value: Record<string, string | number> }
  | { ok: false; detail: string };

export function checkSupplementDraft(input: Record<string, unknown>): SupplementCheck {
  const value: Record<string, string | number> = {};
  for (const field of SUPPLEMENT_FIELDS) {
    const text = String(input[field.key] ?? "").trim();
    if (text.length < field.min) {
      return {
        ok: false,
        detail:
          field.min > 2
            ? `«${field.label}»: нужно не меньше ${field.min} символов.`
            : `Заполните «${field.label}».`,
      };
    }
    if (text.length > field.max) {
      return { ok: false, detail: `«${field.label}»: не больше ${field.max} символов.` };
    }
    if (text) value[field.key] = text;
  }
  // Новая общая стоимость — ради неё допсоглашение и составляется: после
  // подписи клиента это число становится суммой договора. Без него нечего
  // переносить в итоги.
  const amount = parseRublesInput(input.amount);
  if (!amount.ok) return { ok: false, detail: amount.detail };
  if (amount.minor === null) {
    return { ok: false, detail: "Укажите новую общую стоимость числом — она станет суммой договора." };
  }
  value.amount_minor = amount.minor;
  return { ok: true, value };
}
