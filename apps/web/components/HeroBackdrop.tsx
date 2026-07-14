type HeroBackdropVariant = "home" | "services" | "solutions" | "insights" | "collaboration";

type HeroBackdropProps = {
  variant: HeroBackdropVariant;
  tone?: "light" | "dark";
};

const backgrounds: Record<HeroBackdropVariant, { image: string; position: string }> = {
  home: {
    image: "/images/ai-verdict-hero-v1.jpg",
    position: "68% center",
  },
  services: {
    image: "/images/ai-verdict-services-hero-v1.jpg",
    position: "70% center",
  },
  solutions: {
    image: "/images/ai-verdict-solutions-hero-v1.jpg",
    position: "72% center",
  },
  insights: {
    image: "/images/ai-verdict-insights-hero-v1.jpg",
    position: "70% center",
  },
  collaboration: {
    image: "/images/ai-verdict-collaboration-hero-v1.jpg",
    position: "72% center",
  },
};

export default function HeroBackdrop({ variant, tone = "dark" }: HeroBackdropProps) {
  const background = backgrounds[variant];

  return (
    <div aria-hidden="true" className="pointer-events-none absolute inset-0 overflow-hidden">
      <div
        className="absolute inset-0 scale-[1.01] bg-cover"
        style={{ backgroundImage: `url('${background.image}')`, backgroundPosition: background.position }}
      />
      <div
        className={
          tone === "light"
            ? "absolute inset-0 bg-[linear-gradient(90deg,rgba(232,238,246,0.88)_0%,rgba(232,238,246,0.62)_50%,rgba(218,226,237,0.14)_100%)]"
            : "absolute inset-0 bg-[linear-gradient(90deg,rgba(2,6,23,0.88)_0%,rgba(15,23,42,0.62)_52%,rgba(15,23,42,0.16)_100%)]"
        }
      />
      <div
        className={
          tone === "light"
            ? "absolute inset-0 bg-[linear-gradient(180deg,rgba(255,255,255,0.04)_0%,rgba(226,232,240,0.34)_100%)]"
            : "absolute inset-0 bg-[linear-gradient(180deg,rgba(2,6,23,0.04)_0%,rgba(2,6,23,0.62)_100%)]"
        }
      />
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_82%_22%,rgba(245,158,11,0.16),transparent_34%)]" />
    </div>
  );
}
