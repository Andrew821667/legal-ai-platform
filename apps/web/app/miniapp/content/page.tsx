import type { Metadata } from "next";

import MiniAppContentClient from "@/components/miniapp/pages/MiniAppContentClient";

export const metadata: Metadata = {
  title: "Контент Mini App | AI Verdict",
  description: "Подборка материалов AI Verdict для юристов, бизнеса и legal ops внутри Mini App.",
  alternates: {
    canonical: "/miniapp/content",
  },
};

export default function MiniAppContentPage() {
  return <MiniAppContentClient />;
}
