"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import {
  MINIAPP_EVENT_SOURCES,
  MINIAPP_EVENT_TYPES,
  type MiniAppEventSource,
  type MiniAppEventType,
  type MiniAppScreen,
} from "@/lib/reader-events";

export type MiniAppAudience = "lawyer" | "business" | "mixed";

export type MiniAppState = {
  telegramUserId: number | null;
  onboardingDone: boolean;
  audience: MiniAppAudience;
  interests: string[];
  goal: string;
  lastAction: string;
  updatedAt: string;
  savedCount: number;
  recentEvents24h: number;
  leadIntents30d: number;
  recommendedSection: string;
  recommendedScreen: string;
  recommendedReason: string;
};

export type MiniAppActionMeta = {
  eventType?: MiniAppEventType | string;
  source?: MiniAppEventSource | string;
  screen?: MiniAppScreen | string;
  payload?: Record<string, unknown>;
};

type MiniAppStateContextValue = {
  state: MiniAppState;
  ready: boolean;
  updateState: (patch: Partial<MiniAppState>) => void;
  recordAction: (action: string, meta?: MiniAppActionMeta) => void;
  resetState: () => void;
};

const STORAGE_KEY = "legal_ai_miniapp_state_v1";
const STORAGE_TG_KEY = "legal_ai_miniapp_tg_v1";
const CORE_SYNC_TIMEOUT_MS = 4000;
const CONTINUE_STATE_TIMEOUT_MS = 5000;
const PROFILE_SYNC_DEBOUNCE_MS = 800;
const EVENT_DEDUP_WINDOW_MS = 1500;

const DEFAULT_STATE: MiniAppState = {
  telegramUserId: null,
  onboardingDone: false,
  audience: "mixed",
  interests: [],
  goal: "",
  lastAction: "",
  updatedAt: "",
  savedCount: 0,
  recentEvents24h: 0,
  leadIntents30d: 0,
  recommendedSection: "discover",
  recommendedScreen: "content",
  recommendedReason: "",
};

const MiniAppStateContext = createContext<MiniAppStateContextValue | undefined>(undefined);

function toAudience(value: unknown): MiniAppAudience {
  if (value === "lawyer" || value === "business" || value === "mixed") {
    return value;
  }
  return "mixed";
}

function sanitizeState(raw: unknown): MiniAppState {
  if (!raw || typeof raw !== "object") {
    return DEFAULT_STATE;
  }

  const value = raw as Partial<MiniAppState>;
  const telegramUserId = Number(value.telegramUserId);

  return {
    telegramUserId: Number.isFinite(telegramUserId) && telegramUserId > 0 ? telegramUserId : null,
    onboardingDone: Boolean(value.onboardingDone),
    audience: toAudience(value.audience),
    interests: Array.isArray(value.interests)
      ? value.interests.filter((item): item is string => typeof item === "string")
      : [],
    goal: typeof value.goal === "string" ? value.goal : "",
    lastAction: typeof value.lastAction === "string" ? value.lastAction : "",
    updatedAt: typeof value.updatedAt === "string" ? value.updatedAt : "",
    savedCount: Number.isFinite(Number(value.savedCount)) ? Math.max(0, Number(value.savedCount)) : 0,
    recentEvents24h: Number.isFinite(Number(value.recentEvents24h)) ? Math.max(0, Number(value.recentEvents24h)) : 0,
    leadIntents30d: Number.isFinite(Number(value.leadIntents30d)) ? Math.max(0, Number(value.leadIntents30d)) : 0,
    recommendedSection: typeof value.recommendedSection === "string" ? value.recommendedSection : "discover",
    recommendedScreen: typeof value.recommendedScreen === "string" ? value.recommendedScreen : "content",
    recommendedReason: typeof value.recommendedReason === "string" ? value.recommendedReason : "",
  };
}

function resolveTelegramUserIdFromRuntime(): number | null {
  if (typeof window === "undefined") {
    return null;
  }

  const params = new URLSearchParams(window.location.search);
  const fromQuery = Number(params.get("tg") || params.get("telegram_user_id") || "");
  if (Number.isFinite(fromQuery) && fromQuery > 0) {
    return fromQuery;
  }

  const fromStorage = Number(localStorage.getItem(STORAGE_TG_KEY) || "");
  if (Number.isFinite(fromStorage) && fromStorage > 0) {
    return fromStorage;
  }

  const tgUserId = Number((window as any)?.Telegram?.WebApp?.initDataUnsafe?.user?.id || "");
  if (Number.isFinite(tgUserId) && tgUserId > 0) {
    return tgUserId;
  }

  return null;
}

