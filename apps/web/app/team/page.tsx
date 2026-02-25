import type { Metadata } from "next";
import AboutTeam from "@/components/AboutTeam";

export const metadata: Metadata = {
  title: "О команде",
  description:
    "Команда Legal AI PRO: юристы-разработчики с практическим опытом и экспертизой в автоматизации юридической работы.",
  alternates: {
    canonical: "/team",
  },
  openGraph: {
    title: "О команде | Legal AI PRO",
    description:
      "Юристы-разработчики, которые внедряют AI-решения для юридических команд.",
    url: "/team",
    type: "profile",
  },
  twitter: {
    card: "summary",
    title: "О команде | Legal AI PRO",
    description:
      "Юристы-разработчики, которые внедряют AI-решения для юридических команд.",
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
