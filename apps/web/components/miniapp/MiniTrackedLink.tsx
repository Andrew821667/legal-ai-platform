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
};

export default function MiniTrackedLink({
  href,
  action,
  className,
  children,
  target,
  rel,
  meta,
}: MiniTrackedLinkProps) {
  const { recordAction } = useMiniAppState();

  return (
    <Link href={href} className={className} target={target} rel={rel} onClick={() => recordAction(action, meta)}>
      {children}
    </Link>
  );
}
