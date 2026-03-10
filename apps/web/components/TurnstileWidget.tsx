"use client";

import { useEffect, useRef } from "react";

declare global {
  interface Window {
    turnstile?: {
      render: (
        container: HTMLElement,
        options: {
          sitekey: string;
          theme?: "light" | "dark" | "auto";
          callback?: (token: string) => void;
          "expired-callback"?: () => void;
          "error-callback"?: () => void;
        },
      ) => string;
      remove?: (widgetId: string) => void;
      reset?: (widgetId: string) => void;
    };
  }
}

type TurnstileWidgetProps = {
  siteKey: string;
  enabled: boolean;
  onToken: (token: string) => void;
};

export default function TurnstileWidget({ siteKey, enabled, onToken }: TurnstileWidgetProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const widgetIdRef = useRef<string | null>(null);

  useEffect(() => {
    onToken("");

    if (!enabled || !siteKey) {
      if (widgetIdRef.current && window.turnstile?.remove) {
        window.turnstile.remove(widgetIdRef.current);
        widgetIdRef.current = null;
      }
      return;
    }

    let cancelled = false;

    const mountWidget = () => {
      if (cancelled || !containerRef.current || !window.turnstile || widgetIdRef.current) {
        return;
      }

      widgetIdRef.current = window.turnstile.render(containerRef.current, {
        sitekey: siteKey,
        theme: "light",
        callback: (token: string) => onToken(token),
        "expired-callback": () => {
          onToken("");
          if (widgetIdRef.current && window.turnstile?.reset) {
            window.turnstile.reset(widgetIdRef.current);
          }
        },
        "error-callback": () => onToken(""),
      });
    };

    const existingScript = document.querySelector<HTMLScriptElement>('script[data-turnstile-script="1"]');
    if (existingScript) {
      if (window.turnstile) {
        mountWidget();
      } else {
        existingScript.addEventListener("load", mountWidget, { once: true });
      }
    } else {
      const script = document.createElement("script");
      script.src = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";
      script.async = true;
      script.defer = true;
      script.dataset.turnstileScript = "1";
      script.addEventListener("load", mountWidget, { once: true });
      document.head.appendChild(script);
    }

    return () => {
      cancelled = true;
      onToken("");
      if (widgetIdRef.current && window.turnstile?.remove) {
        window.turnstile.remove(widgetIdRef.current);
        widgetIdRef.current = null;
      }
    };
  }, [enabled, onToken, siteKey]);

  if (!enabled || !siteKey) {
    return null;
  }

  return (
    <div className="rounded-lg border border-slate-200 bg-white px-4 py-3">
      <p className="mb-3 text-sm text-slate-600">
        Подтвердите, что заявку отправляет человек.
      </p>
      <div ref={containerRef} />
    </div>
  );
}
