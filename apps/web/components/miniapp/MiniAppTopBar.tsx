"use client";

import { ROUTES } from "@/lib/links";
import MiniTrackedLink from "@/components/miniapp/MiniTrackedLink";
import { useMiniAppState } from "@/components/miniapp/MiniAppStateProvider";
import { MINIAPP_ACTIONS, MINIAPP_EVENT_SOURCES, MINIAPP_EVENT_TYPES, MINIAPP_SCREENS } from "@/lib/reader-events";

const AUDIENCE_LABELS = {
  lawyer: "Юрист",
  business: "Бизнес",
  mixed: "Смешанный контур",
} as const;

export default function MiniAppTopBar() {
  const { state, ready } = useMiniAppState();

  if (!ready) {
    return (
      <article className="mb-4 rounded-xl border border-slate-800 bg-slate-900/70 p-4">
        <p className="text-sm text-slate-400">Загрузка персонального контура...</p>
      </article>
    );
  }

  if (!state.onboardingDone) {
    return (
      <article className="mb-4 rounded-xl border border-amber-500/40 bg-amber-500/10 p-4">
        <h2 className="text-sm font-semibold text-amber-300">Настройте mini-app за 30 секунд</h2>
        <p className="mt-2 text-sm text-slate-200">
          Укажите роль и интересы, чтобы контент и маршруты внедрения подстраивались под ваш текущий контекст.
        </p>
        <MiniTrackedLink
          href={ROUTES.miniAppProfile}
          action={MINIAPP_ACTIONS.openOnboarding}
          meta={{ eventType: MINIAPP_EVENT_TYPES.navClick, source: MINIAPP_EVENT_SOURCES.topbar, screen: MINIAPP_SCREENS.home }}
          className="mt-3 inline-flex rounded-lg bg-amber-500 px-3 py-2 text-xs font-semibold text-slate-950 hover:bg-amber-400 transition-colors"
        >
          Пройти настройку
        </MiniTrackedLink>
      </article>
    );
  }

  return (
    <article className="mb-4 rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-emerald-300">Профиль активен</h2>
          <p className="mt-1 text-xs text-slate-200">
            Роль: {AUDIENCE_LABELS[state.audience]} · Интересы: {state.interests.length || 0}
          </p>
        </div>
        <MiniTrackedLink
          href={ROUTES.miniAppProfile}
          action={MINIAPP_ACTIONS.openProfile}
          meta={{ eventType: MINIAPP_EVENT_TYPES.navClick, source: MINIAPP_EVENT_SOURCES.topbar, screen: MINIAPP_SCREENS.home }}
          className="rounded-lg border border-emerald-400/40 px-3 py-2 text-xs font-semibold text-emerald-200 hover:border-emerald-300 transition-colors"
        >
          Изменить
        </MiniTrackedLink>
      </div>
    </article>
  );
}
