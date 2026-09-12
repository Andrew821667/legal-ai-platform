"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import ClientCardView from "./ClientCardView";
import FinanceView from "./FinanceView";
import TodayView from "./TodayView";
import ClientsView from "./ClientsView";
import { formatRub } from "@/lib/money";
import { LawyerFetchError, lawyerFetch, telegramBackButton, useTelegramInitData } from "./useTelegram";
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
function todayLabel(): string {
  return new Date().toLocaleDateString("ru-RU", { weekday: "long", day: "numeric", month: "long" });
}

function syncAddress(route: WorkspaceRoute, mode: "push" | "replace") {
  const url = `${window.location.pathname}${buildWorkspaceSearch(route)}`;
  const state = { pushed: mode === "push" };
  if (mode === "push") window.history.pushState(state, "", url);
  else window.history.replaceState(state, "", url);
}

export default function LawyerWorkspace() {
  const { initData, ready, insideTelegram } = useTelegramInitData();
  const [tab, setTab] = useState<Tab>("clients");
  const [today, setToday] = useState<Today | null>(null);
  const [finance, setFinance] = useState<Finance | null>(null);
  const [clients, setClients] = useState<ClientRow[] | null>(null);
  const [card, setCard] = useState<ClientCard | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [unauthorized, setUnauthorized] = useState(false);

  // «Загружаю…» — пока в пути хоть один запрос. Раньше это был один флаг на
  // четыре загрузчика: стартовые три уходили разом, первый вернувшийся
  // гасил индикатор для остальных, а обновление после действия — наоборот,
  // включало его над давно готовым экраном. Счётчик, а не флаг.
  const [loading, setLoading] = useState(false);
  const inflight = useRef(0);
  const beginLoading = useCallback(() => {
    inflight.current += 1;
    setLoading(true);
  }, []);
  const endLoading = useCallback(() => {
    inflight.current = Math.max(0, inflight.current - 1);
    if (inflight.current === 0) setLoading(false);
  }, []);

  // Два независимых загрузчика — не читают состояние друг друга и не входят
  // в зависимости друг друга. Раньше был один load() с [tab, clients, today]
  // в зависимостях: setToday() внутри него менял today, today менял identity
  // самого load, а это снова запускало useEffect([load]) — на вкладке
  // «Задачи» цикл ничем не был ограничен и на проде долбил сервер сотнями
  // запросов в секунду, пока вкладка открыта.
  const loadToday = useCallback(async () => {
    if (!ready) return;
    beginLoading();
    setError(null);
    setUnauthorized(false);
    try {
      setToday(await lawyerFetch<Today>("/api/lawyer/today", initData));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось загрузить данные");
      setUnauthorized(err instanceof LawyerFetchError && err.status === 401);
    } finally {
      endLoading();
    }
  }, [ready, initData, beginLoading, endLoading]);

  // Последний поисковый запрос живёт в ref, а не в состоянии: обновление после
  // действия должно сохранять фильтр, но не менять identity загрузчика — иначе
  // эффект начнёт перезапускаться на каждый поиск.
  const lastSearch = useRef("");

  // Тот же контракт, что у loadToday: зависит только от ready/initData и не
  // читает состояние, которое сам меняет, — иначе вернётся цикл из #340.
  const loadFinance = useCallback(async () => {
    if (!ready) return;
    beginLoading();
    setError(null);
    try {
      setFinance(await lawyerFetch<Finance>("/api/lawyer/finance", initData));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось загрузить деньги");
      setUnauthorized(err instanceof LawyerFetchError && err.status === 401);
    } finally {
      endLoading();
    }
  }, [ready, initData, beginLoading, endLoading]);

  const loadClients = useCallback(
    async (search = lastSearch.current) => {
      if (!ready) return;
      lastSearch.current = search;
      beginLoading();
      setError(null);
      setUnauthorized(false);
      try {
        const query = search ? `?search=${encodeURIComponent(search)}` : "";
        setClients(await lawyerFetch<ClientRow[]>(`/api/lawyer/clients${query}`, initData));
      } catch (err) {
        setError(err instanceof Error ? err.message : "Не удалось найти");
        setUnauthorized(err instanceof LawyerFetchError && err.status === 401);
      } finally {
        endLoading();
      }
    },
    [ready, initData, beginLoading, endLoading],
  );

  // Стартовая загрузка: клиенты — для списка, задачи — для счётчика на
  // вкладке «Клиенты» (он показывает, что где-то ждут ответа, не заставляя
  // переключаться и проверять). Оба загрузчика стабильны по identity, пока
  // не меняются ready/initData, — эффект не перезапускает сам себя.
  useEffect(() => {
    void loadClients();
    void loadToday();
    void loadFinance();
  }, [loadClients, loadToday, loadFinance]);

  // При каждом переходе на «Задачи» — свежие данные, а не то, что было при
  // первом заходе в раздел.
  useEffect(() => {
    if (tab === "today") void loadToday();
    if (tab === "finance") void loadFinance();
  }, [tab, loadToday, loadFinance]);

  const openClient = useCallback(
    async (leadId: string) => {
      beginLoading();
      setError(null);
      try {
        setCard(await lawyerFetch<ClientCard>(`/api/lawyer/clients/${leadId}`, initData));
      } catch (err) {
        setError(err instanceof Error ? err.message : "Не удалось открыть карточку");
      } finally {
        endLoading();
      }
    },
    [initData, beginLoading, endLoading],
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
  const [loginHint, setLoginHint] = useState<string | null>(null);
  useEffect(() => {
    if (!ready || landed.current) return;
    landed.current = true;
    // /lawyer/login отправляет сюда с причиной, если токен не подошёл.
    setLoginHint(new URLSearchParams(window.location.search).get("login"));
    const route = parseWorkspaceRoute(window.location.search);
    setTab(route.tab);
    syncAddress(route, "replace");
    if (route.client) void openClient(route.client);
  }, [ready, openClient]);

  // Кнопка reply-клавиатуры Telegram открывает Mini App с пустым initData —
  // так устроен Telegram. Обычно её адрес несёт токен входа, и сюда мы не
  // попадаем; если попали — токен устарел или Telegram открыл голый адрес.
  const noIdentity = ready && initData === "" && unauthorized;
  const guidance =
    loginHint === "denied"
      ? "Этот вход не для вашего аккаунта."
      : loginHint === "stale"
        ? "Ссылка в кнопке устарела. Отправьте боту /admin — кнопка обновится и вход заработает."
        : "Открыто без данных входа. В Telegram отправьте боту /admin — кнопка внизу обновится; в браузере возьмите там же новую «Ссылку для Safari».";

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
  const tabIsEmpty =
    tab === "today" ? today === null : tab === "finance" ? finance === null : clients === null;

  const list = (
    <div>
      {/* Шапка как в «Судебных делах»: день, крупный заголовок и четыре
          числа, ради которых экран и открывают между встречами. */}
      <header className="lw-hero mb-4 p-5">
        <p className="lw-eyebrow">{todayLabel()}</p>
        <h1 className="mt-1 text-lw-3xl font-extrabold tracking-tight text-lw-ink">Рабочее место</h1>
        <p className="mt-2 text-lw-base text-lw-muted">
          {pendingCount
            ? `Ждут вашего ответа: ${pendingCount}. Ниже — клиенты, задачи и деньги практики.`
            : "Ничего не ждёт вашего ответа. Ниже — клиенты, задачи и деньги практики."}
        </p>
        <div className="mt-4 grid grid-cols-2 gap-2.5">
          {(
            [
              [clients?.length ?? "—", "клиентов"],
              [pendingCount ?? 0, "ждут ответа"],
              [finance?.in_pipeline.count ?? "—", "договоров у клиентов"],
              [finance ? formatRub(finance.signed_this_month.minor) : "—", "подписано в этом месяце"],
            ] as [React.ReactNode, string][]
          ).map(([value, caption]) => (
            <div key={caption} className="rounded-2xl border border-lw-border bg-white/80 px-4 py-3">
              <p className="text-lw-xl font-extrabold tabular-nums text-lw-ink">{value}</p>
              <p className="mt-0.5 text-lw-sm text-lw-muted">{caption}</p>
            </div>
          ))}
        </div>
      </header>

      <nav className="mb-4 flex gap-2" role="tablist">
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
            className={`flex flex-1 items-center justify-center gap-2 rounded-full px-3 py-3 text-lw-base font-semibold transition-colors ${
              tab === key
                ? "bg-lw-primary text-white shadow-lw-card"
                : "lw-card text-lw-ink hover:bg-lw-blue-soft"
            }`}
          >
            {title}
            {count ? (
              <span
                className={`rounded-full px-2 text-lw-sm font-bold ${
                  tab === key
                    ? "bg-white/20 text-white"
                    : key === "today"
                      ? "bg-lw-danger-soft text-lw-danger"
                      : "bg-lw-primary-soft text-lw-primary"
                }`}
              >
                {count}
              </span>
            ) : null}
          </button>
        ))}
      </nav>

      {noIdentity ? (
        <div className="lw-card p-4 text-lw-base text-lw-ink">
          <p className="font-semibold">Нужен вход</p>
          <p className="mt-1 text-lw-muted">{guidance}</p>
        </div>
      ) : error ? (
        <div className="rounded-lg border border-lw-danger/30 bg-lw-danger-soft p-3 text-lw-base text-lw-danger">
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

      {/* Индикатор — только пока показывать нечего. Обновление поверх готового
          экрана идёт молча: данные просто сменяются на свежие. */}
      {loading && !error && !card && tabIsEmpty ? (
        <p className="text-lw-base text-lw-muted">Загружаю…</p>
      ) : null}

      {!error && tab === "today" && today ? <TodayView today={today} onOpen={showClient} /> : null}
      {!error && tab === "finance" && finance ? (
        <FinanceView
          finance={finance}
          onOpen={showClient}
          initData={initData}
          insideTelegram={insideTelegram}
        />
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
            onOpenClient={showClient}
            loading={loading}
            initData={initData}
            insideTelegram={insideTelegram}
          />
        ) : (
          <div className="mt-16 rounded-3xl border border-dashed border-lw-border-strong p-10 text-center">
            <p className="text-lw-lg font-semibold text-lw-ink">Карточка клиента откроется здесь</p>
            <p className="mt-1 text-lw-base text-lw-muted">Выберите клиента, задачу или договор слева.</p>
          </div>
        )}
      </div>
    </div>
  );
}
