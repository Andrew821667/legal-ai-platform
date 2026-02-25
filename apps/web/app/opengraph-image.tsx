import { ImageResponse } from "next/og";

export const runtime = "edge";
export const alt = "Legal AI PRO";
export const size = {
  width: 1200,
  height: 630,
};
export const contentType = "image/png";

export default function Image() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          background: "linear-gradient(135deg, #0f172a, #1e293b)",
          color: "#fff",
          padding: "56px",
          fontFamily: "Arial",
        }}
      >
        <div style={{ fontSize: 30, opacity: 0.9 }}>Legal AI PRO</div>

        <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
          <div style={{ fontSize: 64, fontWeight: 700, lineHeight: 1.1, maxWidth: 980 }}>
            Автоматизация юридической работы
          </div>
          <div style={{ fontSize: 32, color: "#cbd5e1", maxWidth: 980 }}>
            AI-решения для договоров, судебной работы и комплаенса
          </div>
        </div>

        <div style={{ fontSize: 26, color: "#fbbf24" }}>legalaipro.ru</div>
      </div>
    ),
    {
      ...size,
    }
  );
}
