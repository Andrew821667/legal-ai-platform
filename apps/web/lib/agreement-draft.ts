/**
 * Черновик договора, который юрист составляет в рабочем месте.
 *
 * Ограничения полей повторяют схему ядра (`AgreementCreate`): расхождение
 * здесь означало бы, что юрист заполняет форму, жмёт «Составить» и получает
 * в ответ разбор Pydantic на английском вместо понятной подсказки. Список
 * полей и порядок — те же, что в мастере бота, чтобы два входа в один и тот
 * же документ не спрашивали разное.
 */

export type AgreementField = {
  key: string;
  label: string;
  hint: string;
  min: number;
  max: number;
  rows: number;
};

export const AGREEMENT_FIELDS: readonly AgreementField[] = [
  {
    key: "subject",
    label: "Предмет",
    hint: "Вопрос, по которому заключается договор",
    min: 10,
    max: 4000,
    rows: 2,
  },
  {
    key: "scope_text",
    label: "Что входит",
    hint: "Что именно входит в работу",
    min: 10,
    max: 6000,
    rows: 4,
  },
  {
    key: "exclusions_text",
    label: "Не входит",
    hint: "Что не делается без отдельного согласования",
    min: 2,
    max: 2000,
    rows: 2,
  },
  {
    key: "schedule_text",
    label: "Сроки",
    hint: "Сроки и этапы работы",
    min: 2,
    max: 2000,
    rows: 2,
  },
  {
    key: "price_text",
    label: "Стоимость",
    hint: "Полная стоимость услуг в рублях",
    min: 2,
    max: 500,
    rows: 1,
  },
  {
    key: "payment_terms",
    label: "Оплата",
    hint: "Порядок и сроки оплаты",
    min: 2,
    max: 2000,
    rows: 2,
  },
];

export type DraftCheck =
  | { ok: true; value: Record<string, string> }
  | { ok: false; detail: string };

export function checkAgreementDraft(input: Record<string, unknown>): DraftCheck {
  const value: Record<string, string> = {};
  for (const field of AGREEMENT_FIELDS) {
    const text = String(input[field.key] ?? "").trim();
    if (text.length < field.min) {
      return {
        ok: false,
        detail: `«${field.label}»: нужно не меньше ${field.min} символов.`,
      };
    }
    if (text.length > field.max) {
      return {
        ok: false,
        detail: `«${field.label}»: не больше ${field.max} символов.`,
      };
    }
    value[field.key] = text;
  }
  return { ok: true, value };
}
