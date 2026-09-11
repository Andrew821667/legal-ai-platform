"use client";

import { useState } from "react";

import { lawyerAction } from "./useTelegram";

/**
 * Срок по обращению: слова клиента и дата рядом.
 *
 * Раньше срок существовал только текстом — клиент дважды написал «к этому
 * четвергу», система это записала и на этом всё: ни напомнить, ни отсортировать.
 * Слова остаются как есть, а дату юрист ставит сам: разобрать «четверг» в
 * календарную точку за него значит угадать процессуальный срок.
 */

function inputValue(iso: string | null): string {
  return iso ? iso.slice(0, 10) : "";
}

export default function DeadlineBox({
  intakeId,
  deadlineAt,
  clientWords,
  initData,
  onChanged,
}: {
  intakeId: string;
  deadlineAt: string | null;
  clientWords: string | null;
  initData: string;
  onChanged: () => void;
}) {
  const [value, setValue] = useState(inputValue(deadlineAt));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const save = async (next: string) => {
    setValue(next);
    setBusy(true);
    setError(null);
    try {
      await lawyerAction(`/api/lawyer/intakes/${intakeId}/deadline`, initData, {
        deadline_at: next || null,
      });
      onChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось сохранить срок");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mt-3 border-t border-lw-border pt-3">
      <div className="flex items-center gap-3">
        <span className="text-lw-sm text-lw-muted">Срок</span>
        <input
          type="date"
          value={value}
          disabled={busy}
          onChange={(event) => void save(event.target.value)}
          className="lw-input !w-auto !py-2 disabled:opacity-60"
        />
        {value ? (
          <button
            type="button"
            disabled={busy}
            onClick={() => void save("")}
            className="text-lw-sm text-lw-muted underline underline-offset-2 hover:text-lw-primary"
          >
            снять
          </button>
        ) : null}
      </div>

      {clientWords ? (
        <p className="mt-1.5 text-lw-sm text-lw-muted">Со слов клиента: «{clientWords}»</p>
      ) : null}
      {error ? <p className="mt-1 text-lw-sm text-lw-danger">{error}</p> : null}
    </div>
  );
}
