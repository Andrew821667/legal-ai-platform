import type { Metadata } from "next";

import AdminPanel from "@/components/AdminPanel";

export const metadata: Metadata = {
  title: "System Monitor | AI Verdict",
  robots: {
    index: false,
    follow: false,
    nocache: true,
  },
};

export default function MonitorPage() {
  return <AdminPanel initialOpen initialTab="system" />;
}
