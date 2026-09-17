import { ShieldCheck } from "lucide-react";

import { EXTERNAL_LINKS } from "@/lib/links";
import type { TelegramLoginMode } from "@/lib/telegram-login-mode";

import TelegramLoginWidget from "./TelegramLoginWidget";

const REASON_TEXT: Record<string, string> = {
  denied: "Вход отменён в Telegram. Попробуйте ещё раз, когда будете готовы.",
  state: "Сессия входа устарела или была открыта в другой вкладке. Попробуйте ещё раз.",
  exchange: "Telegram не ответил на запрос входа. Попробуйте ещё раз через минуту.",
  token: "Telegram не подтвердил вход. Попробуйте ещё раз.",
  profile: "Не удалось получить профиль из Telegram. Попробуйте ещё раз.",
  required: "Для этой страницы нужно сначала войти.",
  stale: "Сеанс кабинета истёк. Войдите ещё раз.",
  ratelimit: "Слишком много попыток входа. Подождите немного и повторите.",
  misconfigured: "Вход временно недоступен — сообщите об этом администратору.",
};

export default function CabinetLogin({
  mode,
  botUsername,
  reason,
}: {
  mode: TelegramLoginMode;
  botUsername: string;
  reason?: string;
}) {
  const hint = reason ? REASON_TEXT[reason] : undefined;

  return (
    <section className="rounded-2xl border border-slate-300 bg-white p-6 text-center shadow-sm sm:p-10">
      <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-amber-50">
        <ShieldCheck className="h-6 w-6 text-amber-600" />
      </div>
      <h1 className="mt-4 text-2xl font-semibold text-slate-900">Личный кабинет</h1>
      <p className="mx-auto mt-2 max-w-md text-sm text-slate-600">
        Войдите через Telegram, чтобы увидеть свои обращения, договоры, акты и NDA — так же, как в
        боте-ассистенте, но на сайте.
      </p>

      {hint ? (
        <p className="mx-auto mt-4 max-w-md rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-800">
          {hint}
        </p>
      ) : null}

      <div className="mt-6">
        {mode === "oidc" ? (
          <a
            href="/cabinet/login"
            className="inline-flex items-center justify-center rounded-lg bg-amber-600 px-5 py-3 text-sm font-semibold text-white transition-colors hover:bg-amber-700"
          >
            Войти через Telegram
          </a>
        ) : (
          <TelegramLoginWidget botUsername={botUsername} />
        )}
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
