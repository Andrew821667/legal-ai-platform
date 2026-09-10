"use client";

import { useState } from "react";

import { AGREEMENT_STATUS, label, shortDate } from "./labels";
import type { ClientRow } from "./types";

export default function ClientsView({
  rows,
  onOpen,
  onSearch,
}: {
  rows: ClientRow[] | null;
  onOpen: (leadId: string) => void;
  onSearch: (term: string) => void;
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
          className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white placeholder:text-slate-500"
        />
        <button
          type="submit"
          className="shrink-0 rounded-lg bg-slate-800 px-3 py-2 text-sm text-slate-200 hover:bg-slate-700"
        >
          Найти
        </button>
      </form>

      {rows === null ? null : rows.length === 0 ? (
        <p className="rounded-lg border border-slate-800 bg-slate-900 p-4 text-sm text-slate-400">
          Никого не нашлось.
        </p>
      ) : (
        <ul className="space-y-2">
          {rows.map((row) => (
            <li key={row.lead_id}>
              <button
                type="button"
                onClick={() => onOpen(row.lead_id)}
                className="w-full rounded-lg border border-slate-800 bg-slate-900 p-3 text-left transition-colors hover:bg-slate-800"
              >
                <div className="flex items-baseline justify-between gap-3">
                  <span className="text-sm font-medium text-white">{row.name}</span>
                  <span className="shrink-0 text-xs text-slate-500">
                    {shortDate(row.last_intake_at)}
                  </span>
                </div>
                <p className="mt-1 text-xs text-slate-400">
                  {row.contact || "контакт не указан"}
                  {row.company ? ` · ${row.company}` : ""}
                </p>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  <Tag>{row.intakes === 1 ? "1 обращение" : `${row.intakes} обращения`}</Tag>
                  {row.nda_signed ? <Tag tone="ok">NDA подписан</Tag> : <Tag tone="warn">без NDA</Tag>}
                  {row.agreement_status ? (
                    <Tag tone={row.agreement_status === "signed" ? "ok" : "warn"}>
                      {label(AGREEMENT_STATUS, row.agreement_status)}
                    </Tag>
                  ) : (
                    <Tag tone="warn">договора нет</Tag>
                  )}
                </div>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function Tag({ children, tone }: { children: React.ReactNode; tone?: "ok" | "warn" }) {
  const colors =
    tone === "ok"
      ? "bg-emerald-950 text-emerald-300"
      : tone === "warn"
        ? "bg-amber-950 text-amber-300"
        : "bg-slate-800 text-slate-300";
  return <span className={`rounded px-1.5 py-0.5 text-[11px] ${colors}`}>{children}</span>;
}
