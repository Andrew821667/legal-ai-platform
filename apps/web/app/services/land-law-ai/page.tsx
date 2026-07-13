import type { Metadata } from "next";

import ServiceDetailPage from "@/components/ServiceDetailPage";
import { createPageMetadata } from "@/lib/seo";
import { serviceDetails } from "@/lib/serviceDetailData";

const service = serviceDetails["land-law-ai"];

export const metadata: Metadata = createPageMetadata({
  title: service.seoTitle,
  description: service.description,
  path: `/services/${service.slug}`,
});

export default function LandLawAIPage() {
  return <ServiceDetailPage service={service} />;
}
