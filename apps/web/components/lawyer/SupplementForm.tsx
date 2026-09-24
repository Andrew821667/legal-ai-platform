"use client";

import { useState } from "react";

import { formatRub, parseRublesInput } from "@/lib/money";
import { SUPPLEMENT_FIELDS } from "@/lib/supplement-draft";
import { dropDraft, readDraft, writeDraft } from "./draft-storage";
import { lawyerAction } from "./useTelegram";

/**
 * Допсоглашение к подписанному договору.
 *
 * Сумму подписанного договора раньше меняла кнопка «изменить» — в одну
 * сторону, без документа для клиента. Здесь юрист пишет новую общую
 * стоимость и дополнительные работы; клиент получает допсоглашение тем же
 * путём, что и договор, и сумма договора меняется только после его подписи.
 *
 * Введённое, как и у договора, живёт в браузере до отправки.
 */

const draftKey = (agreementId: string) => `lawyer.supplement.${agreementId}`;

export default function SupplementForm({
  agreementId,
  currentMinor,
  replacesOpen,
  initData,
  onClose,
  onCreated,
}: {
  agreementId: string;
  currentMinor: number | null;
  /** У договора уже есть неподписанное допсоглашение — новое его заменит. */
  replacesOpen: boolean;
  initData: string;
  onClose: () => void;
  onCreated: () => void;
}) {
  const [values, setValues] = useState<Record<string, string>>(() =>
    readDraft<Record<string, string>>(draftKey(agreementId), {}),
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const update = (key: string, text: string) => {
    const next = { ...values, [key]: text };
    // Как в договоре: формулировка и число подтягивают друг друга, пока
    // второе пусто.
    if (key === "price_text" && !(next.amount || "").trim()) {
      const parsed = parseRublesInput(text);
      if (parsed.ok && parsed.minor !== null) next.amount = String(parsed.minor / 100);
    }
    if (key === "amount" && !(next.price_text || "").trim()) {
      const parsed = parseRublesInput(text);
      if (parsed.ok && parsed.minor !== null) next.price_text = formatRub(parsed.minor);
    }
    setValues(next);
    writeDraft(draftKey(agreementId), next);
  };

  return (
    <form
      className="lw-card mt-3 space-y-3 p-4"
      onSubmit={async (event) => {
        event.preventDefault();
        setBusy(true);
        setError(null);
        try {
          await lawyerAction(`/api/lawyer/agreements/${agreementId}/supplement`, initData, values);
          dropDraft(draftKey(agreementId));
          onCreated();
        } catch (err) {
          setError(err instanceof Error ? err.message : "Не удалось составить допсоглашение");
        } finally {
          setBusy(false);
        }
      }}
    >
      <p className="text-lw-base font-medium text-lw-ink">Допсоглашение</p>
      <p className="text-lw-sm text-lw-muted">
        {currentMinor !== null ? `Сейчас по договору ${formatRub(currentMinor)}. ` : ""}
        Сумма договора изменится, когда клиент подпишет допсоглашение.
      </p>
      {replacesOpen ? (
        <p className="text-lw-sm text-lw-warning">
          Неподписанное допсоглашение будет заменено новым.
        </p>
      ) : null}

      {SUPPLEMENT_FIELDS.map((field) => (
        <div key={field.key}>
          <label className="block">
            <span className="text-lw-sm text-lw-muted">{field.label}</span>
            <textarea
              value={values[field.key] || ""}
              onChange={(event) => update(field.key, event.target.value)}
              rows={field.rows}
              placeholder={field.hint}
              className="lw-input mt-1"
            />
          </label>
          {field.key === "price_text" ? (
            <label className="mt-2 block">
              <span className="text-lw-sm text-lw-muted">Новая сумма к учёту, ₽</span>
              <input
                inputMode="decimal"
                value={values.amount || ""}
                onChange={(event) => update("amount", event.target.value)}
                placeholder="150 000"
                className="lw-input mt-1"
              />
              <span className="mt-1 block text-lw-sm text-lw-muted">
                Общая сумма по договору, не доплата. Станет суммой договора после подписи.
              </span>
            </label>
          ) : null}
        </div>
      ))}

      <p className="text-lw-sm text-lw-muted">
        Реквизиты возьмутся из договора. Допсоглашение появится черновиком — клиент увидит
        его только после отправки; предложение действует 7 дней.
      </p>

      {error ? <p className="text-lw-sm text-lw-danger">{error}</p> : null}

      <div className="flex gap-2">
        <button type="submit" disabled={busy} className="lw-btn flex-1">
          {busy ? "Составляю…" : "Составить"}
        </button>
        <button type="button" onClick={onClose} className="lw-btn-quiet">
          Свернуть
        </button>
      </div>
    </form>
  );
}
