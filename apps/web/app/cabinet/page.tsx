import Link from "next/link";

import CabinetHome from "@/components/cabinet/CabinetHome";
import CabinetLogin from "@/components/cabinet/CabinetLogin";
import { fetchClientAccount } from "@/lib/client-core";
import { LEAD_BOT_USERNAME } from "@/lib/links";
import { readClientSession, type ClientSession } from "@/lib/client-session-server";
import { telegramLoginMode } from "@/lib/telegram-login-mode";

export const dynamic = "force-dynamic";

/**
 * Вошёл через Яндекс ID, а дела — в Telegram: без подсказки клиент увидит
 * пустой кабинет и решит, что всё пропало. Сам блок объединения — в профиле.
 */
async function LinkHint({ session }: { session: ClientSession }) {
  const accountId = session.accountId ?? session.otherAccount?.accountId ?? null;
  if (!accountId) return null;
  const account = await fetchClientAccount(accountId);
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

  return (
    <>
      <LinkHint session={session} />
      <CabinetHome />
    </>
  );
}
