import CabinetHome from "@/components/cabinet/CabinetHome";
import CabinetLogin from "@/components/cabinet/CabinetLogin";
import { LEAD_BOT_USERNAME } from "@/lib/links";
import { readClientSession } from "@/lib/client-session-server";
import { telegramLoginMode } from "@/lib/telegram-login-mode";

export const dynamic = "force-dynamic";

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

  return <CabinetHome />;
}
