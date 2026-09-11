"use client";

import { useState } from "react";

import { Card, Pill } from "./ui";
import { AREA, label, shortDate } from "./labels";
import type { ClientRow } from "./types";
import { formatRub } from "@/lib/money";
import { CLIENT_FILTERS, CLIENT_SORTS, availableAreas, groupClients } from "@/lib/lawyer-clients";
import type { ClientFilter, ClientSort } from "@/lib/lawyer-clients";
import { EXTERNAL_LINKS } from "@/lib/links";

/**
 * Список клиентов — полный, а не отфильтрованный по задачам.
 *
 * Раньше на первом экране был только список задач, и клиент, по которому всё
 * идёт своим чередом, там не появлялся. Со стороны это выглядело так, будто он
 * пропал из системы.
 *
 * Разложен по тому, у кого ход: сначала те, кто ждёт юриста, потом те, за
 * кем решение, потом подписанные. Фильтры сверху — для вопросов «кто ждёт
 * ответа» и «у кого нет NDA», ради которых раньше приходилось листать.
 */

/**
 * Ссылка «поделиться ботом» — открывает выбор чата в самом Telegram.
 * Клиенты попадают в список только через бота, и у маленькой практики
 * главный способ получить нового — самому отправить ссылку.
 */
const SHARE_BOT_URL = `https://t.me/share/url?url=${encodeURIComponent(EXTERNAL_LINKS.leadBot)}&text=${encodeURIComponent(
  "Опишите ваш вопрос боту — я отвечу, как только увижу обращение.",
)}`;

