/**
 * Заготовка условий договора ⇄ поля формы договора в рабочем месте.
 *
 * Сумма в заготовке — копейки, в форме — рубли строкой, как их вводит юрист.
 */

import { AGREEMENT_FIELDS } from "./agreement-draft.ts";
import { parseRublesInput } from "./money.ts";

export type AgreementTemplate = {
  template_id: string;
  name: string;
  practice: string | null;
  subject: string;
  scope_text: string;
  exclusions_text: string;
  schedule_text: string;
  price_text: string;
  amount_minor: number | null;
  payment_terms: string;
  use_count: number;
  /** Пакет услуг сайта, под который заготовка; null — ни под какой. */
  package_id?: string | null;
};

/** Поля формы из заготовки: все условия и сумма к учёту. */
export function templateToDraft(template: AgreementTemplate): Record<string, string> {
  const draft: Record<string, string> = {};
  for (const field of AGREEMENT_FIELDS) {
    draft[field.key] = String((template as unknown as Record<string, unknown>)[field.key] ?? "");
  }
  draft.amount = template.amount_minor === null ? "" : String(template.amount_minor / 100);
  return draft;
}

export type TemplateCheck =
  | { ok: true; value: Record<string, unknown> }
  | { ok: false; detail: string };

/** Тело запроса на сохранение заготовки из того, что сейчас в форме. */
export function draftToTemplate(
  values: Record<string, string>,
  name: string,
  practice: string | null,
  packageId: string | null = null,
): TemplateCheck {
  const title = name.trim();
  if (title.length < 2) return { ok: false, detail: "Назовите заготовку — хотя бы два символа." };
  const amount = parseRublesInput(values.amount);
  if (!amount.ok) return { ok: false, detail: amount.detail };
  const value: Record<string, unknown> = {
    name: title.slice(0, 120),
    practice,
    amount_minor: amount.minor,
    package_id: packageId || null,
  };
  let filled = 0;
  for (const field of AGREEMENT_FIELDS) {
    const text = String(values[field.key] ?? "").trim().slice(0, field.max);
    if (text) filled += 1;
    value[field.key] = text;
  }
  if (filled === 0) return { ok: false, detail: "В форме пусто — сохранять нечего." };
  return { ok: true, value };
}

/** Тело PUT: заготовка как есть, меняется только привязка к пакету сайта. */
export function templateWithPackage(template: AgreementTemplate, packageId: string | null): Record<string, unknown> {
  const body: Record<string, unknown> = {
    name: template.name,
    practice: template.practice,
    amount_minor: template.amount_minor,
    package_id: packageId || null,
  };
  for (const field of AGREEMENT_FIELDS) {
    body[field.key] = String((template as unknown as Record<string, unknown>)[field.key] ?? "");
  }
  return body;
}
