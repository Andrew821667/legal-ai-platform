"use client";

import { useState } from "react";

import { AGREEMENT_FIELDS } from "@/lib/agreement-draft";
import { formatRub, parseRublesInput } from "@/lib/money";
import { dropDraft, readDraft, writeDraft } from "./draft-storage";
import { lawyerAction } from "./useTelegram";

/**
 * Составление договора по обращению.
 *
 * До этого рабочее место умело сказать «условия ещё не предложены», но не
 * предложить их: мастер жил только в переписке с ботом, и юрист уходил
 * дописывать договор туда, откуда пришёл.
 *
 * Введённое сохраняется в браузере до отправки: шесть полей, набранных между
 * встречами, слишком дорого терять из-за случайного касания «Отмена».
 */

const draftKey = (intakeId: string) => `lawyer.agreement.${intakeId}`;

export default function AgreementForm({
  intakeId,
  initData,
  again,
  onCreated,
}: {
  intakeId: string;
  initData: string;
  again: boolean;
  onCreated: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [values, setValues] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const title = again ? "Составить новую редакцию" : "Составить договор";

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => {
          setValues(readDraft<Record<string, string>>(draftKey(intakeId), {}));
          setOpen(true);
        }}
        className="mt-3 w-full rounded-xl bg-amber-500 px-4 py-3 text-base font-medium text-slate-950 transition-colors hover:bg-amber-400"
      >
        {title}
      </button>
    );
  }

  const update = (key: string, text: string) => {
    const next = { ...values, [key]: text };
    // Сумма к учёту и формулировка в документе — две записи об одном. Пока
    // одна пуста, она подтягивается из другой: набрал «10 000» в стоимости —
    // сумма встала сама; набрал сумму — формулировка предложена.
    if (key === "price_text" && !(next.amount || "").trim()) {
      const parsed = parseRublesInput(text);
      if (parsed.ok && parsed.minor !== null) next.amount = String(parsed.minor / 100);
    }
    if (key === "amount" && !(next.price_text || "").trim()) {
      const parsed = parseRublesInput(text);
      if (parsed.ok && parsed.minor !== null) next.price_text = formatRub(parsed.minor);
    }
    setValues(next);
    writeDraft(draftKey(intakeId), next);
  };

  return (
    <form
      className="mt-3 space-y-3 rounded-xl border border-slate-800 bg-slate-950/60 p-3"
      onSubmit={async (event) => {
        event.preventDefault();
        setBusy(true);
        setError(null);
        try {
          await lawyerAction(`/api/lawyer/intakes/${intakeId}/agreement`, initData, values);
          dropDraft(draftKey(intakeId));
          setOpen(false);
          setValues({});
          onCreated();
        } catch (err) {
          setError(err instanceof Error ? err.message : "Не удалось составить договор");
        } finally {
          setBusy(false);
        }
      }}
    >
      <p className="text-base font-medium text-white">{title}</p>
      {again ? (
        <p className="text-sm text-amber-200">
          Прежняя редакция станет заменённой, как только новая будет составлена.
        </p>
      ) : null}

      {AGREEMENT_FIELDS.map((field) => (
        <div key={field.key}>
          <label className="block">
            <span className="text-sm text-slate-400">{field.label}</span>
            <textarea
              value={values[field.key] || ""}
              onChange={(event) => update(field.key, event.target.value)}
              rows={field.rows}
              placeholder={field.hint}
              className="mt-1 w-full rounded-xl border border-slate-700 bg-slate-950 p-3 text-base text-slate-100 placeholder:text-slate-400"
            />
          </label>
          {field.key === "price_text" ? (
            <label className="mt-2 block">
              <span className="text-sm text-slate-400">Сумма к учёту, ₽</span>
              <input
                inputMode="decimal"
                value={values.amount || ""}
                onChange={(event) => update("amount", event.target.value)}
                placeholder="10 000"
                className="mt-1 w-full rounded-xl border border-slate-700 bg-slate-950 p-3 text-base text-slate-100 placeholder:text-slate-400"
              />
              <span className="mt-1 block text-sm text-slate-400">
                Число для итогов. В документ уходит формулировка выше.
              </span>
            </label>
          ) : null}
        </div>
      ))}

      <p className="text-sm text-slate-400">
        Предложение будет действовать 7 дней. Договор появится черновиком — клиент
        увидит его только после отправки.
      </p>

      {error ? <p className="text-sm text-rose-300">{error}</p> : null}

      <div className="flex gap-2">
        <button
          type="submit"
          disabled={busy}
          className="flex-1 rounded-xl bg-amber-500 px-4 py-3 text-base font-medium text-slate-950 disabled:opacity-60"
        >
          {busy ? "Составляю…" : "Составить"}
        </button>
        <button
          type="button"
          onClick={() => setOpen(false)}
          className="rounded-xl bg-slate-800 px-4 py-3 text-base text-slate-200 hover:bg-slate-700"
        >
          Свернуть
        </button>
      </div>
    </form>
  );
}
