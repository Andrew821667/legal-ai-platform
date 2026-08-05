import type { Metadata } from "next";

import MiniAppHomeClient from "@/components/miniapp/pages/MiniAppHomeClient";

export const metadata: Metadata = {
  title: "Mini App",
  description: "Mini App юридической и инженерной практик AI Verdict: автоматизация юридической функции, правовая помощь, разработка и AI.",
  alternates: {
    canonical: "/miniapp",
  },
};

export default function MiniAppPage() {
  return <MiniAppHomeClient />;
}