/** Ниже этого числа под списком остаётся пустой экран — заполняем его делом. */
const FEW_CLIENTS = 5;

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
  const [filter, setFilter] = useState<ClientFilter>("all");
  const [areas, setAreas] = useState<string[]>([]);
  const [sort, setSort] = useState<ClientSort>("recent");
  const areaOptions = rows ? availableAreas(rows) : [];
  const groups = rows ? groupClients(rows, filter, { areas, sort }) : [];
  const shown = groups.reduce((sum, group) => sum + group.rows.length, 0);

  const toggleArea = (area: string) => {
    setAreas((current) => (current.includes(area) ? current.filter((a) => a !== area) : [...current, area]));
  };

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
          className="lw-input"
        />
        <button
          type="submit"
          className="lw-btn shrink-0"
        >
          Найти
        </button>
      </form>

      {rows && rows.length > 0 ? (
        <div className="mb-3 flex flex-wrap gap-1.5" role="group" aria-label="Фильтр">
          {CLIENT_FILTERS.map((item) => (
            <button
              key={item.key}
              type="button"
              aria-pressed={filter === item.key}
              onClick={() => setFilter(item.key)}
              className={`rounded-full px-3 py-1.5 text-lw-sm font-semibold transition-colors ${
                filter === item.key
                  ? "bg-lw-primary text-white"
                  : "bg-white text-lw-ink ring-1 ring-lw-border hover:bg-lw-blue-soft"
              }`}
            >
              {item.title}
            </button>
          ))}
        </div>
      ) : null}

      {/* Чипов областей нет, пока практика ведёт дела в одном направлении —
          фильтровать не из чего, а ряд занял бы место без пользы. */}
      {areaOptions.length > 1 ? (
        <div className="mb-3 flex flex-wrap gap-1.5" role="group" aria-label="Область права">
          {areaOptions.map((area) => (
            <button
              key={area}
              type="button"
              aria-pressed={areas.includes(area)}
              onClick={() => toggleArea(area)}
              className={`rounded-full px-3 py-1.5 text-lw-sm font-semibold transition-colors ${
                areas.includes(area)
                  ? "bg-lw-primary-2 text-white"
                  : "bg-white text-lw-ink ring-1 ring-lw-border hover:bg-lw-blue-soft"
              }`}
            >
              {label(AREA, area)}
            </button>
          ))}
        </div>
      ) : null}

      {rows && rows.length > 1 ? (
        <div className="mb-3 flex flex-wrap items-center gap-1.5 text-lw-sm text-lw-muted">
          <span>Порядок:</span>
          {CLIENT_SORTS.map((item) => (
            <button
              key={item.key}
              type="button"
              aria-pressed={sort === item.key}
              onClick={() => setSort(item.key)}
              className={`rounded-full px-2.5 py-1 font-semibold transition-colors ${
                sort === item.key ? "bg-lw-ink text-white" : "hover:bg-lw-blue-soft hover:text-lw-ink"
              }`}
            >
              {item.title}
            </button>
          ))}
        </div>
      ) : null}

      {rows === null ? null : rows.length === 0 ? (
        <Card>
          <p className="text-lw-base text-lw-muted">Никого не нашлось.</p>
        </Card>
      ) : shown === 0 ? (
        <Card>
          <p className="text-lw-base text-lw-muted">По этому фильтру никого нет.</p>
        </Card>
      ) : (
        groups.map((group) => (
          <section key={group.key} className="mb-4">
            <h2 className="lw-eyebrow mb-2 flex items-baseline gap-2">
              {group.title}
              <span className="text-lw-muted">{group.rows.length}</span>
            </h2>
            <ul className="space-y-2">
              {group.rows.map((row) => (
                <li key={row.lead_id}>
                  <button
                    type="button"
                    onClick={() => onOpen(row.lead_id)}
                    aria-current={row.lead_id === selectedId ? "true" : undefined}
                    className={`lw-card w-full p-4 text-left transition-shadow hover:shadow-lw-card-hover ${
                      row.lead_id === selectedId ? "!border-lw-primary !bg-lw-blue-soft" : ""
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="truncate text-lw-lg font-medium text-lw-ink">{row.name}</p>
                        <p className="mt-0.5 truncate text-lw-sm text-lw-muted">
                          {row.contact || "контакт не указан"}
                          {row.company ? ` · ${row.company}` : ""}
                        </p>
                      </div>
                      <span className="shrink-0 text-right text-lw-sm text-lw-muted">
                        <span className="block">{shortDate(row.last_intake_at)}</span>
                        {row.amount_minor !== null ? (
                          <span className="block font-semibold tabular-nums text-lw-ink">
                            {formatRub(row.amount_minor)}
                          </span>
                        ) : null}
                      </span>
                    </div>

                    <div className="mt-3 flex flex-wrap items-center gap-1.5">
                      <Pill tone={stageTone(row.stage, row.waiting_on_me)}>{row.stage}</Pill>
                      {row.waiting_on_me ? <Pill tone="alert">Ждёт ответа</Pill> : null}
                      {row.nda_signed ? null : <Pill tone="warn">без NDA</Pill>}
                      {row.intakes > 1 ? <Pill>{row.intakes} обращения</Pill> : null}
                      {row.legal_areas.map((area) => (
                        <Pill key={area} tone="mute">
                          {label(AREA, area)}
                        </Pill>
                      ))}
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          </section>
        ))
      )}

      {/* Под двумя-тремя клиентами оставалось две трети пустого экрана —
          читалось как незаполненное состояние. Здесь — то, что в нём
          действительно можно сделать: позвать следующего клиента. */}
      {rows && rows.length > 0 && rows.length < FEW_CLIENTS && !term.trim() ? (
        <div className="mt-2 rounded-3xl border border-dashed border-lw-border-strong p-5">
          <p className="text-lw-base font-semibold text-lw-ink">Новый клиент появится здесь сам</p>
          <p className="mt-1 text-lw-base text-lw-muted">
            Как только опишет вопрос боту. Ссылку на бота можно отправить прямо из Telegram —
            собеседнику, в группу или себе на будущее.
          </p>
          <a href={SHARE_BOT_URL} className="lw-btn-quiet mt-3 inline-flex">
            Поделиться ботом
          </a>
        </div>
      ) : null}
    </div>
  );
}
