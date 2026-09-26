/**
 * Черновик условий от модели → форма договора в рабочем месте.
 *
 * Черновик заполняет только пустые поля: то, что юрист уже набрал или
 * подставил из заготовки, важнее предложения модели, и молча затирать это
 * нельзя. Чтобы получить предложение заново, поле достаточно очистить.
 */

import { AGREEMENT_FIELDS } from "./agreement-draft.ts";

export type TermsDraftResponse = {
  fields: Record<string, string>;
  amount_minor: number | null;
  template: { template_id: string; name: string } | null;
  notes: string[];
};

export type TermsDraftMerge = {
  values: Record<string, string>;
  /** Подписи полей, заполненных черновиком. */
  filled: string[];
  /** Подписи полей, где осталось набранное юристом. */
  kept: string[];
  /** Подписи полей, которые остались пустыми: стоимость и оплата без заготовки. */
  empty: string[];
};

const blank = (value: string | undefined) => !(value || "").trim();

export function mergeTermsDraft(
  current: Record<string, string>,
  draft: TermsDraftResponse,
): TermsDraftMerge {
  const values = { ...current };
  const filled: string[] = [];
  const kept: string[] = [];
  const empty: string[] = [];
  for (const field of AGREEMENT_FIELDS) {
    const proposed = String(draft.fields?.[field.key] ?? "").trim();
    if (!blank(current[field.key])) {
      if (proposed) kept.push(field.label);
      continue;
    }
    if (proposed) {
      values[field.key] = proposed.slice(0, field.max);
      filled.push(field.label);
    } else {
      empty.push(field.label);
    }
  }
  if (blank(current.amount) && typeof draft.amount_minor === "number" && draft.amount_minor >= 0) {
    values.amount = String(draft.amount_minor / 100);
  }
  return { values, filled, kept, empty };
}

/** Короткий итог под кнопкой: что сделано и что осталось юристу. */
export function termsDraftSummary(merge: TermsDraftMerge, template: TermsDraftResponse["template"]): string {
  if (merge.filled.length === 0) {
    return merge.kept.length
      ? "Все поля уже заполнены — очистите те, что хотите получить заново."
      : "Модель ничего не предложила — заполните форму сами.";
  }
  const parts = [`Заполнено: ${merge.filled.join(", ").toLowerCase()}.`];
  if (template) parts.push(`За основу взята заготовка «${template.name}».`);
  if (merge.empty.length) parts.push(`Укажите сами: ${merge.empty.join(", ").toLowerCase()}.`);
  if (merge.kept.length) parts.push(`Не тронуто набранное: ${merge.kept.join(", ").toLowerCase()}.`);
  parts.push("Проверьте всё перед тем, как составить договор.");
  return parts.join(" ");
}
