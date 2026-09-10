"use client";

import { useCallback, useEffect, useRef, useState } from "react";

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

  // Два независимых загрузчика — не читают состояние друг друга и не входят
  // в зависимости друг друга. Раньше был один load() с [tab, clients, today]
  // в зависимостях: setToday() внутри него менял today, today менял identity
  // самого load, а это снова запускало useEffect([load]) — на вкладке
  // «Задачи» цикл ничем не был ограничен и на проде долбил сервер сотнями
  // запросов в секунду, пока вкладка открыта.
  const loadToday = useCallback(async () => {
    if (!ready) return;
    setLoading(true);
    setError(null);
    try {
      setToday(await lawyerFetch<Today>("/api/lawyer/today", initData));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось загрузить данные");
    } finally {
      setLoading(false);
    }
  }, [ready, initData]);

  // Последний поисковый запрос живёт в ref, а не в состоянии: обновление после
  // действия должно сохранять фильтр, но не менять identity загрузчика — иначе
  // эффект начнёт перезапускаться на каждый поиск.
  const lastSearch = useRef("");

  const loadClients = useCallback(
    async (search = lastSearch.current) => {
      if (!ready) return;
      lastSearch.current = search;
      setLoading(true);
      setError(null);
      try {
        const query = search ? `?search=${encodeURIComponent(search)}` : "";
        setClients(await lawyerFetch<ClientRow[]>(`/api/lawyer/clients${query}`, initData));
      } catch (err) {
        setError(err instanceof Error ? err.message : "Не удалось найти");
      } finally {
        setLoading(false);
      }
    },
    [ready, initData],
  );

  // Стартовая загрузка: клиенты — для списка, задачи — для счётчика на
  // вкладке «Клиенты» (он показывает, что где-то ждут ответа, не заставляя
  // переключаться и проверять). Оба загрузчика стабильны по identity, пока
  // не меняются ready/initData, — эффект не перезапускает сам себя.
  useEffect(() => {
    void loadClients();
    void loadToday();
  }, [loadClients, loadToday]);

  // При каждом переходе на «Задачи» — свежие данные, а не то, что было при
  // первом заходе в раздел.
  useEffect(() => {
    if (tab === "today") void loadToday();
  }, [tab, loadToday]);

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

  // После любого действия внутри карточки экран обязан говорить правду.
  // Раньше пилюля статуса продолжала показывать «Черновик» рядом с надписью
  // «Отправлено», а счётчик задач не менялся, пока не переоткроешь карточку.
  const refreshAfterAction = useCallback(
    async (leadId: string) => {
      await Promise.all([openClient(leadId), loadToday(), loadClients()]);
    },
    [openClient, loadToday, loadClients],
  );

  const pendingCount = today
    ? today.sections.reduce((sum, section) => sum + section.items.length, 0)
    : undefined;

  if (card) {
    return (
      <ClientCardView
        card={card}
        onBack={() => setCard(null)}
        onChanged={() => void refreshAfterAction(card.lead_id)}
        loading={loading}
        initData={initData}
      />
    );
  }

  return (
    <div>
      <header className="mb-4">
        <p className="text-sm uppercase tracking-widest text-slate-400">AI Verdict</p>
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
            onClick={() => void (tab === "today" ? loadToday() : loadClients())}
            className="ml-3 underline underline-offset-2"
          >
            Повторить
          </button>
        </div>
      ) : null}

      {loading && !error ? <p className="text-base text-slate-400">Загружаю…</p> : null}

      {!error && tab === "today" && today ? <TodayView today={today} onOpen={openClient} /> : null}
      {!error && tab === "clients" ? (
        <ClientsView rows={clients} onOpen={openClient} onSearch={(term) => void loadClients(term)} />
      ) : null}
    </div>
  );
}
