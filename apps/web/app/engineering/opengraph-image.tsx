import { ImageResponse } from "next/og";

import OgCard from "@/components/OgCard";

export const runtime = "edge";
export const alt = "Инженерная практика AI Verdict";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function Image() {
  return new ImageResponse(
    <OgCard
      eyebrow="Инженерная практика"
      title="Разработка программ, AI-сервисов и интеграций"
      description="От диагностики процесса и архитектуры до запуска и сопровождения рабочей системы"
      variant="engineering"
    />,
    size,
  );
}
