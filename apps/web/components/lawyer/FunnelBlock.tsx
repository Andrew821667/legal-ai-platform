"use client";

import { useEffect, useState } from "react";

import { formatRub } from "@/lib/money";
import { Card } from "./ui";
import { lawyerFetch } from "./useTelegram";
import type { Funnel, FunnelStageKey } from "./types";

const number = (value: number) => value.toLocaleString("ru-RU");

/**
 * Откуда приходят клиенты и где останавливаются.
 *
 * Считается когорта: из пришедших за период — сколько дошли до каждого шага.
 * Так видно, какой источник приводит платящих клиентов, а какой — только
 * вопросы, и на каком шаге теряются люди.
 *
 * Над воронкой — сайт по Метрике: сколько людей зашло и сколько из них
 * оставили заявку. Ушедшие молча в воронке ядра не видны вовсе.
 */

const PERIODS = [
  { days: 30, label: "30 дней" },
  { days: 90, label: "90 дней" },
  { days: 365, label: "год" },
];

const COLUMNS: { key: FunnelStageKey; short: string }[] = [
  { key: "leads", short: "пришли" },
  { key: "intake", short: "обращ." },
  { key: "agreement", short: "дог." },
  { key: "signed", short: "подп." },
  { key: "paid", short: "опл." },
];

