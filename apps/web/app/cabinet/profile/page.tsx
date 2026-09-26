import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { UserRound } from "lucide-react";

import CabinetProfileClient from "@/components/cabinet/CabinetProfileClient";
import { readClientSession } from "@/lib/client-session-server";
import { EXTERNAL_LINKS, ROUTES } from "@/lib/links";

export const metadata: Metadata = {
  title: "Профиль | Личный кабинет",
  robots: { index: false, follow: false, nocache: true },
};
export const dynamic = "force-dynamic";

const METHOD_LABEL: Record<string, string> = {
  oidc: "Telegram Login",
  legacy: "Telegram (виджет)",
  yandex: "Яндекс ID",
};

export default async function CabinetProfilePage() {
  const session = await readClientSession();
  if (!session) {
    redirect("/cabinet?login=required");
  }

  const profile = session.profile;
  const displayName = [profile?.fn, profile?.ln].filter(Boolean).join(" ") || "Клиент AI Verdict";
  const initials = (profile?.fn?.[0] || "?").toUpperCase();

  return (
    <section className="rounded-2xl border border-slate-300 bg-white p-6 shadow-sm sm:p-10">
      <div className="flex items-center gap-4">
        {profile?.photo ? (
          // eslint-disable-next-line @next/next/no-img-element -- внешний URL Telegram, next/image его не оптимизирует без доп. настройки домена
          <img src={profile.photo} alt="" className="h-16 w-16 rounded-full object-cover" />
        ) : (
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-amber-100 text-xl font-semibold text-amber-700">
            {initials}
          </div>
        )}
        <div>
          <h1 className="text-xl font-semibold text-slate-900">{displayName}</h1>
          {profile?.un ? <p className="text-sm text-slate-500">@{profile.un}</p> : null}
          {profile?.email ? <p className="text-sm text-slate-500">{profile.email}</p> : null}
        </div>
      </div>

      <div className="mt-6 space-y-2">
        <CabinetProfileClient phoneMasked={profile?.phoneMasked} />
        <p className="text-sm text-slate-600">
          Способ входа: <span className="font-medium text-slate-900">{METHOD_LABEL[profile?.method || "oidc"]}</span>
        </p>
      </div>

      <div className="mt-6 flex flex-wrap items-center gap-3">
        <Link
          href={ROUTES.cabinet}
          className="inline-flex items-center justify-center rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 transition-colors hover:bg-slate-50"
        >
          <UserRound className="mr-2 h-4 w-4" />
          Мои дела
        </Link>
        <a href={EXTERNAL_LINKS.leadBot} className="text-sm font-semibold text-amber-700 underline">
          Открыть бота-ассистента
        </a>
        <form action="/cabinet/logout" method="post" className="ml-auto">
          <button
            type="submit"
            className="inline-flex items-center justify-center rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 transition-colors hover:bg-slate-50"
          >
            Выйти
          </button>
        </form>
      </div>
    </section>
  );
}
