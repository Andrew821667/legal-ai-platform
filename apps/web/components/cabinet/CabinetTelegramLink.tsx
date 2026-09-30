"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";

type Props =
  | { mode: "code"; email: string | null; botLinkUrl: string; pending?: boolean }
  | { mode: "linked"; username: string | null; linkedAt: string | null }
  | { mode: "sessions"; email: string | null };

async function send(
  method: "POST" | "DELETE",
  body?: object,
): Promise<{ ok: boolean; detail?: string; pending?: boolean }> {
  try {
    const response = await fetch("/api/client/link", {
      method,
      headers: body ? { "content-type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
    const data = (await response.json().catch(() => null)) as { detail?: unknown; pending?: unknown } | null;
    if (response.ok) return { ok: true, pending: data?.pending === true };
    return { ok: false, detail: typeof data?.detail === "string" ? data.detail : "Не получилось. Попробуйте ещё раз." };
  } catch {
    return { ok: false, detail: "Нет связи с сайтом. Попробуйте ещё раз." };
  }
}

function consentText(email: string | null): string {
  const account = email ? `учётной записи ${email}` : "вашей учётной записи";
  return (
    `Нажимая «Объединить», вы соглашаетесь привязать ваш Telegram к ${account}: ` +
    "в кабинете на сайте будут видны дела и документы из Telegram, а в Telegram — заявки с сайта. " +
    "Отвязать можно здесь же в любой момент."
  );
}

const button =
  "inline-flex items-center justify-center rounded-lg px-4 py-2 text-sm font-semibold transition-colors disabled:opacity-50";

/**
 * Объединение входа через Яндекс ID с Telegram (app/api/client/link).
 * code — вошёл через Яндекс ID: код из бота; sessions — в браузере открыты оба
 * входа; linked — уже объединено, можно отвязать.
 */
export default function CabinetTelegramLink(props: Props) {
  const router = useRouter();
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [waiting, setWaiting] = useState(props.mode === "code" && Boolean(props.pending));

  // Код введён — ждём «Да» в боте: спрашиваем сайт, пока не объединится или не отменят.
  useEffect(() => {
    if (!waiting) return;
    const timer = window.setInterval(async () => {
      const response = await fetch("/api/client/link", { cache: "no-store" }).catch(() => null);
      const state = (await response?.json().catch(() => null)) as { linked?: boolean; pending?: boolean } | null;
      if (state?.linked) {
        window.clearInterval(timer);
        router.refresh();
      } else if (state && !state.pending) {
        window.clearInterval(timer);
        setWaiting(false);
        setCode("");
        setError("Объединение отменено в Telegram или запрос устарел. Чтобы попробовать снова, запросите в боте новый код.");
      }
    }, 3000);
    return () => window.clearInterval(timer);
  }, [waiting, router]);

  async function run(method: "POST" | "DELETE", body?: object) {
    setBusy(true);
    setError(null);
    const result = await send(method, body);
    setBusy(false);
    if (result.ok && result.pending) {
      setWaiting(true);
    } else if (result.ok) {
      router.refresh();
    } else {
      setError(result.detail || null);
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    void run("POST", { code });
  }

  if (props.mode === "linked") {
    const since = props.linkedAt ? new Date(props.linkedAt).toLocaleDateString("ru-RU") : null;
    return (
      <div id="telegram" className="scroll-mt-24 rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-slate-700">
        <p className="font-semibold text-slate-900">
          ✅ Telegram объединён{props.username ? ` (@${props.username})` : ""}
          {since ? ` с ${since}` : ""}
        </p>
        <p className="mt-1">Здесь видны ваши дела и документы из Telegram, а в Telegram — заявки с сайта.</p>
        <button
          type="button"
          disabled={busy}
          onClick={() => {
            if (window.confirm("Отвязать Telegram? Дела из Telegram перестанут показываться здесь.")) {
              void run("DELETE");
            }
          }}
          className={`${button} mt-3 border border-slate-300 bg-white text-slate-700 hover:bg-slate-50`}
        >
          Отвязать Telegram
        </button>
        {error ? <p className="mt-2 text-red-700">{error}</p> : null}
      </div>
    );
  }

  if (props.mode === "sessions") {
    return (
      <div id="telegram" className="scroll-mt-24 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-slate-700">
        <p className="font-semibold text-slate-900">Объединить вход через Telegram и через Яндекс ID?</p>
        <p className="mt-1">
          В этом браузере вы вошли и через Telegram, и через Яндекс ID{props.email ? ` (${props.email})` : ""}. После
          объединения можно входить любым способом и видеть одни и те же дела — в том числе без VPN.
        </p>
        <p className="mt-2 text-xs text-slate-500">{consentText(props.email)}</p>
        <button
          type="button"
          disabled={busy}
          onClick={() => void run("POST", { from_session: true })}
          className={`${button} mt-3 bg-amber-600 text-white hover:bg-amber-700`}
        >
          Объединить
        </button>
        {error ? (
          <p className="mt-2 text-red-700">
            {error}{" "}
            <a href="/cabinet/login?next=/cabinet/profile" className="underline">
              Войти через Telegram
            </a>{" "}
            ·{" "}
            <a href="/cabinet/login/yandex?next=/cabinet/profile" className="underline">
              Войти через Яндекс ID
            </a>
          </p>
        ) : null}
      </div>
    );
  }

  if (waiting) {
    return (
      <div id="telegram" className="scroll-mt-24 rounded-xl border border-sky-200 bg-sky-50 p-4 text-sm text-slate-700">
        <p className="font-semibold text-slate-900">📨 Подтвердите объединение в Telegram</p>
        <p className="mt-1">
          Бот прислал вам вопрос с почтой этой учётной записи{props.mode === "code" && props.email ? ` (${props.email})` : ""}.
          Откройте его и нажмите «Да, объединить» — эта страница обновится сама.
        </p>
        {props.mode === "code" ? (
          <a href={props.botLinkUrl.replace(/\?start=.*$/, "")} target="_blank" rel="noreferrer" className="mt-3 inline-block font-semibold text-amber-700 underline">
            Открыть бота
          </a>
        ) : null}
      </div>
    );
  }

  return (
    <form id="telegram" onSubmit={submit} className="scroll-mt-24 rounded-xl border border-slate-300 bg-slate-50 p-4 text-sm text-slate-700">
      <p className="font-semibold text-slate-900">Общались с нами в Telegram? Объедините входы</p>
      <p className="mt-1">Тогда дела и документы из Telegram появятся здесь.</p>
      <ol className="mt-3 list-decimal space-y-2 pl-5">
        <li>
          Получите код в боте:{" "}
          <a href={props.botLinkUrl} target="_blank" rel="noreferrer" className="font-semibold text-amber-700 underline">
            открыть бота
          </a>{" "}
          (или отправьте ему команду /link). Код действует 10 минут.
        </li>
        <li>
          Введите код сюда:
          <input
            value={code}
            onChange={(event) => setCode(event.target.value)}
            placeholder="XXXX-XXXX"
            autoComplete="one-time-code"
            maxLength={32}
            className="mt-2 block w-full max-w-xs rounded-lg border border-slate-300 bg-white px-3 py-2 font-mono tracking-widest text-slate-900 uppercase"
          />
        </li>
      </ol>
      <p className="mt-3 text-xs text-slate-500">{consentText(props.email)}</p>
      <button
        type="submit"
        disabled={busy || !code.trim()}
        className={`${button} mt-3 bg-amber-600 text-white hover:bg-amber-700`}
      >
        Объединить
      </button>
      {error ? <p className="mt-2 text-red-700">{error}</p> : null}
    </form>
  );
}
