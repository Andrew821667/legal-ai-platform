import { ImageResponse } from "next/og";

import OgCard from "@/components/OgCard";

export const runtime = "edge";
export const alt = "Юридическая практика AI Verdict";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function Image() {
  return new ImageResponse(
    <OgCard
      eyebrow="Юридическая практика"
      title="Юридическая помощь бизнесу и частным клиентам"
      description="Дистанционная работа по российскому праву с ответственностью практикующего юриста"
      variant="legal"
    />,
    size,
  );
}
