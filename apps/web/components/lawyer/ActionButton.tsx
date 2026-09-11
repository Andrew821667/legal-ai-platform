"use client";

import { useState } from "react";

/**
 * Кнопка действия с состоянием.
 *
 * Показывает ход и результат прямо на месте: отдельное всплывающее сообщение в
 * мессенджере легко пропустить, а отправка договора — не то действие, о судьбе
 * которого можно гадать.
 */
export default function ActionButton({
  label,
  done,
  onRun,
  tone = "primary",
  busy = "Отправляю…",
}: {
  label: string;
  done: string;
  onRun: () => Promise<void>;
  tone?: "primary" | "quiet";
  busy?: string;
}) {
  const [state, setState] = useState<"idle" | "busy" | "ok">("idle");
  const [error, setError] = useState<string | null>(null);

  if (state === "ok") {
    return <p className="text-lw-sm text-lw-success">{done}</p>;
  }

  return (
    <div>
      <button
        type="button"
        disabled={state === "busy"}
        onClick={async () => {
          setState("busy");
          setError(null);
          try {
            await onRun();
            setState("ok");
          } catch (err) {
            setError(err instanceof Error ? err.message : "Не получилось");
            setState("idle");
          }
        }}
        className={`w-full ${tone === "primary" ? "lw-btn" : "lw-btn-quiet"}`}
      >
        {state === "busy" ? busy : label}
      </button>
      {error ? <p className="mt-1 text-lw-sm text-lw-danger">{error}</p> : null}
    </div>
  );
}
