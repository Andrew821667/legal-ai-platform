"use client";

/** Общие элементы рабочего места: статусы, строки данных, заголовки блоков. */

// Мягкие бейджи, как в «Судебных делах»: цветная подложка и насыщенный текст.
const TONES = {
  ok: "bg-lw-success-soft text-lw-success",
  warn: "bg-lw-warning-soft text-lw-warning",
  alert: "bg-lw-danger-soft text-lw-danger",
  mute: "bg-lw-soft text-lw-muted",
} as const;

export type Tone = keyof typeof TONES;

export function Pill({ children, tone = "mute" }: { children: React.ReactNode; tone?: Tone }) {
  return (
    <span
      className={`inline-flex shrink-0 items-center whitespace-nowrap rounded-full px-3 py-1 text-lw-sm font-semibold ${TONES[tone]}`}
    >
      {children}
    </span>
  );
}

/** Строка «подпись — значение». Пустые значения не показываем. */
export function Row({ label, value }: { label: string; value: React.ReactNode }) {
  if (value === null || value === undefined || value === "" || value === "—") {
    return null;
  }
  return (
    <div className="flex gap-3 py-2 text-lw-base">
      <span className="w-32 shrink-0 text-lw-muted">{label}</span>
      <span className="min-w-0 flex-1 text-lw-ink">{value}</span>
    </div>
  );
}

export function Card({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return <div className={`lw-card p-4 ${className}`}>{children}</div>;
}

export function SectionTitle({
  children,
  count,
}: {
  children: React.ReactNode;
  count?: number;
}) {
  return (
    <h2 className="lw-eyebrow mb-2 flex items-baseline gap-2">
      {children}
      {count !== undefined ? <span className="text-lw-muted">{count}</span> : null}
    </h2>
  );
}

/** Ход дела: пройденные шаги подсвечены, текущий выделен. */
export function Progress({ stage }: { stage: string }) {
  const steps = ["Обращение", "NDA", "Договор", "Подписан"];
  const reached =
    stage === "Договор подписан"
      ? 4
      : stage === "Договор у клиента" || stage === "Договор не отправлен"
        ? 3
        : stage === "Готовим условия"
          ? 2
          : 1;

  return (
    <div className="mt-3 flex items-center gap-1.5">
      {steps.map((step, index) => {
        const done = index + 1 < reached;
        const current = index + 1 === reached;
        return (
          <div key={step} className="flex flex-1 flex-col gap-1.5">
            <div
              className={`h-1.5 rounded-full ${
                done ? "bg-lw-primary" : current ? "bg-lw-primary-2" : "bg-lw-border"
              }`}
            />
            <span
              className={`text-lw-sm ${
                current ? "font-semibold text-lw-primary" : done ? "text-lw-ink" : "text-lw-muted"
              }`}
            >
              {step}
            </span>
          </div>
        );
      })}
    </div>
  );
}
