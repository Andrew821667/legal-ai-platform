"use client";

import Link from "next/link";
import { MiniAppActionMeta, useMiniAppState } from "@/components/miniapp/MiniAppStateProvider";

type MiniTrackedLinkProps = {
  href: string;
  action: string;
  className?: string;
  children: React.ReactNode;
  target?: string;
  rel?: string;
  meta?: MiniAppActionMeta;
  variant?: "primary" | "secondary" | "info";
};

const variantClasses: Record<NonNullable<MiniTrackedLinkProps["variant"]>, string> = {
  primary:
    "miniapp-action-primary inline-flex min-h-11 w-full items-center justify-center rounded-lg bg-amber-400 px-4 py-2.5 text-center text-sm font-semibold text-slate-950 shadow-[0_8px_20px_rgba(251,191,36,0.22)] ring-1 ring-amber-200/60 transition-colors hover:bg-amber-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-200",
  secondary:
    "miniapp-action-secondary inline-flex min-h-11 w-full items-center justify-center rounded-lg border border-amber-300/70 bg-slate-950 px-4 py-2.5 text-center text-sm font-semibold text-amber-100 shadow-[0_8px_18px_rgba(0,0,0,0.28)] transition-colors hover:border-amber-200 hover:bg-slate-900 hover:text-amber-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-300",
  info:
    "miniapp-action-info inline-flex min-h-11 w-full items-center justify-center rounded-lg bg-sky-400 px-4 py-2.5 text-center text-sm font-semibold text-slate-950 shadow-[0_8px_20px_rgba(56,189,248,0.22)] ring-1 ring-sky-200/70 transition-colors hover:bg-sky-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-200",
};

export default function MiniTrackedLink({
  href,
  action,
  className,
  children,
  target,
  rel,
  meta,
  variant,
}: MiniTrackedLinkProps) {
  const { recordAction } = useMiniAppState();
  const isExternal = /^https?:\/\//i.test(href);
  const resolvedClassName = [variant ? variantClasses[variant] : "", className].filter(Boolean).join(" ");

  if (isExternal) {
    return (
      <a href={href} className={resolvedClassName} target={target} rel={rel} onClick={() => recordAction(action, meta)}>
        {children}
      </a>
    );
  }

  return (
    <Link href={href} className={resolvedClassName} target={target} rel={rel} onClick={() => recordAction(action, meta)}>
      {children}
    </Link>
  );
}
