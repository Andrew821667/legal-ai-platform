"use client";

import { useCallback, useEffect, useState } from "react";

import ClientCardView from "./ClientCardView";
import TodayView from "./TodayView";
import ClientsView from "./ClientsView";
import { lawyerFetch, useTelegramInitData } from "./useTelegram";
import type { ClientCard, ClientRow, Today } from "./types";

type Tab = "today" | "clients";

export default function LawyerWorkspace() {
  const { initData, ready } = useTelegramInitData();
  const [tab, setTab] = useState<Tab>("today");
  const [today, setToday] = useState<Today | null>(null);
  const [clients, setClients] = useState<ClientRow[] | null>(null);
  const [card, setCard] = useState<ClientCard | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    if (!ready) return;
    setLoading(true);
    setError(null);
    try {
      if (tab === "today") {
        setToday(await lawyerFetch<Today>("/api/lawyer/today", initData));
      } else if (clients === null) {
        setClients(await lawyerFetch<ClientRow[]>("/api/lawyer/clients", initData));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось загрузить данные");
    } finally {
      setLoading(false);
    }
  }, [ready, tab, initData, clients]);

  useEffect(() => {
    void load();
  }, [load]);

  const openClient = useCallback(
    async (leadId: string) => {
      setLoading(true);
      setError(null);
      try {
        setCard(await lawyerFetch<ClientCard>(`/api/lawyer/clients/${leadId}`, initData));
      } catch (err) {
        setError(err instanceof Error ? err.message : "Не удалось открыть карточку");
      } finally {
        setLoading(false);
      }
    },
    [initData],
  );

  const search = useCallback(
    async (term: string) => {
      setLoading(true);
      setError(null);
      try {
        const query = term ? `?search=${encodeURIComponent(term)}` : "";
        setClients(await lawyerFetch<ClientRow[]>(`/api/lawyer/clients${query}`, initData));
      } catch (err) {
        setError(err instanceof Error ? err.message : "Не удалось найти");
      } finally {
        setLoading(false);
      }
    },
    [initData],
  );

  if (card) {
    return (
      <ClientCardView
        card={card}
        onBack={() => setCard(null)}
        loading={loading}
      />
    );
  }

  return (
    <div>
      <header className="mb-4">
        <p className="text-xs uppercase tracking-wide text-slate-500">AI Verdict</p>
        <h1 className="text-xl font-semibold text-white">Рабочее место</h1>
      </header>

      <nav className="mb-4 flex gap-2" role="tablist">
        {(
          [
            ["today", "Сегодня"],
            ["clients", "Клиенты"],
          ] as [Tab, string][]
        ).map(([key, title]) => (
          <button
            key={key}
            type="button"
            role="tab"
            aria-selected={tab === key}
            onClick={() => setTab(key)}
            className={`rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
              tab === key
                ? "bg-amber-500 text-slate-950"
                : "bg-slate-800 text-slate-300 hover:bg-slate-700"
            }`}
          >
            {title}
          </button>
        ))}
      </nav>

      {error ? (
        <div className="rounded-lg border border-rose-900 bg-rose-950/50 p-3 text-sm text-rose-200">
          {error}
          <button
            type="button"
            onClick={() => void load()}
            className="ml-3 underline underline-offset-2"
          >
            Повторить
          </button>
        </div>
      ) : null}

      {loading && !error ? <p className="text-sm text-slate-400">Загружаю…</p> : null}

      {!error && tab === "today" && today ? <TodayView today={today} onOpen={openClient} /> : null}
      {!error && tab === "clients" ? (
        <ClientsView rows={clients} onOpen={openClient} onSearch={search} />
      ) : null}
    </div>
  );
}
