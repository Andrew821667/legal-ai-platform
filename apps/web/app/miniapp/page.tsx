import type { Metadata } from "next";

import MiniAppHomeClient from "@/components/miniapp/pages/MiniAppHomeClient";

export const metadata: Metadata = {
  title: "Mini App",
  description: "Mini App AI Verdict: контент, инструменты, решения и персональный маршрут внедрения AI в юридическую функцию.",
  alternates: {
    canonical: "/miniapp",
  },
};

export default function MiniAppPage() {
  return <MiniAppHomeClient />;
}
