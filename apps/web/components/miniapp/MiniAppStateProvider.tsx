"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

export type MiniAppAudience = "lawyer" | "business" | "mixed";

export type MiniAppState = {
  onboardingDone: boolean;
  audience: MiniAppAudience;
  interests: string[];
  goal: string;
  lastAction: string;
  updatedAt: string;
};

type MiniAppStateContextValue = {
  state: MiniAppState;
  ready: boolean;
  updateState: (patch: Partial<MiniAppState>) => void;
  recordAction: (action: string) => void;
  resetState: () => void;
};

const STORAGE_KEY = "legal_ai_miniapp_state_v1";

const DEFAULT_STATE: MiniAppState = {
  onboardingDone: false,
  audience: "mixed",
  interests: [],
  goal: "",
  lastAction: "",
  updatedAt: "",
};

const MiniAppStateContext = createContext<MiniAppStateContextValue | undefined>(undefined);

function sanitizeState(raw: unknown): MiniAppState {
  if (!raw || typeof raw !== "object") {
    return DEFAULT_STATE;
  }

  const value = raw as Partial<MiniAppState>;
  const audience: MiniAppAudience =
    value.audience === "lawyer" || value.audience === "business" || value.audience === "mixed"
      ? value.audience
      : DEFAULT_STATE.audience;

  return {
    onboardingDone: Boolean(value.onboardingDone),
    audience,
    interests: Array.isArray(value.interests)
      ? value.interests.filter((item): item is string => typeof item === "string")
      : [],
    goal: typeof value.goal === "string" ? value.goal : "",
    lastAction: typeof value.lastAction === "string" ? value.lastAction : "",
    updatedAt: typeof value.updatedAt === "string" ? value.updatedAt : "",
  };
}

export default function MiniAppStateProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<MiniAppState>(DEFAULT_STATE);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw) as unknown;
        setState(sanitizeState(parsed));
      }
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
  }, [state, ready]);

  const updateState = useCallback((patch: Partial<MiniAppState>) => {
    setState((prev) => ({
      ...prev,
      ...patch,
      updatedAt: new Date().toISOString(),
    }));
  }, []);

  const recordAction = useCallback((action: string) => {
    setState((prev) => ({
      ...prev,
      lastAction: action,
      updatedAt: new Date().toISOString(),
    }));
  }, []);

  const resetState = useCallback(() => {
    setState(DEFAULT_STATE);
  }, []);

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
