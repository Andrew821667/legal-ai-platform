"use client";

import { useState } from "react";

import { Card, Pill } from "./ui";
import { shortDate } from "./labels";
import type { ClientRow } from "./types";

/**
 * Список клиентов — полный, а не отфильтрованный по задачам.
 *
 * Раньше на первом экране был только список задач, и клиент, по которому всё
 * идёт своим чередом, там не появлялся. Со стороны это выглядело так, будто он
 * пропал из системы.
 */

function stageTone(stage: string, waiting: boolean) {
  if (waiting) return "alert" as const;
  if (stage === "Договор подписан") return "ok" as const;
  if (stage === "Договор не отправлен" || stage === "Клиент отказался") return "warn" as const;
  return "mute" as const;
}

export default function ClientsView({
  rows,
  onOpen,
  onSearch,
  selectedId = null,
}: {
  rows: ClientRow[] | null;
  onOpen: (leadId: string) => void;
  onSearch: (term: string) => void;
  selectedId?: string | null;
}) {
  const [term, setTerm] = useState("");

  return (
    <div>
      <form
        className="mb-3 flex gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          onSearch(term.trim());
        }}
      >
        <input
          value={term}
          onChange={(event) => setTerm(event.target.value)}
          placeholder="Имя, контакт или компания"
          className="w-full rounded-xl border border-slate-800 bg-slate-900/60 px-3 py-2.5 text-base text-white outline-none transition-colors placeholder:text-slate-400 focus:border-slate-600"
        />
        <button
          type="submit"
          className="shrink-0 rounded-xl bg-slate-800 px-4 text-base text-slate-200 transition-colors hover:bg-slate-700"
        >
          Найти
        </button>
      </form>

      {rows === null ? null : rows.length === 0 ? (
        <Card>
          <p className="text-base text-slate-400">Никого не нашлось.</p>
        </Card>
      ) : (
        <ul className="space-y-2">
          {rows.map((row) => (
            <li key={row.lead_id}>
              <button
                type="button"
                onClick={() => onOpen(row.lead_id)}
                aria-current={row.lead_id === selectedId ? "true" : undefined}
                className={`w-full rounded-2xl border p-4 text-left transition-colors ${
                  row.lead_id === selectedId
                    ? "border-amber-500/60 bg-slate-900"
                    : "border-slate-800/80 bg-slate-900/60 hover:border-slate-700 hover:bg-slate-900"
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate text-lg font-medium text-white">{row.name}</p>
                    <p className="mt-0.5 truncate text-sm text-slate-400">
                      {row.contact || "контакт не указан"}
                      {row.company ? ` · ${row.company}` : ""}
                    </p>
                  </div>
                  <span className="shrink-0 text-sm text-slate-400">
                    {shortDate(row.last_intake_at)}
                  </span>
                </div>

                <div className="mt-3 flex flex-wrap items-center gap-1.5">
                  <Pill tone={stageTone(row.stage, row.waiting_on_me)}>{row.stage}</Pill>
                  {row.waiting_on_me ? <Pill tone="alert">Ждёт ответа</Pill> : null}
                  {row.nda_signed ? null : <Pill tone="warn">без NDA</Pill>}
                  {row.intakes > 1 ? <Pill>{row.intakes} обращения</Pill> : null}
                </div>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
