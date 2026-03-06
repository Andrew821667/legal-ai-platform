"use client";

import { useEffect, useRef } from "react";
import { usePathname, useSearchParams } from "next/navigation";
import { useMiniAppState } from "@/components/miniapp/MiniAppStateProvider";
import {
  MINIAPP_EVENT_SOURCES,
  MINIAPP_EVENT_TYPES,
  defaultActionForScreen,
  resolveMiniAppScreen,
} from "@/lib/reader-events";

export default function MiniAppDeepLinkSync() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const { ready, recordAction, updateState } = useMiniAppState();
  const handledRef = useRef<string>("");

  useEffect(() => {
    if (!ready) {
      return;
    }

    const rawParams = searchParams.toString();
    if (!rawParams) {
      return;
    }

    const key = `${pathname}?${rawParams}`;
    if (handledRef.current === key) {
      return;
    }
    handledRef.current = key;

    const screen = resolveMiniAppScreen((searchParams.get("screen") || "").trim() || pathname);
    const source = (searchParams.get("src") || "").trim() || MINIAPP_EVENT_SOURCES.deeplink;
    const action = (searchParams.get("act") || "").trim() || defaultActionForScreen(screen);
    const postId = (searchParams.get("post_id") || "").trim() || null;

    recordAction(action, {
      eventType: MINIAPP_EVENT_TYPES.deeplinkOpen,
      source,
      screen,
      payload: postId ? { post_id: postId } : {},
    });
    updateState({ lastAction: action });
  }, [pathname, ready, recordAction, searchParams, updateState]);

  return null;
}