export default function FunnelBlock({ initData }: { initData: string }) {
  const [days, setDays] = useState(90);
  const [funnel, setFunnel] = useState<Funnel | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    setError("");
    lawyerFetch<Funnel>(`/api/lawyer/funnel?days=${days}`, initData)
      .then((data) => {
        if (!cancelled) setFunnel(data);
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message);
      });
    return () => {
      cancelled = true;
    };
  }, [days, initData]);

  const top = funnel?.stages[0]?.count || 0;

  return (
    <section>
      <div className="mb-2 flex items-center justify-between gap-3">
        <h2 className="lw-eyebrow">Воронка</h2>
        <div className="flex gap-1">
          {PERIODS.map((period) => (
            <button
              key={period.days}
              type="button"
              onClick={() => setDays(period.days)}
              className={`rounded-full px-2.5 py-1 text-lw-sm ${
                days === period.days ? "bg-lw-primary text-white" : "bg-lw-cell text-lw-muted hover:bg-lw-blue-soft"
              }`}
            >
              {period.label}
            </button>
          ))}
        </div>
      </div>
      <Card>
        {error ? <p className="text-lw-sm text-lw-danger">{error}</p> : null}
        {!funnel && !error ? <p className="text-lw-sm text-lw-muted">Считаю…</p> : null}
        {funnel?.site ? <SiteBlock funnel={funnel} /> : null}
        {funnel && top === 0 ? (
          <p className="text-lw-base text-lw-muted">За этот период новых клиентов не было.</p>
        ) : null}
        {funnel && top > 0 ? (
          <>
            <ul className="space-y-2">
              {funnel.stages.map((stage) => (
                <li key={stage.key}>
                  <div className="flex items-baseline justify-between gap-3 text-lw-sm">
                    <span className="text-lw-ink">{stage.title}</span>
                    <span className="tabular-nums text-lw-ink">
                      <b>{stage.count}</b>
                      {stage.from_previous_pct !== null ? (
                        <span className="text-lw-muted"> · {stage.from_previous_pct}% от прошлого шага</span>
                      ) : null}
                    </span>
                  </div>
                  <div className="mt-1 h-2 overflow-hidden rounded-full bg-lw-cell">
                    <div
                      className="h-full rounded-full bg-lw-primary"
                      style={{ width: `${Math.max(stage.count ? 3 : 0, (stage.count * 100) / top)}%` }}
                    />
                  </div>
                </li>
              ))}
            </ul>
            {funnel.paid_minor > 0 ? (
              <p className="mt-3 text-lw-sm text-lw-muted">
                Оплачено этими клиентами: <b className="text-lw-ink">{formatRub(funnel.paid_minor)}</b>
              </p>
            ) : null}

            <div className="mt-4 overflow-x-auto">
              <table className="w-full min-w-[18rem] text-lw-sm tabular-nums">
                <thead>
                  <tr className="text-lw-muted">
                    <th className="py-1 pr-2 text-left font-normal">Источник</th>
                    {COLUMNS.map((column) => (
                      <th key={column.key} className="px-1 py-1 text-right font-normal">
                        {column.short}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {funnel.sources.map((source) => (
                    <tr key={source.key} className="border-t border-lw-border">
                      <td className="py-1.5 pr-2 text-lw-ink">
                        {source.title}
                        {source.paid_minor > 0 ? (
                          <span className="block text-lw-muted">{formatRub(source.paid_minor)}</span>
                        ) : null}
                      </td>
                      {COLUMNS.map((column) => (
                        <td key={column.key} className="px-1 py-1.5 text-right text-lw-ink">
                          {source.counts[column.key] || <span className="text-lw-muted">—</span>}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="mt-2 text-lw-sm text-lw-muted">
              Считаются клиенты, пришедшие за период; тестовые аккаунты и архив — нет. «Канал» — пришли по
              кнопке из поста; кто прочитал пост и написал боту сам, попадает в «Бот напрямую».
            </p>
          </>
        ) : null}
      </Card>
    </section>
  );
}

function SiteBlock({ funnel }: { funnel: Funnel }) {
  const site = funnel.site;
  if (!site) return null;
  if (site.status === "off") {
    return (
      <p className="mb-3 text-lw-sm text-lw-muted">
        Посетители сайта появятся здесь, когда на сервере будет токен Метрики (YM_ACCESS_TOKEN).
      </p>
    );
  }
  if (site.status === "error") {
    return <p className="mb-3 text-lw-sm text-lw-muted">Метрика: {site.detail}</p>;
  }

  const leadsFrom = (key: string) => funnel.sources.find((source) => source.key === key)?.counts.leads || 0;
  const formLeads = leadsFrom("site_form");
  const botLeads = leadsFrom("site_bot");
  const siteLeads = formLeads + botLeads;
  const conversion = site.users ? Math.round((siteLeads * 1000) / site.users) / 10 : null;

  return (
    <div className="mb-4 rounded-xl bg-lw-cell p-3 text-lw-sm">
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-lw-ink">Сайт</span>
        <span className="tabular-nums text-lw-ink">
          <b>{number(site.users)}</b> <span className="text-lw-muted">посетителей · {number(site.visits)} визитов</span>
        </span>
      </div>
      <p className="mt-1 text-lw-muted">
        Оставили заявку: <b className="text-lw-ink">{siteLeads}</b>
        {conversion !== null ? ` — ${String(conversion).replace(".", ",")}% посетителей` : ""} (форма — {formLeads},
        в бота с сайта — {botLeads}).
      </p>
      {site.formSubmits !== null ? (
        <p className="mt-1 text-lw-muted">
          Отправок формы по Метрике: <b className="text-lw-ink">{site.formSubmits}</b>
          {site.formSubmits > formLeads
            ? " — больше, чем заявок с формы: повторные отправки одного человека, тестовые или отсеянные антиспамом."
            : "."}
        </p>
      ) : (
        <p className="mt-1 text-lw-muted">
          Цели «lead_form_submit» в счётчике нет — отправки формы Метрика не считает.
        </p>
      )}
      {site.sources.length ? (
        <ul className="mt-2 space-y-1">
          {site.sources.slice(0, 5).map((source) => (
            <li key={source.key} className="flex items-baseline justify-between gap-3 tabular-nums">
              <span className="text-lw-ink">{source.title}</span>
              <span className="text-lw-muted">
                {number(source.visits)} визитов
                {source.formSubmits ? ` · заявок ${source.formSubmits}` : ""}
              </span>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
