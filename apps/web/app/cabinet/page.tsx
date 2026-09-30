import Link from "next/link";

import CabinetHome from "@/components/cabinet/CabinetHome";
import CabinetLogin from "@/components/cabinet/CabinetLogin";
import { isStaffTelegramId } from "@/lib/cabinet-admin";
import { fetchClientAccount, type ClientAccountInfo } from "@/lib/client-core";
import { LEAD_BOT_USERNAME } from "@/lib/links";
import { readClientSession, type ClientSession } from "@/lib/client-session-server";
import { telegramLoginMode } from "@/lib/telegram-login-mode";

export const dynamic = "force-dynamic";

/**
 * Вошёл через Яндекс ID, а дела — в Telegram: без подсказки клиент увидит
 * пустой кабинет и решит, что всё пропало. Сам блок объединения — в профиле.
 */
function LinkHint({ session, account }: { session: ClientSession; account: ClientAccountInfo | null }) {
  if (!account || account.telegram_user_id) return null;
  const text = session.telegramUserId
    ? "Вы вошли и через Telegram, и через Яндекс ID. Объедините входы — и дела будут одни и те же при любом входе."
    : "Общались с нами в Telegram? Объедините входы — и дела и документы из Telegram появятся здесь.";
  return (
    <p className="mb-4 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-slate-700">
      {text}{" "}
      <Link href="/cabinet/profile#telegram" prefetch={false} className="font-semibold text-amber-700 underline">
        Объединить
      </Link>
    </p>
  );
}

/** Администратор — не клиент: вместо дел и клиентских форм — путь в рабочее место. */
function AdminCabinet({ email }: { email: string | null }) {
  return (
    <section className="rounded-2xl border border-slate-300 bg-white p-6 shadow-sm sm:p-10">
      <p className="text-sm font-semibold uppercase tracking-wide text-amber-700">Администратор</p>
      <h1 className="mt-1 text-2xl font-semibold text-slate-900">Вы вошли как администратор</h1>
      <p className="mt-3 text-sm leading-6 text-slate-600">
        Это кабинет клиентов: здесь они подписывают NDA, дают согласие на обработку данных и заполняют
        реквизиты. Вам эти формы не нужны — дела клиентов в рабочем месте юриста.
        {email ? ` Учётная запись сайта: ${email}.` : ""}
      </p>
      <div className="mt-6 flex flex-wrap items-center gap-3">
        <a
          href="/lawyer"
          className="inline-flex items-center justify-center rounded-lg bg-amber-600 px-4 py-2 text-sm font-semibold text-white hover:bg-amber-700"
        >
          Рабочее место юриста
        </a>
        <Link href="/cabinet/profile" prefetch={false} className="text-sm font-semibold text-amber-700 underline">
          Профиль и Telegram
        </Link>
      </div>
      <p className="mt-4 text-xs text-slate-500">Вход в рабочее место — как обычно, по ссылке из бота.</p>
    </section>
  );
}

export default async function CabinetPage({
  searchParams,
}: {
  searchParams: Promise<{ login?: string }>;
}) {
  const [session, { login }] = await Promise.all([readClientSession(), searchParams]);

  if (!session) {
    const yandexEnabled = Boolean(
      (process.env.YANDEX_OAUTH_CLIENT_ID || "").trim() && (process.env.YANDEX_OAUTH_CLIENT_SECRET || "").trim(),
    );
    return (
      <CabinetLogin
        mode={telegramLoginMode()}
        botUsername={LEAD_BOT_USERNAME}
        reason={login}
        yandexEnabled={yandexEnabled}
      />
    );
  }

  const accountId = session.accountId ?? session.otherAccount?.accountId ?? null;
  const account = accountId ? await fetchClientAccount(accountId) : null;
  if (isStaffTelegramId(session.telegramUserId) || isStaffTelegramId(account?.telegram_user_id)) {
    return <AdminCabinet email={account?.email ?? null} />;
  }

  return (
    <>
      <LinkHint session={session} account={account} />
      <CabinetHome />
    </>
  );
}
