import BrandMark from "@/components/BrandMark";

type OgCardProps = {
  eyebrow: string;
  title: string;
  description: string;
  variant?: "home" | "legal" | "engineering" | "automation";
};

const accents = {
  home: "#d97706",
  legal: "#b45309",
  engineering: "#64748b",
  automation: "#d97706",
};

export default function OgCard({ eyebrow, title, description, variant = "home" }: OgCardProps) {
  const accent = accents[variant];

  return (
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        position: "relative",
        overflow: "hidden",
        background: "linear-gradient(135deg, #f8fafc 0%, #e2e8f0 58%, #cbd5e1 100%)",
        color: "#0f172a",
        padding: "56px",
        fontFamily: "Arial",
      }}
    >
      <div style={{ position: "absolute", right: -40, top: -70, width: 540, height: 540, border: `2px solid ${accent}44`, borderRadius: 80, transform: "rotate(18deg)" }} />
      <div style={{ position: "absolute", right: 110, top: 110, width: 340, height: 340, border: "2px solid #47556955", borderRadius: 64, transform: "rotate(18deg)" }} />
      <div style={{ position: "absolute", right: 230, top: 235, width: 116, height: 116, display: "flex", background: accent, borderRadius: 28, boxShadow: `0 20px 55px ${accent}55` }} />

      <div style={{ display: "flex", alignItems: "center", gap: "16px", fontSize: 30, fontWeight: 700 }}>
        <BrandMark size={54} />
        <div>AI Verdict</div>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: "18px", maxWidth: 910 }}>
        <div style={{ fontSize: 24, color: accent, fontWeight: 700, textTransform: "uppercase", letterSpacing: 1.2 }}>
          {eyebrow}
        </div>
        <div style={{ fontSize: 60, fontWeight: 700, lineHeight: 1.08 }}>{title}</div>
        <div style={{ fontSize: 28, color: "#334155", lineHeight: 1.3, maxWidth: 900 }}>{description}</div>
      </div>

      <div style={{ display: "flex", fontSize: 24, color: "#475569" }}>ai-verdict.ru</div>
    </div>
  );
}
