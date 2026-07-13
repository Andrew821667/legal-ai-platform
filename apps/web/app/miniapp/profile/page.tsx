import type { Metadata } from "next";

import MiniAppProfileClient from "@/components/miniapp/pages/MiniAppProfileClient";

export const metadata: Metadata = {
  title: "Профиль Mini App | AI Verdict",
  description: "Профиль Mini App AI Verdict для персонализации контента, интересов и маршрутов внедрения.",
  alternates: {
    canonical: "/miniapp/profile",
  },
  robots: {
    index: false,
    follow: true,
    nocache: true,
  },
};

export default function MiniAppProfilePage() {
  return <MiniAppProfileClient />;
}
