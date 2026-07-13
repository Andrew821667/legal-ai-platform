import type { Metadata } from "next";
import AboutTeam from "@/components/AboutTeam";
import { createPageMetadata } from "@/lib/seo";

export const metadata: Metadata = createPageMetadata({
  title: "О команде",
  description:
    "Основатель AI Verdict, ответственность за продукт и материалы, а также подход к автоматизации юридической функции.",
  path: "/team",
  type: "profile",
});

export default function TeamPage() {
  return (
    <main className="min-h-screen bg-slate-800">
      <AboutTeam />
    </main>
  );
}
