import { ImageResponse } from "next/og";

import OgCard from "@/components/OgCard";

export const runtime = "edge";
export const alt = "Автоматизация юридических процессов AI Verdict";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function Image() {
  return new ImageResponse(
    <OgCard
      eyebrow="Ключевое пересечение практик"
      title="Автоматизация юридических процессов"
      description="Договоры, legal intake, комплаенс, контроль сроков, AI и интеграции с системами компании"
      variant="automation"
    />,
    size,
  );
}
