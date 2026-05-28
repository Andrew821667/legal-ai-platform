import type { Metadata } from "next";

import MiniAppProfileClient from "@/components/miniapp/pages/MiniAppProfileClient";

export const metadata: Metadata = {
  title: "Профиль Mini App | AI Verdict",
  description: "Профиль Mini App AI Verdict для персонализации контента, интересов и маршрутов внедрения.",
  alternates: {
    canonical: "/miniapp/profile",
  },
};

export default function MiniAppProfilePage() {
  return <MiniAppProfileClient />;
}
