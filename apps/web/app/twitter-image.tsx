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
          justifyContent: "center",
          background: "linear-gradient(135deg, #0f172a, #1e293b)",
          color: "#fff",
          padding: "56px",
          fontFamily: "Arial",
          gap: "18px",
        }}
      >
        <div style={{ fontSize: 28, color: "#fbbf24" }}>Legal AI PRO</div>
        <div style={{ fontSize: 58, fontWeight: 700, lineHeight: 1.1 }}>
          AI для юридических команд
        </div>
        <div style={{ fontSize: 30, color: "#cbd5e1" }}>
          Договоры, судебная работа, комплаенс
        </div>
      </div>
    ),
    {
      ...size,
    }
  );
}
