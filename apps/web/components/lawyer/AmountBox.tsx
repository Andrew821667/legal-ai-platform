"use client";

import { useState } from "react";

import { formatRub } from "@/lib/money";
import { lawyerAction } from "./useTelegram";

/**
 * Сумма к учёту у договора.
 *
 * Отдельно от формулировки в документе: «10 тысяч» и «10000 руб» в двух
 * редакциях одного договора складывать нельзя, а число без формулировки в
 * договор не положить. Договоры, составленные до появления числа, здесь же и
 * дозаполняются — иначе итоги молча неполные.
 */
export default function AmountBox({
  agreementId,
  amountMinor,
  initData,
  onChanged,
}: {
  agreementId: string;
  amountMinor: number | null;
  initData: string;
  onChanged: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!editing) {
    return (
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 py-1.5 text-lw-sm">
        <span className="w-32 shrink-0 text-lw-muted">Сумма к учёту</span>
        {amountMinor === null ? (
          <span className="text-lw-warning">не указана — в итоги не попадает</span>
        ) : (
          <span className="font-medium text-lw-ink">{formatRub(amountMinor)}</span>
        )}
        <button
          type="button"
          onClick={() => {
            setValue(amountMinor === null ? "" : String(amountMinor / 100));
            setEditing(true);
          }}
          className="text-lw-muted underline underline-offset-2 hover:text-lw-primary"
        >
          {amountMinor === null ? "указать" : "изменить"}
        </button>
      </div>
    );
  }

  return (
    <form
      className="flex flex-wrap items-center gap-2 py-1.5"
      onSubmit={async (event) => {
        event.preventDefault();
        setBusy(true);
        setError(null);
        try {
          await lawyerAction(`/api/lawyer/agreements/${agreementId}/amount`, initData, {
            amount: value,
          });
          setEditing(false);
          onChanged();
        } catch (err) {
          setError(err instanceof Error ? err.message : "Не удалось сохранить");
        } finally {
          setBusy(false);
        }
      }}
    >
      <span className="w-32 shrink-0 text-lw-sm text-lw-muted">Сумма к учёту</span>
      <input
        inputMode="decimal"
        autoFocus
        value={value}
        onChange={(event) => setValue(event.target.value)}
        placeholder="10 000"
        className="lw-input !w-36 !py-2"
      />
      <button
        type="submit"
        disabled={busy}
        className="lw-btn !px-4 !py-2 !text-[15px]"
      >
        {busy ? "Сохраняю…" : "Сохранить"}
      </button>
      <button
        type="button"
        onClick={() => setEditing(false)}
        className="text-lw-sm text-lw-muted hover:text-lw-primary"
      >
        Отмена
      </button>
      {error ? <p className="w-full text-lw-sm text-lw-danger">{error}</p> : null}
    </form>
  );
}
