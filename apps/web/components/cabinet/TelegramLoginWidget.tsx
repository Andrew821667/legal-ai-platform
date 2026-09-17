"use client";

import { useEffect, useRef } from "react";

/**
 * Legacy iframe-виджет Telegram Login. Собирается через next/script нельзя:
 * telegram-widget.js ищет свой <script data-telegram-login=...> тег в DOM и
 * вставляет iframe СРАЗУ ПОСЛЕ него — next/script переносит скрипты в
 * <head>, и iframe оказался бы не там, где ожидает разметка. Поэтому тег
 * создаётся и вставляется вручную в контейнер-ref.
 */
export default function TelegramLoginWidget({ botUsername }: { botUsername: string }) {
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    container.innerHTML = "";

    // window.location.origin — реальный адрес, каким его видит браузер
    // (тот же, что дальше проверит побайтное совпадение redirect_uri), а не
    // адрес процесса Next.js за Caddy.
    const authUrl = `${window.location.origin}/cabinet/callback/legacy`;
    const script = document.createElement("script");
    script.src = "https://telegram.org/js/telegram-widget.js?22";
    script.async = true;
    script.setAttribute("data-telegram-login", botUsername);
    script.setAttribute("data-size", "large");
    script.setAttribute("data-auth-url", authUrl);
    script.setAttribute("data-request-access", "write");
    container.appendChild(script);

    return () => {
      container.innerHTML = "";
    };
  }, [botUsername]);

  return <div ref={containerRef} className="flex justify-center" />;
}
