"use client";

import Link from "next/link";
import type { ReactNode } from "react";

import { trackServiceRouteClick, type ServiceRoute } from "@/lib/lead-attribution";

type Props = {
  href: string;
  route: ServiceRoute;
  className?: string;
  children: ReactNode;
};

export default function TrackedServiceLink({ href, route, className, children }: Props) {
  return (
    <Link href={href} className={className} onClick={() => trackServiceRouteClick(route, href)}>
      {children}
    </Link>
  );
}
