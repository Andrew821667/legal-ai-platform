"use client";

import { useEffect, useMemo, useState } from "react";
import { leadBotDeepLink } from "@/lib/links";
import MiniAppCtaFlowCard from "@/components/miniapp/MiniAppCtaFlowCard";
import MiniAppGuideCard from "@/components/miniapp/MiniAppGuideCard";
import MiniTrackedLink from "@/components/miniapp/MiniTrackedLink";
import { useMiniAppState, type MiniAppAudience } from "@/components/miniapp/MiniAppStateProvider";
import { MINIAPP_ACTIONS, MINIAPP_EVENT_SOURCES, MINIAPP_EVENT_TYPES, MINIAPP_SCREENS } from "@/lib/reader-events";

const interestOptions = [
  "AI в договорах",
  "AI law",
  "Legal ops",
  "Судебная практика",
  "Общий AI",
];

const audienceLabels: Record<MiniAppAudience, string> = {
  lawyer: "Юрист",
  business: "Бизнес",
  mixed: "Смешанный",
};

export default function MiniAppProfilePage() {
  const { state, ready, updateState, resetState, recordAction } = useMiniAppState();

  const [audience, setAudience] = useState<MiniAppAudience>("mixed");
  const [goal, setGoal] = useState("");
  const [interests, setInterests] = useState<string[]>([]);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (!ready) {
      return;
    }

    setAudience(state.audience);
    setGoal(state.goal);
    setInterests(state.interests);
  }, [ready, state.audience, state.goal, state.interests]);

  const updatedAtLabel = useMemo(() => {
    if (!state.updatedAt) {
      return "нет";
    }

    const date = new Date(state.updatedAt);
    if (Number.isNaN(date.getTime())) {
      return "нет";
    }

    return date.toLocaleString("ru-RU");
  }, [state.updatedAt]);

  const toggleInterest = (value: string) => {
    setSaved(false);
    setInterests((prev) =>
      prev.includes(value) ? prev.filter((item) => item !== value) : [...prev, value],
    );
  };

  const handleSave = () => {
    updateState({
      onboardingDone: true,
      audience,
      interests,
      goal,
    });
    recordAction(MINIAPP_ACTIONS.profileSaved, {
      eventType: MINIAPP_EVENT_TYPES.profileSaved,
      source: MINIAPP_EVENT_SOURCES.profile,
      screen: MINIAPP_SCREENS.profile,
      payload: { audience, interests_count: interests.length },
    });
    setSaved(true);
  };

  const handleReset = () => {
    resetState();
    setAudience("mixed");
    setGoal("");
    setInterests([]);
    setSaved(false);
  };

  return (
    <section className="space-y-4">
      <MiniAppGuideCard
        title="Как использовать экран"
        description="Заполните роль, интересы и цель. После сохранения mini-app начнет показывать более релевантный контент и маршруты внедрения."
      />

      <article className="rounded-xl border border-slate-800 bg-slate-900/70 p-4">
        <h2 className="text-base font-semibold text-white">Профиль</h2>
        <p className="mt-2 text-xs text-slate-400">Последнее обновление: {updatedAtLabel}</p>

        <div className="mt-4 space-y-3">
          <fieldset>
            <legend className="text-sm text-slate-300">Роль</legend>
            <div className="mt-2 grid grid-cols-3 gap-2">
              {(Object.keys(audienceLabels) as MiniAppAudience[]).map((value) => (
                <button
                  key={value}
                  type="button"
                  className={`rounded-lg border px-2 py-2 text-xs transition-colors ${
                    audience === value
                      ? "border-amber-500 bg-amber-500/15 text-amber-300"
                      : "border-slate-700 text-slate-300 hover:border-slate-500"
                  }`}
                  onClick={() => {
                    setAudience(value);
                    setSaved(false);
                  }}
                >
                  {audienceLabels[value]}
                </button>
              ))}
            </div>
          </fieldset>

          <fieldset>
            <legend className="text-sm text-slate-300">Интересы</legend>
            <div className="mt-2 flex flex-wrap gap-2">
              {interestOptions.map((option) => {
                const selected = interests.includes(option);
                return (
                  <button
                    key={option}
                    type="button"
                    onClick={() => toggleInterest(option)}
                    className={`rounded-full border px-3 py-1 text-xs transition-colors ${
                      selected
                        ? "border-amber-500 bg-amber-500/15 text-amber-300"
                        : "border-slate-700 text-slate-300 hover:border-slate-500"
                    }`}
                  >
                    {option}
                  </button>
                );
              })}
            </div>
          </fieldset>

          <label className="block">
            <span className="text-sm text-slate-300">Цель внедрения</span>
            <textarea
              value={goal}
              onChange={(event) => {
                setGoal(event.target.value);
                setSaved(false);
              }}
              rows={3}
              placeholder="Например: сократить срок согласования договоров"
              className="mt-2 w-full rounded-lg border border-slate-700 bg-slate-950/70 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 outline-none focus:border-amber-500"
            />
          </label>
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={handleSave}
            className="rounded-lg bg-amber-500 px-3 py-2 text-sm font-semibold text-slate-950 hover:bg-amber-400 transition-colors"
          >
            Сохранить профиль
          </button>
          <button
            type="button"
            onClick={handleReset}
            className="rounded-lg border border-slate-700 px-3 py-2 text-sm font-semibold text-slate-200 hover:border-slate-500 transition-colors"
          >
            Сбросить и начать заново
          </button>
        </div>

        {saved && (
          <p className="mt-3 text-sm text-emerald-300">Профиль сохранен. Персональные рекомендации обновлены.</p>
        )}
      </article>

      <MiniTrackedLink
        href={leadBotDeepLink("web_miniapp_profile")}
        action={MINIAPP_ACTIONS.openAssistant}
        meta={{
          eventType: MINIAPP_EVENT_TYPES.ctaClick,
          source: MINIAPP_EVENT_SOURCES.profile,
          screen: MINIAPP_SCREENS.profile,
          payload: { cta: "lead_bot" },
        }}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex rounded-lg border border-sky-500/60 px-4 py-2 text-sm font-semibold text-sky-200 hover:border-sky-300 transition-colors"
      >
        Связаться с Ассистентом Legal AI Pro
      </MiniTrackedLink>

      <MiniAppCtaFlowCard
        leadStart="web_miniapp_profile"
        sourceScreen="/miniapp/profile"
        title="Персональный маршрут: Узнать -> Проверить -> Внедрить"
      />
    </section>
  );
}
