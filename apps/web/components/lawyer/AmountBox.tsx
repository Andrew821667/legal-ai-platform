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
 *
 * Указанную сумму отсюда не поменять: это было бы решение одной стороны.
 * У подписанного договора вместо правки — допсоглашение, которое подписывает
 * клиент; неподписанный меняется новой редакцией.
 */
export default function AmountBox({
  agreementId,
  amountMinor,
  pendingMinor = null,
  onSupplement,
  supplementHref,
  initData,
  onChanged,
}: {
  agreementId: string;
  amountMinor: number | null;
  /** Сумма из отправленного, но ещё не подписанного допсоглашения. */
  pendingMinor?: number | null;
  /** Есть только у подписанного договора — открывает форму допсоглашения. */
  onSupplement?: () => void;
  /** Есть — «допсоглашение» открывается по ссылке в новой вкладке. */
  supplementHref?: string;
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
        {pendingMinor !== null && pendingMinor !== amountMinor ? (
          <span className="text-lw-muted">→ {formatRub(pendingMinor)} после подписи допсоглашения</span>
        ) : null}
        {amountMinor === null ? (
          <button
            type="button"
            onClick={() => {
              setValue("");
              setEditing(true);
            }}
            className="text-lw-muted underline underline-offset-2 hover:text-lw-primary"
          >
            указать
          </button>
        ) : supplementHref ? (
          <a
            href={supplementHref}
            target="_blank"
            rel="noopener"
            className="text-lw-muted underline underline-offset-2 hover:text-lw-primary"
          >
            допсоглашение ↗
          </a>
        ) : onSupplement ? (
          <button
            type="button"
            onClick={onSupplement}
            className="text-lw-muted underline underline-offset-2 hover:text-lw-primary"
          >
            допсоглашение
          </button>
        ) : null}
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
