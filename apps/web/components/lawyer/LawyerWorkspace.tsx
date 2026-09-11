"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import ClientCardView from "./ClientCardView";
import FinanceView from "./FinanceView";
import TodayView from "./TodayView";
import ClientsView from "./ClientsView";
import { lawyerFetch, telegramBackButton, useTelegramInitData } from "./useTelegram";
import type { ClientCard, ClientRow, Finance, Today } from "./types";
import { buildWorkspaceSearch, parseWorkspaceRoute } from "@/lib/lawyer-route";
import type { Tab, WorkspaceRoute } from "@/lib/lawyer-route";

/**
 * Экран живёт в адресе: `?client=<id>` — карточка, `?tab=today` — вкладка.
 *
 * Вкладки не создают записей в истории (replaceState): «назад» с вкладки
 * закрывает мини-апп, как в любом мобильном приложении. Карточка — создаёт
 * (pushState): «назад» из неё возвращает туда, откуда пришли. Исключение —
 * приземление по прямой ссылке из уведомления: за карточкой ничего нет, и
 * history.back() закрыл бы мини-апп целиком, поэтому такая запись помечена
 * как не наша, и «назад» просто подменяет адрес на список.
 */
function syncAddress(route: WorkspaceRoute, mode: "push" | "replace") {
  const url = `${window.location.pathname}${buildWorkspaceSearch(route)}`;
  const state = { pushed: mode === "push" };
  if (mode === "push") window.history.pushState(state, "", url);
  else window.history.replaceState(state, "", url);
}

export default function LawyerWorkspace() {
  const { initData, ready } = useTelegramInitData();
  const [tab, setTab] = useState<Tab>("clients");
  const [today, setToday] = useState<Today | null>(null);
  const [finance, setFinance] = useState<Finance | null>(null);
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

  // Тот же контракт, что у loadToday: зависит только от ready/initData и не
  // читает состояние, которое сам меняет, — иначе вернётся цикл из #340.
  const loadFinance = useCallback(async () => {
    if (!ready) return;
    setLoading(true);
    setError(null);
    try {
      setFinance(await lawyerFetch<Finance>("/api/lawyer/finance", initData));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось загрузить деньги");
    } finally {
      setLoading(false);
    }
  }, [ready, initData]);

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
    if (tab === "finance") void loadFinance();
  }, [tab, loadToday, loadFinance]);

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

  // Открыть карточку по нажатию — с записью в историю.
  const showClient = useCallback(
    (leadId: string) => {
      syncAddress({ tab, client: leadId }, "push");
      void openClient(leadId);
    },
    [tab, openClient],
  );

  const closeCard = useCallback(() => {
    if (window.history.state?.pushed) {
      // Запись наша — назад по истории, popstate восстановит вкладку.
      window.history.back();
      return;
    }
    syncAddress({ tab, client: null }, "replace");
    setCard(null);
  }, [tab]);

  const selectTab = useCallback((next: Tab) => {
    setTab(next);
    syncAddress({ tab: next, client: null }, "replace");
  }, []);

  // Приземление: адрес читается один раз, когда есть чем подписать запрос.
  // Ref, а не состояние: эффект не должен перезапускаться от смены identity
  // openClient — тот самый класс ошибок, что чинили в #340.
  const landed = useRef(false);
  useEffect(() => {
    if (!ready || landed.current) return;
    landed.current = true;
    const route = parseWorkspaceRoute(window.location.search);
    setTab(route.tab);
    syncAddress(route, "replace");
    if (route.client) void openClient(route.client);
  }, [ready, openClient]);

  // Кнопка «назад» браузера или Telegram: состояние — из адреса, не наоборот.
  useEffect(() => {
    const onPop = () => {
      const route = parseWorkspaceRoute(window.location.search);
      setTab(route.tab);
      if (route.client) void openClient(route.client);
      else setCard(null);
    };
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, [openClient]);

  // Нативная кнопка «назад» Telegram видна только в карточке. Без неё жест
  // «назад» закрывал мини-апп целиком — работала лишь ссылка «К списку».
  useEffect(() => {
    const back = telegramBackButton();
    if (!back) return;
    if (!card) {
      back.hide();
      return;
    }
    back.show();
    back.onClick(closeCard);
    return () => back.offClick(closeCard);
  }, [card, closeCard]);

  // После любого действия внутри карточки экран обязан говорить правду.
  // Раньше пилюля статуса продолжала показывать «Черновик» рядом с надписью
  // «Отправлено», а счётчик задач не менялся, пока не переоткроешь карточку.
  const refreshAfterAction = useCallback(
    async (leadId: string) => {
      await Promise.all([openClient(leadId), loadToday(), loadClients(), loadFinance()]);
    },
    [openClient, loadToday, loadClients, loadFinance],
  );

  const pendingCount = today
    ? today.sections.reduce((sum, section) => sum + section.items.length, 0)
    : undefined;

  const list = (
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
            ["finance", "Деньги", undefined],
          ] as [Tab, string, number | undefined][]
        ).map(([key, title, count]) => (
          <button
            key={key}
            type="button"
            role="tab"
            aria-selected={tab === key}
            onClick={() => selectTab(key)}
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
            onClick={() =>
              void (tab === "today" ? loadToday() : tab === "finance" ? loadFinance() : loadClients())
            }
            className="ml-3 underline underline-offset-2"
          >
            Повторить
          </button>
        </div>
      ) : null}

      {loading && !error && !card ? <p className="text-base text-slate-400">Загружаю…</p> : null}

      {!error && tab === "today" && today ? <TodayView today={today} onOpen={showClient} /> : null}
      {!error && tab === "finance" && finance ? (
        <FinanceView finance={finance} onOpen={showClient} />
      ) : null}
      {!error && tab === "clients" ? (
        <ClientsView
          rows={clients}
          onOpen={showClient}
          onSearch={(term) => void loadClients(term)}
          selectedId={card?.lead_id ?? null}
        />
      ) : null}
    </div>
  );

  // Телефон: карточка вместо списка. Ноутбук: список слева, карточка справа —
  // это данные вида «выбрал в списке, читаешь рядом», и раньше на широком
  // экране они лежали одним мобильным столбцом посреди пустоты.
  return (
    <div className="lg:grid lg:grid-cols-[minmax(360px,420px)_minmax(0,1fr)] lg:items-start lg:gap-8">
      <div
        className={`${card ? "hidden lg:block" : ""} lg:sticky lg:top-5 lg:max-h-[calc(100vh-2.5rem)] lg:overflow-y-auto lg:pr-1`}
      >
        {list}
      </div>
      <div className={card ? "" : "hidden lg:block"}>
        {card ? (
          <ClientCardView
            card={card}
            onBack={closeCard}
            onChanged={() => void refreshAfterAction(card.lead_id)}
            loading={loading}
            initData={initData}
          />
        ) : (
          <div className="mt-16 rounded-2xl border border-dashed border-slate-800 p-10 text-center">
            <p className="text-lg font-medium text-slate-300">Карточка клиента откроется здесь</p>
            <p className="mt-1 text-base text-slate-400">Выберите клиента, задачу или договор слева.</p>
          </div>
        )}
      </div>
    </div>
  );
}