function mapStateFromServer(payload: any, prev: MiniAppState): MiniAppState {
  const updatedAt = typeof payload?.updated_at === "string" ? payload.updated_at : prev.updatedAt;
  const interests = Array.isArray(payload?.interests)
    ? payload.interests.filter((item: unknown): item is string => typeof item === "string")
    : prev.interests;

  return {
    ...prev,
    onboardingDone: Boolean(payload?.onboarding_done),
    audience: toAudience(payload?.audience),
    interests,
    goal: typeof payload?.goal === "string" ? payload.goal : "",
    lastAction: typeof payload?.last_action === "string" ? payload.last_action : prev.lastAction,
    updatedAt,
    savedCount: Number.isFinite(Number(payload?.saved_count)) ? Math.max(0, Number(payload.saved_count)) : prev.savedCount,
    recentEvents24h: Number.isFinite(Number(payload?.recent_events_24h))
      ? Math.max(0, Number(payload.recent_events_24h))
      : prev.recentEvents24h,
    leadIntents30d: Number.isFinite(Number(payload?.lead_intents_30d))
      ? Math.max(0, Number(payload.lead_intents_30d))
      : prev.leadIntents30d,
    recommendedSection:
      typeof payload?.recommended_section === "string" ? payload.recommended_section : prev.recommendedSection,
    recommendedScreen:
      typeof payload?.recommended_screen === "string" ? payload.recommended_screen : prev.recommendedScreen,
    recommendedReason:
      typeof payload?.recommended_reason === "string" ? payload.recommended_reason : prev.recommendedReason,
  };
}

async function fetchWithTimeout(
  input: RequestInfo | URL,
  init: RequestInit = {},
  timeoutMs: number = CORE_SYNC_TIMEOUT_MS,
): Promise<Response> {
  const controller = new AbortController();
  const upstreamSignal = init.signal;
  const onAbort = () => controller.abort();
  if (upstreamSignal) {
    upstreamSignal.addEventListener("abort", onAbort, { once: true });
  }
  const timeoutId = setTimeout(() => controller.abort(), Math.max(500, timeoutMs));

  try {
    return await fetch(input, {
      ...init,
      signal: controller.signal,
    });
  } finally {
    clearTimeout(timeoutId);
    if (upstreamSignal) {
      upstreamSignal.removeEventListener("abort", onAbort);
    }
  }
}

