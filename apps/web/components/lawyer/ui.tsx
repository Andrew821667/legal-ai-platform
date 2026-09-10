"use client";

/** Общие элементы рабочего места: статусы, строки данных, заголовки блоков. */

const TONES = {
  ok: "bg-emerald-500/15 text-emerald-300 ring-emerald-500/25",
  warn: "bg-amber-500/15 text-amber-300 ring-amber-500/25",
  alert: "bg-rose-500/15 text-rose-300 ring-rose-500/25",
  mute: "bg-slate-500/15 text-slate-300 ring-slate-500/25",
} as const;

export type Tone = keyof typeof TONES;

export function Pill({ children, tone = "mute" }: { children: React.ReactNode; tone?: Tone }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ring-inset ${TONES[tone]}`}
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
    <div className="flex gap-2 py-1 text-xs">
      <span className="w-28 shrink-0 text-slate-500">{label}</span>
      <span className="min-w-0 flex-1 text-slate-200">{value}</span>
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
  return (
    <div className={`rounded-2xl border border-slate-800/80 bg-slate-900/60 p-4 ${className}`}>
      {children}
    </div>
  );
}

export function SectionTitle({
  children,
  count,
}: {
  children: React.ReactNode;
  count?: number;
}) {
  return (
    <h2 className="mb-2 flex items-baseline gap-2 text-[13px] font-semibold uppercase tracking-wide text-slate-400">
      {children}
      {count !== undefined ? <span className="text-slate-600">{count}</span> : null}
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
    <div className="mt-3 flex items-center gap-1">
      {steps.map((step, index) => {
        const done = index + 1 <= reached;
        return (
          <div key={step} className="flex flex-1 flex-col gap-1">
            <div className={`h-1 rounded-full ${done ? "bg-amber-500" : "bg-slate-800"}`} />
            <span className={`text-[10px] ${done ? "text-slate-300" : "text-slate-600"}`}>
              {step}
            </span>
          </div>
        );
      })}
    </div>
  );
}
