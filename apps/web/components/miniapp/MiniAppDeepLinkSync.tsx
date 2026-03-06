"use client";

import { useEffect, useRef } from "react";
import { usePathname, useSearchParams } from "next/navigation";
import { useMiniAppState } from "@/components/miniapp/MiniAppStateProvider";

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

    const screen = (searchParams.get("screen") || "").trim() || pathname;
    const source = (searchParams.get("src") || "").trim() || "miniapp";
    const action = (searchParams.get("act") || "").trim() || `miniapp_open_${screen}`;
    const postId = (searchParams.get("post_id") || "").trim() || null;

    recordAction(action, {
      eventType: "deeplink_open",
      source,
      screen,
      payload: postId ? { post_id: postId } : {},
    });
    updateState({ lastAction: action });
  }, [pathname, ready, recordAction, searchParams, updateState]);

  return null;
}
