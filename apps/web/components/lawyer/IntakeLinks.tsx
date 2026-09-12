"use client";

import { useEffect, useRef, useState } from "react";

import { lawyerAction, lawyerFetch } from "./useTelegram";
import type { ClientRow, IntakeLinkRow } from "./types";

/**
 * Связь с делом другого клиента — только пометка для контекста.
 *
 * Найдено вживую: один клиент упоминал бывшего супруга другого клиента как
 * противоположную сторону в том же имущественном споре, а проверка
 * конфликта у каждого обращения шла независимо — юрист узнавал о связи
 * только по памяти. Договоры, NDA и документы каждого обращения остаются
 * полностью раздельными: это перекрёстная ссылка, а не слияние дел.
 */

const ROLE_TEXT: Record<IntakeLinkRow["role"], string> = {
  main: "Основное дело — второстепенное у",
  subordinate: "Второстепенное — основное у",
  joint: "Общее рассмотрение с",
};

function LinkRow({
  link,
  initData,
  onOpen,
  onChanged,
}: {
  link: IntakeLinkRow;
  initData: string;
  onOpen: (leadId: string) => void;
  onChanged: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const remove = async () => {
    setBusy(true);
    try {
      await lawyerAction(`/api/lawyer/intakes/links/${link.link_id}`, initData, undefined, "DELETE");
      onChanged();
    } finally {
      setBusy(false);
    }
  };
  return (
    <li className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1 text-lw-sm">
      <span className="text-lw-ink">
        {ROLE_TEXT[link.role]}{" "}
        <button
          type="button"
          onClick={() => onOpen(link.linked_lead_id)}
          className="font-medium text-lw-primary underline-offset-2 hover:underline"
        >
          {link.linked_client}
        </button>
        {link.note ? <span className="text-lw-muted"> · {link.note}</span> : null}
      </span>
      <button
        type="button"
        disabled={busy}
        onClick={() => void remove()}
        className="shrink-0 text-lw-muted underline underline-offset-2 hover:text-lw-danger disabled:opacity-60"
      >
        снять
      </button>
    </li>
  );
}

function AddLinkForm({
  intakeId,
  currentLeadId,
  initData,
  onChanged,
  onCancel,
}: {
  intakeId: string;
  currentLeadId: string;
  initData: string;
  onChanged: () => void;
  onCancel: () => void;
}) {
  const [term, setTerm] = useState("");
  const [results, setResults] = useState<ClientRow[] | null>(null);
  const [selected, setSelected] = useState<ClientRow | null>(null);
  const [role, setRole] = useState<"subordinate" | "main" | "joint">("joint");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    const query = term.trim();
    if (!query) {
      setResults(null);
      return;
    }
    debounceRef.current = setTimeout(async () => {
      try {
        const rows = await lawyerFetch<ClientRow[]>(
          `/api/lawyer/clients?search=${encodeURIComponent(query)}`,
          initData,
        );
        setResults(rows.filter((row) => row.lead_id !== currentLeadId));
      } catch {
        setResults([]);
      }
    }, 300);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [term, initData, currentLeadId]);

  const submit = async () => {
    if (!selected) return;
    setBusy(true);
    setError(null);
    try {
      await lawyerAction(`/api/lawyer/intakes/${intakeId}/links`, initData, {
        linked_lead_id: selected.lead_id,
        role,
        note: note.trim() || undefined,
      });
      onChanged();
      onCancel();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось связать");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mt-2 rounded-xl bg-lw-cell p-3">
      {selected ? (
        <div className="flex items-center justify-between gap-2 text-lw-sm">
          <span className="text-lw-ink">
            Клиент: <span className="font-medium">{selected.name}</span>
          </span>
          <button
            type="button"
            onClick={() => setSelected(null)}
            className="text-lw-muted underline underline-offset-2 hover:text-lw-primary"
          >
            изменить
          </button>
        </div>
      ) : (
        <>
          <input
            autoFocus
            value={term}
            onChange={(event) => setTerm(event.target.value)}
            placeholder="Имя, контакт или компания другого клиента"
            className="lw-input"
          />
          {results && results.length > 0 ? (
            <ul className="mt-1.5 max-h-40 space-y-1 overflow-y-auto">
              {results.map((row) => (
                <li key={row.lead_id}>
                  <button
                    type="button"
                    onClick={() => setSelected(row)}
                    className="w-full rounded-lg px-2 py-1.5 text-left text-lw-sm text-lw-ink hover:bg-lw-blue-soft"
                  >
                    {row.name}
                    {row.contact ? <span className="text-lw-muted"> · {row.contact}</span> : null}
                  </button>
                </li>
              ))}
            </ul>
          ) : results && results.length === 0 ? (
            <p className="mt-1.5 text-lw-sm text-lw-muted">Никого не нашлось.</p>
          ) : null}
        </>
      )}

      {selected ? (
        <>
          <div className="mt-2.5 flex flex-wrap gap-1.5" role="group" aria-label="Роль этого дела">
            {(
              [
                ["joint", "Общее рассмотрение"],
                ["subordinate", "Это дело — второстепенное"],
                ["main", "Это дело — основное"],
              ] as [typeof role, string][]
            ).map(([key, title]) => (
              <button
                key={key}
                type="button"
                aria-pressed={role === key}
                onClick={() => setRole(key)}
                className={`rounded-full px-3 py-1.5 text-lw-sm font-semibold transition-colors ${
                  role === key
                    ? "bg-lw-primary text-white"
                    : "bg-white text-lw-ink ring-1 ring-lw-border hover:bg-lw-blue-soft"
                }`}
              >
                {title}
              </button>
            ))}
          </div>
          <input
            value={note}
            onChange={(event) => setNote(event.target.value)}
            placeholder="Заметка (необязательно)"
            className="lw-input mt-2"
          />
          {error ? <p className="mt-1.5 text-lw-sm text-lw-danger">{error}</p> : null}
          <div className="mt-2.5 flex gap-2">
            <button
              type="button"
              disabled={busy}
              onClick={() => void submit()}
              className="lw-btn-quiet disabled:opacity-60"
            >
              {busy ? "Связываю…" : "Связать"}
            </button>
            <button
              type="button"
              onClick={onCancel}
              className="text-lw-sm text-lw-muted underline underline-offset-2 hover:text-lw-primary"
            >
              Отмена
            </button>
          </div>
        </>
      ) : (
        <button
          type="button"
          onClick={onCancel}
          className="mt-2 text-lw-sm text-lw-muted underline underline-offset-2 hover:text-lw-primary"
        >
          Отмена
        </button>
      )}
    </div>
  );
}

export default function IntakeLinks({
  intakeId,
  currentLeadId,
  links,
  initData,
  onOpen,
  onChanged,
}: {
  intakeId: string;
  currentLeadId: string;
  links: IntakeLinkRow[];
  initData: string;
  onOpen: (leadId: string) => void;
  onChanged: () => void;
}) {
  const [adding, setAdding] = useState(false);

  return (
    <div className="mt-3 border-t border-lw-border pt-3">
      {links.length > 0 ? (
        <ul className="space-y-1.5">
          {links.map((link) => (
            <LinkRow key={link.link_id} link={link} initData={initData} onOpen={onOpen} onChanged={onChanged} />
          ))}
        </ul>
      ) : null}

      {adding ? (
        <AddLinkForm
          intakeId={intakeId}
          currentLeadId={currentLeadId}
          initData={initData}
          onChanged={onChanged}
          onCancel={() => setAdding(false)}
        />
      ) : (
        <button
          type="button"
          onClick={() => setAdding(true)}
          className="text-lw-sm text-lw-muted underline underline-offset-2 hover:text-lw-primary"
        >
          + Связать с делом другого клиента
        </button>
      )}
    </div>
  );
}
