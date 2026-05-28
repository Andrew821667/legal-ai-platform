import type { Metadata } from "next";

import MiniAppToolsClient from "@/components/miniapp/pages/MiniAppToolsClient";

export const metadata: Metadata = {
  title: "Инструменты Mini App | AI Verdict",
  description: "Практические инструменты AI Verdict: проверка договора, история анализов и сценарии внедрения.",
  alternates: {
    canonical: "/miniapp/tools",
  },
};

export default function MiniAppToolsPage() {
  return <MiniAppToolsClient />;
}
