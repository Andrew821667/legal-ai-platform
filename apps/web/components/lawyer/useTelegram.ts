"use client";

import { useEffect, useState } from "react";

/**
 * Доступ к окружению Telegram.
 *
 * initData передаётся на сервер заголовком и там проверяется по подписи.
 * Полагаться на то, что говорит о себе клиентский код, нельзя: страницу можно
 * открыть и вне Telegram.
 */

type TelegramBackButton = {
  show: () => void;
  hide: () => void;
  onClick: (handler: () => void) => void;
  offClick: (handler: () => void) => void;
};

type TelegramWebApp = {
  initData?: string;
  /** «ios», «android», «tdesktop», «weba»…; «unknown» — страница открыта не в Telegram. */
  platform?: string;
  ready?: () => void;
  expand?: () => void;
  colorScheme?: string;
  BackButton?: TelegramBackButton;
  setHeaderColor?: (color: string) => void;
  setBackgroundColor?: (color: string) => void;
};

/** Нативная кнопка «назад» Telegram — та, что в шапке мини-аппа. */
export function telegramBackButton(): TelegramBackButton | undefined {
  return window.Telegram?.WebApp?.BackButton;
}

declare global {
  interface Window {
    Telegram?: { WebApp?: TelegramWebApp };
    /** Мост в нативное приложение — есть только внутри WebView Telegram. */
    TelegramWebviewProxy?: unknown;
  }
}

/**
 * Открыто ли внутри Telegram. Раньше об этом судили по initData, но кнопка
 * reply-клавиатуры открывает Mini App с пустым initData — а это всё ещё
 * Telegram, где скачивание не работает и файлы надо слать в чат.
 */
function detectInsideTelegram(app: TelegramWebApp | undefined): boolean {
  if (typeof window !== "undefined" && window.TelegramWebviewProxy !== undefined) return true;
  const platform = app?.platform || "unknown";
  return platform !== "unknown";
}

export function useTelegramInitData(): { initData: string; ready: boolean; insideTelegram: boolean } {
  const [initData, setInitData] = useState("");
  const [insideTelegram, setInsideTelegram] = useState(false);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const app = window.Telegram?.WebApp;
    app?.ready?.();
    app?.expand?.();
    // Шапка и подложка Telegram — в цвет страницы, иначе над светлым экраном
    // остаётся тёмная полоса от прежней темы.
    app?.setHeaderColor?.("#f7f8fb");
    app?.setBackgroundColor?.("#f7f8fb");
    setInitData(app?.initData || "");
    setInsideTelegram(detectInsideTelegram(app));
    setReady(true);
  }, []);

  return { initData, ready, insideTelegram };
}

/** Ошибка запроса с кодом: 401 значит «нет входа», и экран должен это отличать. */
export class LawyerFetchError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

export async function lawyerFetch<T>(path: string, initData: string): Promise<T> {
  const response = await fetch(path, {
    headers: { "x-telegram-init-data": initData },
    cache: "no-store",
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new LawyerFetchError(body?.detail || `Ошибка ${response.status}`, response.status);
  }
  return body as T;
}

export async function lawyerAction<T>(
  path: string,
  initData: string,
  payload?: unknown,
  method: "POST" | "DELETE" = "POST",
): Promise<T> {
  const response = await fetch(path, {
    method,
    headers: {
      "x-telegram-init-data": initData,
      ...(payload === undefined ? {} : { "content-type": "application/json" }),
    },
    body: payload === undefined ? undefined : JSON.stringify(payload),
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body?.detail || `Ошибка ${response.status}`);
  }
  return body as T;
}
