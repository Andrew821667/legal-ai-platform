"use client";

import { useState } from "react";

import { AGREEMENT_FIELDS } from "@/lib/agreement-draft";
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

const STORAGE_PREFIX = "lawyer.agreement.";

function readDraft(intakeId: string): Record<string, string> {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_PREFIX + intakeId) || "{}");
  } catch {
    return {};
  }
}

function writeDraft(intakeId: string, values: Record<string, string>) {
  try {
    localStorage.setItem(STORAGE_PREFIX + intakeId, JSON.stringify(values));
  } catch {
    // Приватный режим или переполненное хранилище — не повод ломать форму.
  }
}

function dropDraft(intakeId: string) {
  try {
    localStorage.removeItem(STORAGE_PREFIX + intakeId);
  } catch {
    // см. writeDraft
  }
}

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
          setValues(readDraft(intakeId));
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
    setValues(next);
    writeDraft(intakeId, next);
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
          dropDraft(intakeId);
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
        <label key={field.key} className="block">
          <span className="text-sm text-slate-400">{field.label}</span>
          <textarea
            value={values[field.key] || ""}
            onChange={(event) => update(field.key, event.target.value)}
            rows={field.rows}
            placeholder={field.hint}
            className="mt-1 w-full rounded-xl border border-slate-700 bg-slate-950 p-3 text-base text-slate-100 placeholder:text-slate-500"
          />
        </label>
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
