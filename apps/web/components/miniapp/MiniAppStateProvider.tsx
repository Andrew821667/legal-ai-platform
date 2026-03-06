"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";

export type MiniAppAudience = "lawyer" | "business" | "mixed";

export type MiniAppState = {
  telegramUserId: number | null;
  onboardingDone: boolean;
  audience: MiniAppAudience;
  interests: string[];
  goal: string;
  lastAction: string;
  updatedAt: string;
};

export type MiniAppActionMeta = {
  eventType?: string;
  source?: string;
  screen?: string;
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

const DEFAULT_STATE: MiniAppState = {
  telegramUserId: null,
  onboardingDone: false,
  audience: "mixed",
  interests: [],
  goal: "",
  lastAction: "",
  updatedAt: "",
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

function mapProfileFromServer(payload: any, prev: MiniAppState): MiniAppState {
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
  };
}

export default function MiniAppStateProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<MiniAppState>(DEFAULT_STATE);
  const [ready, setReady] = useState(false);
  const loadedRemoteForUserRef = useRef<number | null>(null);

  const pushProfileToCore = useCallback(async (nextState: MiniAppState) => {
    if (!nextState.telegramUserId) {
      return;
    }

    try {
      await fetch("/api/reader/miniapp/profile", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          telegram_user_id: nextState.telegramUserId,
          onboarding_done: nextState.onboardingDone,
          audience: nextState.audience,
          interests: nextState.interests,
          goal: nextState.goal,
          last_action: nextState.lastAction,
          sync_reader_topics: true,
        }),
      });
    } catch {
      // Silent fallback to local state if core API is unavailable.
    }
  }, []);

  const pushEventToCore = useCallback(
    async (telegramUserId: number, action: string, meta?: MiniAppActionMeta) => {
      try {
        await fetch("/api/reader/miniapp/event", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            telegram_user_id: telegramUserId,
            event_type: (meta?.eventType || "action").slice(0, 100),
            source: meta?.source || "miniapp",
            screen: meta?.screen || null,
            action,
            payload: meta?.payload || {},
            update_last_action: true,
          }),
        });
      } catch {
        // Keep UX non-blocking.
      }
    },
    [],
  );

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
        const response = await fetch(
          `/api/reader/miniapp/profile?telegram_user_id=${encodeURIComponent(String(state.telegramUserId))}`,
          { cache: "no-store" },
        );
        if (!response.ok) {
          return;
        }
        const payload = await response.json();
        setState((prev) => mapProfileFromServer(payload, prev));
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
          void pushProfileToCore(next);
        }
        return next;
      });
    },
    [pushProfileToCore],
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
        void pushProfileToCore(next);
      }
      return next;
    });
  }, [pushProfileToCore]);

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
