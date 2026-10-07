import type { Metadata } from "next";

import ServiceDetailPage from "@/components/ServiceDetailPage";
import { ROUTES } from "@/lib/links";
import { createPageMetadata } from "@/lib/seo";
import { serviceDetails } from "@/lib/serviceDetailData";

const service = serviceDetails.integrations;

export const metadata: Metadata = createPageMetadata({
  title: service.seoTitle,
  description: service.description,
  path: ROUTES.integrations,
  socialImage: "/engineering/opengraph-image",
  keywords: [
    "интеграция CRM с сайтом",
    "интеграция 1С и CRM",
    "разработка интеграции API",
    "автоматизация заявок с сайта",
    "интеграция бизнес систем",
    "разработка интеграций для бизнеса",
  ],
});

export default function IntegrationsPage() {
  return <ServiceDetailPage service={service} path={ROUTES.integrations} />;
}
