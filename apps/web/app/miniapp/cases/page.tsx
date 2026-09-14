import type { Metadata } from "next";

import ClientCases from "@/components/miniapp/pages/ClientCases";

export const metadata: Metadata = {
  title: "Мои дела",
  robots: { index: false, follow: false, nocache: true },
};

export default function ClientCasesPage() {
  return <ClientCases />;
}
