import { ImageResponse } from "next/og";

import OgCard from "@/components/OgCard";

export const runtime = "edge";
export const alt = "AI Verdict — юридическая и инженерная практики";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function Image() {
  return new ImageResponse(
    <OgCard
      eyebrow="Юридическая + инженерная практики"
      title="Автоматизация юридической функции"
      description="Правовая логика, прикладная разработка, AI и интеграции в одном рабочем контуре"
      variant="home"
    />,
    size,
  );
}
