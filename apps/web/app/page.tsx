import type { Metadata } from "next";
import Hero from "@/components/Hero";
import Features from "@/components/Features";
import ComparisonTable from "@/components/ComparisonTable";
import ROICalculator from "@/components/ROICalculator";
import Services from "@/components/Services";
import ProcessTimeline from "@/components/ProcessTimeline";
import LeadMagnets from "@/components/LeadMagnets";
import LeadCaptureForm from "@/components/LeadCaptureForm";
import FAQ from "@/components/FAQ";
import TrustSignals from "@/components/TrustSignals";
import FloatingCTAWrapper from "@/components/FloatingCTAWrapper";
import FAQStructuredData from "@/components/FAQStructuredData";

export const metadata: Metadata = {
  title: "Автоматизация юридической работы",
  description:
    "AI-сценарии для юридической функции: заявки, договорная работа, комплаенс и типовые процессы.",
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
      <LeadMagnets />
      <LeadCaptureForm />
      <FAQ />
      <TrustSignals />
      <FloatingCTAWrapper />
    </main>
  );
}
