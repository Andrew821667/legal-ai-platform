import type { Metadata } from "next";

import MiniAppEngineeringHelpClient from "@/components/miniapp/pages/MiniAppEngineeringHelpClient";

export const metadata: Metadata = {
  title: "Инженерная практика Mini App | AI Verdict",
  description: "Передача инженерной задачи или автоматизации юридической функции команде через Mini App AI Verdict.",
  robots: { index: false, follow: true, nocache: true },
};

export default function MiniAppEngineeringHelpPage() {
  return <MiniAppEngineeringHelpClient />;
}
