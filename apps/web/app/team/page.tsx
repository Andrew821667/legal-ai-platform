import type { Metadata } from "next";
import AboutTeam from "@/components/AboutTeam";

export const metadata: Metadata = {
  title: "О команде",
  description:
    "Как команда Legal AI PRO подходит к автоматизации юридической функции: процессы, данные, контроль и внедрение.",
  alternates: {
    canonical: "/team",
  },
  openGraph: {
    title: "О команде | Legal AI PRO",
    description:
      "Подход команды Legal AI PRO к внедрению AI в юридические процессы.",
    url: "/team",
    type: "profile",
  },
  twitter: {
    card: "summary",
    title: "О команде | Legal AI PRO",
    description:
      "Подход команды Legal AI PRO к внедрению AI в юридические процессы.",
  },
  robots: {
    index: true,
    follow: true,
  },
};

export default function TeamPage() {
  return (
    <main className="min-h-screen bg-slate-900">
      <AboutTeam />
    </main>
  );
}
