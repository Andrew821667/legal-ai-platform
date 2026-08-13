"use client";

import { useMemo, useState } from "react";

type FieldProps = {
  label: string;
  min: number;
  value: number;
  onChange: (value: number) => void;
  suffix: string;
};

const money = new Intl.NumberFormat("ru-RU", {
  maximumFractionDigits: 0,
  style: "currency",
  currency: "RUB",
});

const number = new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 1 });

function Field({ label, min, value, onChange, suffix }: FieldProps) {
  return (
    <label className="block">
      <span className="text-sm font-medium text-slate-200">{label}</span>
      <span className="mt-2 flex items-center overflow-hidden rounded-lg border border-slate-700 bg-slate-950">
        <input
          className="min-w-0 flex-1 bg-transparent px-4 py-3 text-white outline-none focus:ring-2 focus:ring-inset focus:ring-amber-500"
          inputMode="decimal"
          min={min}
          onChange={(event) => onChange(Math.max(min, Number(event.target.value) || 0))}
          type="number"
          value={value}
        />
        <span className="border-l border-slate-700 px-3 text-sm text-slate-400">{suffix}</span>
      </span>
    </label>
  );
}

export default function LegalAiRoiCalculator() {
  const [tasks, setTasks] = useState(100);
  const [before, setBefore] = useState(45);
  const [after, setAfter] = useState(20);
  const [hourCost, setHourCost] = useState(2500);
  const [setupCost, setSetupCost] = useState(50000);
  const [monthlyCost, setMonthlyCost] = useState(15000);
  const [months, setMonths] = useState(12);

  const result = useMemo(() => {
    const savedMinutes = tasks * Math.max(0, before - after);
    const savedHours = savedMinutes / 60;
    const monthlyBenefit = savedHours * hourCost;
    const totalBenefit = monthlyBenefit * months;
    const totalCost = setupCost + monthlyCost * months;
    const net = totalBenefit - totalCost;
    const roi = totalCost > 0 ? (net / totalCost) * 100 : null;
    const monthlyNet = monthlyBenefit - monthlyCost;
    const payback = monthlyNet > 0 ? setupCost / monthlyNet : null;

    return { savedHours, monthlyBenefit, totalCost, net, roi, payback };
  }, [after, before, hourCost, monthlyCost, months, setupCost, tasks]);

  return (
    <section className="border-y border-slate-800 bg-slate-900/70" aria-labelledby="roi-calculator-title">
      <div className="mx-auto max-w-6xl px-4 py-14 sm:px-6 lg:px-8">
        <div className="max-w-4xl">
          <p className="text-sm font-semibold uppercase tracking-wide text-amber-300">Интерактивный расчет</p>
          <h2 id="roi-calculator-title" className="mt-3 text-3xl font-semibold text-white">
            Калькулятор ROI юридической автоматизации
          </h2>
          <p className="mt-4 leading-7 text-slate-300">
            Сравните текущий маршрут с пилотом Legal AI. Меняйте исходные данные: результат показывает экономическую
            модель, а не обещанный эффект продукта.
          </p>
        </div>

        <div className="mt-8 grid gap-8 lg:grid-cols-[1fr_0.9fr]">
          <div className="grid gap-5 rounded-2xl border border-slate-700 bg-slate-950/70 p-6 sm:grid-cols-2">
            <Field label="Задач в месяц" min={1} value={tasks} onChange={setTasks} suffix="шт." />
            <Field label="Стоимость часа специалиста" min={0} value={hourCost} onChange={setHourCost} suffix="₽" />
            <Field label="Время до автоматизации" min={1} value={before} onChange={setBefore} suffix="мин." />
            <Field label="Время после автоматизации" min={0} value={after} onChange={setAfter} suffix="мин." />
            <Field label="Настройка и интеграция" min={0} value={setupCost} onChange={setSetupCost} suffix="₽" />
            <Field label="Ежемесячные расходы" min={0} value={monthlyCost} onChange={setMonthlyCost} suffix="₽" />
            <Field label="Период оценки" min={1} value={months} onChange={setMonths} suffix="мес." />
          </div>

          <div className="rounded-2xl border border-amber-500/30 bg-amber-500/10 p-6">
            <h3 className="text-xl font-semibold text-white">Расчет по введенным данным</h3>
            <dl className="mt-6 space-y-5">
              <div className="flex items-end justify-between gap-4 border-b border-amber-500/20 pb-4">
                <dt className="text-sm text-slate-300">Высвобождается в месяц</dt>
                <dd className="text-xl font-semibold text-white">{number.format(result.savedHours)} ч</dd>
              </div>
              <div className="flex items-end justify-between gap-4 border-b border-amber-500/20 pb-4">
                <dt className="text-sm text-slate-300">Потенциальный эффект в месяц</dt>
                <dd className="text-xl font-semibold text-white">{money.format(result.monthlyBenefit)}</dd>
              </div>
              <div className="flex items-end justify-between gap-4 border-b border-amber-500/20 pb-4">
                <dt className="text-sm text-slate-300">Все расходы за период</dt>
                <dd className="text-xl font-semibold text-white">{money.format(result.totalCost)}</dd>
              </div>
              <div className="flex items-end justify-between gap-4 border-b border-amber-500/20 pb-4">
                <dt className="text-sm text-slate-300">Чистый эффект за период</dt>
                <dd className={result.net >= 0 ? "text-xl font-semibold text-emerald-300" : "text-xl font-semibold text-rose-300"}>
                  {money.format(result.net)}
                </dd>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <dt className="text-sm text-slate-300">ROI</dt>
                  <dd className="mt-1 text-2xl font-semibold text-white">
                    {result.roi === null ? "—" : `${number.format(result.roi)} %`}
                  </dd>
                </div>
                <div>
                  <dt className="text-sm text-slate-300">Окупаемость</dt>
                  <dd className="mt-1 text-2xl font-semibold text-white">
                    {result.payback === null ? "не достигается" : `${number.format(result.payback)} мес.`}
                  </dd>
                </div>
              </div>
            </dl>
          </div>
        </div>

        <p className="mt-5 text-sm leading-6 text-slate-500">
          В расчет не включена цена юридической ошибки и косвенные эффекты. Перед решением о внедрении исходные
          показатели нужно измерить на сопоставимом наборе задач, а результат пилота — подтвердить ответственным специалистом.
        </p>
      </div>
    </section>
  );
}
