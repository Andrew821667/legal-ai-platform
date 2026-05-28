import type { Metadata } from "next";

import MiniAppLeadClient from "@/components/miniapp/pages/MiniAppLeadClient";

export const metadata: Metadata = {
  title: "Заявка Mini App | AI Verdict",
  description: "Форма заявки Mini App AI Verdict для связи по пилоту или проверке договорного сценария.",
  alternates: {
    canonical: "/miniapp/lead",
  },
  robots: {
    index: false,
    follow: true,
    nocache: true,
  },
};

export default function MiniAppLeadPage() {
  return <MiniAppLeadClient />;
}
