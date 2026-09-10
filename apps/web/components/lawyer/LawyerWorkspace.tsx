"use client";

import { useCallback, useEffect, useState } from "react";

import ClientCardView from "./ClientCardView";
import TodayView from "./TodayView";
import ClientsView from "./ClientsView";
import { lawyerFetch, useTelegramInitData } from "./useTelegram";
import type { ClientCard, ClientRow, Today } from "./types";

type Tab = "clients" | "today";

export default function LawyerWorkspace() {
  const { initData, ready } = useTelegramInitData();
  const [tab, setTab] = useState<Tab>("clients");
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
      // Счётчик задач нужен и на вкладке клиентов: он показывает, что где-то
      // ждут ответа, не заставляя переключаться и проверять.
      if (tab === "clients" && today === null) {
        setToday(await lawyerFetch<Today>("/api/lawyer/today", initData));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось загрузить данные");
    } finally {
      setLoading(false);
    }
  }, [ready, tab, initData, clients, today]);

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

  const pendingCount = today
    ? today.sections.reduce((sum, section) => sum + section.items.length, 0)
    : undefined;

  if (card) {
    return (
      <ClientCardView
        card={card}
        onBack={() => setCard(null)}
        loading={loading}
        initData={initData}
      />
    );
  }

  return (
    <div>
      <header className="mb-4">
        <p className="text-sm uppercase tracking-widest text-slate-600">AI Verdict</p>
        <h1 className="text-2xl font-semibold text-white">Рабочее место</h1>
      </header>

      <nav className="mb-4 flex gap-1 rounded-xl bg-slate-900/70 p-1" role="tablist">
        {(
          [
            ["clients", "Клиенты", clients?.length],
            ["today", "Задачи", pendingCount],
          ] as [Tab, string, number | undefined][]
        ).map(([key, title, count]) => (
          <button
            key={key}
            type="button"
            role="tab"
            aria-selected={tab === key}
            onClick={() => setTab(key)}
            className={`flex flex-1 items-center justify-center gap-1.5 rounded-lg px-3 py-2 text-base font-medium transition-colors ${
              tab === key ? "bg-slate-800 text-white" : "text-slate-400 hover:text-slate-200"
            }`}
          >
            {title}
            {count ? (
              <span
                className={`rounded-full px-1.5 text-sm ${
                  key === "today" ? "bg-amber-500 text-slate-950" : "bg-slate-700 text-slate-300"
                }`}
              >
                {count}
              </span>
            ) : null}
          </button>
        ))}
      </nav>

      {error ? (
        <div className="rounded-lg border border-rose-900 bg-rose-950/50 p-3 text-base text-rose-200">
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

      {loading && !error ? <p className="text-base text-slate-400">Загружаю…</p> : null}

      {!error && tab === "today" && today ? <TodayView today={today} onOpen={openClient} /> : null}
      {!error && tab === "clients" ? (
        <ClientsView rows={clients} onOpen={openClient} onSearch={search} />
      ) : null}
    </div>
  );
}
