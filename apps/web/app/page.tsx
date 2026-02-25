import type { Metadata } from "next";
import Hero from "@/components/Hero";
import Features from "@/components/Features";
import ComparisonTable from "@/components/ComparisonTable";
import ROICalculator from "@/components/ROICalculator";
import Services from "@/components/Services";
import ProcessTimeline from "@/components/ProcessTimeline";
import Testimonials from "@/components/Testimonials";
import LeadMagnets from "@/components/LeadMagnets";
import FAQ from "@/components/FAQ";
import TrustSignals from "@/components/TrustSignals";
import FloatingCTAWrapper from "@/components/FloatingCTAWrapper";
import AdminPanel from "@/components/AdminPanel";
import FAQStructuredData from "@/components/FAQStructuredData";

export const metadata: Metadata = {
  title: "Автоматизация юридической работы",
  description:
    "AI-решения для юридических команд: договоры, судебная работа, комплаенс и ROI-калькулятор для оценки эффекта.",
  alternates: {
    canonical: "/",
  },
};

export default function Home() {
  const siteUrl = process.env.NEXT_PUBLIC_SITE_URL || "https://legalaipro.ru";

  return (
    <main>
      <FAQStructuredData siteUrl={siteUrl} />
      <Hero />
      <Features />
      <Services />
      <ComparisonTable />
      <ROICalculator />
      <ProcessTimeline />
      <Testimonials />
      <LeadMagnets />
      <FAQ />
      <TrustSignals />
      <FloatingCTAWrapper />
      <AdminPanel password={process.env.NEXT_PUBLIC_ADMIN_PASSWORD || "admin123"} />
    </main>
  );
}
