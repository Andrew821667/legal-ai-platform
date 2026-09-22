import type { Metadata } from "next";

import ServiceDetailPage from "@/components/ServiceDetailPage";
import { ROUTES } from "@/lib/links";
import { createPageMetadata } from "@/lib/seo";
import { serviceDetails } from "@/lib/serviceDetailData";

const service = serviceDetails["automation-diagnostic"];

export const metadata: Metadata = createPageMetadata({
  title: service.seoTitle,
  description: service.description,
  path: ROUTES.automationDiagnostic,
  socialImage: "/engineering/opengraph-image",
  keywords: [
    "диагностика автоматизации",
    "аудит бизнес процессов",
    "автоматизация бизнес процессов",
    "интеграция CRM и 1С",
    "интеграция информационных систем",
    "техническое задание на автоматизацию",
    "консультация по автоматизации бизнеса",
    "внедрение AI в бизнес процессы",
  ],
});

export default function AutomationDiagnosticPage() {
  return <ServiceDetailPage service={service} path={ROUTES.automationDiagnostic} />;
}
