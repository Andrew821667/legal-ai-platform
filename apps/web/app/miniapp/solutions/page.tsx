import type { Metadata } from "next";

import MiniAppSolutionsClient from "@/components/miniapp/pages/MiniAppSolutionsClient";

export const metadata: Metadata = {
  title: "Решения Mini App | AI Verdict",
  description: "Маршруты внедрения AI Verdict для юристов, бизнеса и договорной работы.",
  alternates: {
    canonical: "/miniapp/solutions",
  },
};

export default function MiniAppSolutionsPage() {
  return <MiniAppSolutionsClient />;
}
