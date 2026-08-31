import type { Metadata } from "next";

import MiniAppContentClient from "@/components/miniapp/pages/MiniAppContentClient";
import { listPublishedAiLawComments } from "@/lib/aiLawEditorialStore";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Контент Mini App | AI Verdict",
  description: "Подборка материалов AI Verdict для юристов, бизнеса и legal ops внутри Mini App.",
  alternates: {
    canonical: "/miniapp/content",
  },
};

export default function MiniAppContentPage() {
  const aiLawItems = listPublishedAiLawComments().map((comment) => ({
    slug: comment.slug,
    title: comment.title,
    effectiveDates: comment.effectiveStages.map((stage) => stage.date),
  }));
  return <MiniAppContentClient aiLawItems={aiLawItems} />;
}
