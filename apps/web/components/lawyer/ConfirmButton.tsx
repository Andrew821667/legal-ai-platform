"use client";

import { useState } from "react";

/**
 * Кнопка необратимого или заметного действия — с подтверждением на месте.
 *
 * Не window.confirm: внутри Telegram его диалог выглядит чужим, а на части
 * платформ не показывается вовсе. Первое нажатие раскрывает объяснение, что
 * произойдёт, второе — делает.
 */
export default function ConfirmButton({
  label,
  explain,
  confirmLabel,
  busy = "Выполняю…",
  danger = false,
  onConfirm,
}: {
  label: string;
  explain: React.ReactNode;
  confirmLabel: string;
  busy?: string;
  danger?: boolean;
  onConfirm: () => Promise<void>;
}) {
  const [open, setOpen] = useState(false);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const tone = danger ? "lw-btn-quiet lw-btn-quiet-danger w-full" : "lw-btn-quiet w-full";

  if (!open) {
    return (
      <button type="button" onClick={() => setOpen(true)} className={tone}>
        {label}
      </button>
    );
  }

  return (
    <div className={`rounded-xl p-3 ${danger ? "bg-lw-danger-soft" : "bg-lw-cell"}`}>
      <div className="text-lw-sm text-lw-ink">{explain}</div>
      <div className="mt-3 flex gap-2">
        <button
          type="button"
          disabled={running}
          onClick={async () => {
            setRunning(true);
            setError(null);
            try {
              await onConfirm();
              setOpen(false);
            } catch (err) {
              setError(err instanceof Error ? err.message : "Не получилось");
            } finally {
              setRunning(false);
            }
          }}
          className={`lw-btn flex-1 ${danger ? "lw-btn-danger" : ""}`}
        >
          {running ? busy : confirmLabel}
        </button>
        <button type="button" disabled={running} onClick={() => setOpen(false)} className="lw-btn-quiet">
          Отмена
        </button>
      </div>
      {error ? <p className="mt-2 text-lw-sm text-lw-danger">{error}</p> : null}
    </div>
  );
}