export default function MiniAppStateProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<MiniAppState>(DEFAULT_STATE);
  const [ready, setReady] = useState(false);
  const loadedRemoteForUserRef = useRef<number | null>(null);
  const profileSyncTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pendingProfileRef = useRef<MiniAppState | null>(null);
  const lastProfileSignatureRef = useRef<string>("");
  const lastEventSignatureRef = useRef<string>("");
  const lastEventAtRef = useRef<number>(0);

  const syncProfileToCoreNow = useCallback(async (nextState: MiniAppState) => {
    if (!nextState.telegramUserId) {
      return;
    }

    const payload = {
      telegram_user_id: nextState.telegramUserId,
      onboarding_done: nextState.onboardingDone,
      audience: nextState.audience,
      interests: nextState.interests,
      goal: nextState.goal,
      last_action: nextState.lastAction,
      sync_reader_topics: true,
    };
    const signature = JSON.stringify(payload);
    if (signature === lastProfileSignatureRef.current) {
      return;
    }

    try {
      const response = await fetchWithTimeout(
        "/api/reader/miniapp/profile",
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        },
        CORE_SYNC_TIMEOUT_MS,
      );
      if (!response.ok) {
        return;
      }
      lastProfileSignatureRef.current = signature;
    } catch {
      // Silent fallback to local state if core API is unavailable.
    }
  }, []);

  const scheduleProfileSync = useCallback(
    (nextState: MiniAppState, immediate: boolean = false) => {
      if (!nextState.telegramUserId) {
        return;
      }

      pendingProfileRef.current = nextState;
      if (profileSyncTimerRef.current) {
        clearTimeout(profileSyncTimerRef.current);
        profileSyncTimerRef.current = null;
      }

      const flush = () => {
        profileSyncTimerRef.current = null;
        const pending = pendingProfileRef.current;
        pendingProfileRef.current = null;
        if (pending) {
          void syncProfileToCoreNow(pending);
        }
      };

      if (immediate) {
        flush();
        return;
      }

      profileSyncTimerRef.current = setTimeout(flush, PROFILE_SYNC_DEBOUNCE_MS);
    },
    [syncProfileToCoreNow],
  );

  const pushEventToCore = useCallback(
    async (telegramUserId: number, action: string, meta?: MiniAppActionMeta) => {
      const eventType = String(meta?.eventType || MINIAPP_EVENT_TYPES.action).slice(0, 100);
      const source = String(meta?.source || MINIAPP_EVENT_SOURCES.app);
      const screen = meta?.screen || null;
      const payload = meta?.payload || {};
      const signature = JSON.stringify([telegramUserId, action, eventType, source, screen, payload]);
      const now = Date.now();
      if (
        signature === lastEventSignatureRef.current &&
        now - lastEventAtRef.current <= EVENT_DEDUP_WINDOW_MS
      ) {
        return;
      }
      lastEventSignatureRef.current = signature;
      lastEventAtRef.current = now;

      try {
        await fetchWithTimeout(
          "/api/reader/miniapp/event",
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              telegram_user_id: telegramUserId,
              event_type: eventType,
              source,
              screen,
              action,
              payload,
              update_last_action: true,
            }),
          },
          CORE_SYNC_TIMEOUT_MS,
        );
      } catch {
        // Keep UX non-blocking.
      }
    },
    [],
  );

  useEffect(() => {
    return () => {
      if (profileSyncTimerRef.current) {
        clearTimeout(profileSyncTimerRef.current);
        profileSyncTimerRef.current = null;
      }
      const pending = pendingProfileRef.current;
      pendingProfileRef.current = null;
      if (pending) {
        void syncProfileToCoreNow(pending);
      }
    };
  }, [syncProfileToCoreNow]);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      const localState = raw ? sanitizeState(JSON.parse(raw) as unknown) : DEFAULT_STATE;
      const runtimeTelegramUserId = resolveTelegramUserIdFromRuntime();
      const merged = {
        ...localState,
        telegramUserId: runtimeTelegramUserId ?? localState.telegramUserId,
      };

      if (merged.telegramUserId) {
        localStorage.setItem(STORAGE_TG_KEY, String(merged.telegramUserId));
      }

      setState(merged);
    } catch {
      setState(DEFAULT_STATE);
    } finally {
      setReady(true);
    }
  }, []);

  useEffect(() => {
    if (!ready) {
      return;
    }

    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    if (state.telegramUserId) {
      localStorage.setItem(STORAGE_TG_KEY, String(state.telegramUserId));
    }
  }, [state, ready]);

  useEffect(() => {
    if (!ready || !state.telegramUserId) {
      return;
    }
    if (loadedRemoteForUserRef.current === state.telegramUserId) {
      return;
    }

    loadedRemoteForUserRef.current = state.telegramUserId;

    void (async () => {
      try {
        const response = await fetchWithTimeout(
          `/api/reader/continue-state?telegram_user_id=${encodeURIComponent(String(state.telegramUserId))}`,
          { cache: "no-store" },
          CONTINUE_STATE_TIMEOUT_MS,
        );
        if (!response.ok) {
          return;
        }
        const payload = await response.json();
        setState((prev) => mapStateFromServer(payload, prev));
      } catch {
        // Keep local fallback when backend is unavailable.
      }
    })();
  }, [ready, state.telegramUserId]);

  const updateState = useCallback(
    (patch: Partial<MiniAppState>) => {
      setState((prev) => {
        const next: MiniAppState = {
          ...prev,
          ...patch,
          updatedAt: new Date().toISOString(),
        };
        if (next.telegramUserId) {
          scheduleProfileSync(next);
        }
        return next;
      });
    },
    [scheduleProfileSync],
  );

  const recordAction = useCallback(
    (action: string, meta?: MiniAppActionMeta) => {
      setState((prev) => {
        const next: MiniAppState = {
          ...prev,
          lastAction: action,
          updatedAt: new Date().toISOString(),
        };
        if (next.telegramUserId) {
          void pushEventToCore(next.telegramUserId, action, meta);
        }
        return next;
      });
    },
    [pushEventToCore],
  );

  const resetState = useCallback(() => {
    setState((prev) => {
      const next: MiniAppState = {
        ...DEFAULT_STATE,
        telegramUserId: prev.telegramUserId,
        updatedAt: new Date().toISOString(),
      };
      if (next.telegramUserId) {
        scheduleProfileSync(next, true);
      }
      return next;
    });
  }, [scheduleProfileSync]);

  const contextValue = useMemo<MiniAppStateContextValue>(
    () => ({
      state,
      ready,
      updateState,
      recordAction,
      resetState,
    }),
    [ready, recordAction, resetState, state, updateState],
  );

  return <MiniAppStateContext.Provider value={contextValue}>{children}</MiniAppStateContext.Provider>;
}

export function useMiniAppState() {
  const context = useContext(MiniAppStateContext);

  if (!context) {
    throw new Error("useMiniAppState must be used within MiniAppStateProvider");
  }

  return context;
}
