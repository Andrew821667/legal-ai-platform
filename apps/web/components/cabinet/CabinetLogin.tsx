import { ShieldCheck } from "lucide-react";

import { EXTERNAL_LINKS } from "@/lib/links";
import type { TelegramLoginMode } from "@/lib/telegram-login-mode";

import TelegramLoginWidget from "./TelegramLoginWidget";

const REASON_TEXT: Record<string, string> = {
  denied: "Вход отменён. Попробуйте ещё раз, когда будете готовы.",
  email: "Яндекс не передал адрес почты. При входе разрешите доступ к почте — по ней кабинет находит ваши дела.",
  conflict: "Эта почта уже привязана к другому аккаунту Яндекса. Войдите тем аккаунтом или напишите юристу.",
  state: "Сессия входа устарела или была открыта в другой вкладке. Попробуйте ещё раз.",
  exchange: "Сервис входа не ответил. Попробуйте ещё раз через минуту.",
  token: "Вход не подтверждён. Попробуйте ещё раз.",
  profile: "Не удалось получить профиль. Попробуйте ещё раз.",
  required: "Для этой страницы нужно сначала войти.",
  stale: "Сеанс кабинета истёк. Войдите ещё раз.",
  ratelimit: "Слишком много попыток входа. Подождите немного и повторите.",
  misconfigured: "Вход временно недоступен — сообщите об этом администратору.",
};

export default function CabinetLogin({
  mode,
  botUsername,
  reason,
  yandexEnabled = false,
}: {
  mode: TelegramLoginMode;
  botUsername: string;
  reason?: string;
  /** Вход через Яндекс ID настроен — он главный: Telegram в России без VPN не открывается. */
  yandexEnabled?: boolean;
}) {
  const hint = reason ? REASON_TEXT[reason] : undefined;

  return (
    <section className="rounded-2xl border border-slate-300 bg-white p-6 text-center shadow-sm sm:p-10">
      <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-amber-50">
        <ShieldCheck className="h-6 w-6 text-amber-600" />
      </div>
      <h1 className="mt-4 text-2xl font-semibold text-slate-900">Личный кабинет</h1>
      <p className="mx-auto mt-2 max-w-md text-sm text-slate-600">
        Войдите, чтобы увидеть свои обращения, договоры, акты и NDA.
      </p>

      {hint ? (
        <p className="mx-auto mt-4 max-w-md rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-800">
          {hint}
        </p>
      ) : null}

      <div className="mt-6 flex flex-col items-center gap-3">
        {yandexEnabled ? (
          <a
            href="/cabinet/login/yandex"
            className="inline-flex min-w-64 items-center justify-center rounded-lg bg-amber-600 px-5 py-3 text-sm font-semibold text-white transition-colors hover:bg-amber-700"
          >
            Войти с Яндекс ID
          </a>
        ) : null}
        {mode === "oidc" ? (
          <a
            href="/cabinet/login"
            className={
              yandexEnabled
                ? "inline-flex min-w-64 items-center justify-center rounded-lg border border-slate-300 px-5 py-3 text-sm font-semibold text-slate-700 transition-colors hover:bg-slate-50"
                : "inline-flex items-center justify-center rounded-lg bg-amber-600 px-5 py-3 text-sm font-semibold text-white transition-colors hover:bg-amber-700"
            }
          >
            Войти через Telegram
          </a>
        ) : (
          <TelegramLoginWidget botUsername={botUsername} />
        )}
        {yandexEnabled ? (
          <p className="max-w-md text-xs text-slate-500">
            Через Telegram — если он у вас открывается. Если нет, входите с Яндекс ID: дела с сайта
            найдутся по вашей почте.
          </p>
        ) : null}
      </div>

      <p className="mt-6 text-xs text-slate-500">
        Ещё нет диалога с ботом?{" "}
        <a href={EXTERNAL_LINKS.leadBot} className="font-semibold text-amber-700 underline">
          Откройте бота-ассистента
        </a>{" "}
        — оттуда тоже можно перейти в кабинет.
      </p>
    </section>
  );
}
