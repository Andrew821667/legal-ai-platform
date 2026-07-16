import type { Metadata } from "next";

import MiniAppLegalHelpClient from "@/components/miniapp/pages/MiniAppLegalHelpClient";

export const metadata: Metadata = {
  title: "Юридическая помощь Mini App | AI Verdict",
  description: "Передача юридической задачи человеку через Mini App AI Verdict.",
  robots: { index: false, follow: true, nocache: true },
};

export default function MiniAppLegalHelpPage() {
  return <MiniAppLegalHelpClient />;
}
