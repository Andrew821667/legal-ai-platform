type HeroBackdropVariant =
  | "home"
  | "legal"
  | "engineering"
  | "services"
  | "solutions"
  | "insights"
  | "collaboration";

type HeroBackdropProps = {
  variant: HeroBackdropVariant;
  tone?: "light" | "dark";
  priority?: boolean;
};

type Background = {
  desktop: string;
  mobile?: string;
  position: string;
  alt: string;
};

const backgrounds: Record<HeroBackdropVariant, Background> = {
  home: {
    desktop: "/images/visual-v2/home-hero-v2-desktop",
    mobile: "/images/visual-v2/home-hero-v2-mobile",
    position: "center",
    alt: "AI Verdict — автоматизация юридических процессов с помощью искусственного интеллекта",
  },
  legal: {
    desktop: "/images/visual-v2/legal-hero-v2-desktop",
    mobile: "/images/visual-v2/legal-hero-v2-mobile",
    position: "center",
    alt: "Legal AI — искусственный интеллект для юридической работы",
  },
  engineering: {
    desktop: "/images/visual-v2/engineering-hero-v2-desktop",
    mobile: "/images/visual-v2/engineering-hero-v2-mobile",
    position: "center",
    alt: "Инженерная практика AI Verdict — прикладные AI-системы и интеграции",
  },
  services: {
    desktop: "/images/ai-verdict-services-hero-v1.jpg",
    position: "70% center",
    alt: "Услуги AI Verdict по автоматизации юридической работы",
  },
  solutions: {
    desktop: "/images/ai-verdict-solutions-hero-v1.jpg",
    position: "72% center",
    alt: "Решения AI Verdict для юридических команд и бизнеса",
  },
  insights: {
    desktop: "/images/ai-verdict-insights-hero-v1.jpg",
    position: "70% center",
    alt: "Экспертные материалы AI Verdict о Legal AI",
  },
  collaboration: {
    desktop: "/images/ai-verdict-collaboration-hero-v1.jpg",
    position: "72% center",
    alt: "Совместная работа юридической и инженерной практик AI Verdict",
  },
};

export default function HeroBackdrop({ variant, tone = "dark", priority = false }: HeroBackdropProps) {
  const background = backgrounds[variant];
  const modern = Boolean(background.mobile);

  return (
    <div aria-hidden="true" className="pointer-events-none absolute inset-0 overflow-hidden">
      {modern ? (
        <picture>
          <source
            media="(max-width: 639px)"
            srcSet={`${background.mobile}-480.avif`}
            type="image/avif"
          />
          <source media="(max-width: 639px)" srcSet={`${background.mobile}.webp`} type="image/webp" />
          <source srcSet={`${background.desktop}.avif`} type="image/avif" />
          <source srcSet={`${background.desktop}.webp`} type="image/webp" />
          <img
            alt={background.alt}
            className="absolute inset-0 h-full w-full scale-[1.01] object-cover"
            decoding={priority ? "sync" : "async"}
            fetchPriority={priority ? "high" : "auto"}
            loading={priority ? "eager" : "lazy"}
            src={`${background.desktop}.webp`}
            style={{ objectPosition: background.position }}
          />
        </picture>
      ) : (
        <img
          alt={background.alt}
          className="absolute inset-0 h-full w-full scale-[1.01] object-cover"
          decoding={priority ? "sync" : "async"}
          fetchPriority={priority ? "high" : "auto"}
          loading={priority ? "eager" : "lazy"}
          src={background.desktop}
          style={{ objectPosition: background.position }}
        />
      )}
      <div
        className={
          tone === "light"
            ? modern
              ? "absolute inset-0 bg-[linear-gradient(180deg,rgba(232,238,246,0.82)_0%,rgba(232,238,246,0.58)_56%,rgba(226,232,240,0.08)_100%)] sm:bg-[linear-gradient(90deg,rgba(232,238,246,0.78)_0%,rgba(232,238,246,0.50)_48%,rgba(218,226,237,0.03)_100%)]"
              : "absolute inset-0 bg-[linear-gradient(90deg,rgba(232,238,246,0.84)_0%,rgba(232,238,246,0.58)_50%,rgba(218,226,237,0.12)_100%)]"
            : "absolute inset-0 bg-[linear-gradient(90deg,rgba(2,6,23,0.88)_0%,rgba(15,23,42,0.62)_52%,rgba(15,23,42,0.16)_100%)]"
        }
      />
      <div
        className={
          tone === "light"
            ? "absolute inset-0 bg-[linear-gradient(180deg,rgba(255,255,255,0.02)_0%,rgba(226,232,240,0.28)_100%)]"
            : "absolute inset-0 bg-[linear-gradient(180deg,rgba(2,6,23,0.04)_0%,rgba(2,6,23,0.62)_100%)]"
        }
      />
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_78%_34%,rgba(245,158,11,0.12),transparent_32%)]" />
    </div>
  );
}
