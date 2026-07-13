import type { Metadata } from "next";

import ServiceDetailPage from "@/components/ServiceDetailPage";
import { createPageMetadata } from "@/lib/seo";
import { serviceDetails } from "@/lib/serviceDetailData";

const service = serviceDetails["corporate-ma-ai"];

export const metadata: Metadata = createPageMetadata({
  title: service.seoTitle,
  description: service.description,
  path: `/services/${service.slug}`,
});

export default function CorporateMAPage() {
  return <ServiceDetailPage service={service} />;
}
