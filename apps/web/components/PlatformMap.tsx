import Link from "next/link";

import { PLATFORM_PARTS, type PlatformPartId } from "@/lib/platformParts";

type PlatformMapProps = {
  /**
   * Visual density. "full" — large cards with description + CTA, used on the
   * site home page. "compact" — tighter cards with icon + name + short
   * description (no CTA), used inside the Telegram Mini App where vertical
   * space is precious.
   */
  variant?: "full" | "compact";
  /**
   * The card representing the current surface gets an "вы здесь" badge and
   * an amber accent border, plus its CTA is disabled. Helps the user place
   * themselves on the map.
   */
  highlightId?: PlatformPartId;
  /** Optional section title; default depends on variant. */
  title?: string;
  /** Optional intro paragraph under the title. */
  intro?: string;
  /** Optional className passthrough for the outer section. */
  className?: string;
};

export default function PlatformMap({
  variant = "full",
  highlightId,
  title,
  intro,
  className = "",
}: PlatformMapProps) {
  const compact = variant === "compact";
  const heading = title ?? (compact ? "Другие части платформы" : "Платформа AI Verdict: с чего удобно начать");
  const introText =
    intro ??
    (compact
      ? "Из Telegram можно перейти в любую другую точку платформы."
      : "Выберите удобную точку входа. Заявка попадет в нужное направление.");

  return (
    <section
      className={`${compact ? "" : "max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16"} ${className}`.trim()}
      aria-labelledby="platform-map-heading"
    >
      {!compact && (
        <div className="max-w-3xl mb-8">
          <h2 id="platform-map-heading" className="text-3xl md:text-4xl font-semibold text-white">
            {heading}
          </h2>
          <p className="mt-4 text-slate-300">{introText}</p>
        </div>
      )}
      {compact && (
        <header className="mb-3">
          <h2 id="platform-map-heading" className="text-sm font-semibold text-amber-300">
            {heading}
          </h2>
          <p className="mt-1 text-xs text-slate-400">{introText}</p>
        </header>
      )}

      <ul
        className={
          compact
            ? "grid grid-cols-1 gap-2"
            : "grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4"
        }
      >
        {PLATFORM_PARTS.map((part) => {
          const Icon = part.icon;
          const isCurrent = part.id === highlightId;
          const baseCard = compact
            ? "rounded-lg p-3 flex items-start gap-3 transition-colors"
            : "rounded-2xl p-6 flex flex-col gap-3 h-full transition-colors";
          const accent = isCurrent
            ? "border border-amber-500/60 bg-amber-500/10"
            : "border border-slate-800 bg-slate-800/60 hover:border-amber-500/40";

          const linkProps = part.external
            ? { href: part.url, target: "_blank" as const, rel: "noopener noreferrer" }
            : { href: part.url };

          return (
            <li key={part.id}>
              <article className={`${baseCard} ${accent}`}>
                <div className={compact ? "shrink-0 mt-0.5" : "flex items-center gap-3"}>
                  <div
                    className={
                      compact
                        ? "rounded-md bg-slate-900 p-1.5 text-amber-300"
                        : "rounded-lg bg-slate-900 p-2 text-amber-300"
                    }
                  >
                    <Icon className={compact ? "h-4 w-4" : "h-5 w-5"} aria-hidden />
                  </div>
                  {!compact && (
                    <h3 className="text-lg font-semibold text-white flex items-center gap-2">
                      {part.name}
                      {isCurrent && (
                        <span className="rounded-full border border-amber-500/60 bg-amber-500/15 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-amber-200">
                          вы здесь
                        </span>
                      )}
                    </h3>
                  )}
                </div>

                <div className={compact ? "flex-1" : ""}>
                  {compact && (
                    <p className="text-sm font-semibold text-white flex items-center gap-2">
                      {part.name}
                      {isCurrent && (
                        <span className="rounded-full border border-amber-500/60 bg-amber-500/15 px-1.5 py-0 text-[9px] font-medium uppercase tracking-wide text-amber-200">
                          здесь
                        </span>
                      )}
                    </p>
                  )}
                  <p className={compact ? "mt-0.5 text-xs text-slate-300 leading-relaxed" : "text-sm text-slate-300 leading-relaxed"}>
                    {part.description}
                  </p>

                  {!compact && (
                    <div className="mt-auto pt-4 flex flex-wrap gap-3 text-sm">
                      {isCurrent ? (
                        <span className="inline-flex items-center rounded-lg border border-slate-700 px-4 py-2 text-slate-700 cursor-default">
                          Вы уже здесь
                        </span>
                      ) : part.external ? (
                        <a
                          {...linkProps}
                          className="inline-flex items-center rounded-lg bg-amber-500 px-4 py-2 font-semibold text-slate-950 hover:bg-amber-400 transition-colors"
                        >
                          {part.ctaLabel} →
                        </a>
                      ) : (
                        <Link
                          {...linkProps}
                          className="inline-flex items-center rounded-lg bg-amber-500 px-4 py-2 font-semibold text-slate-950 hover:bg-amber-400 transition-colors"
                        >
                          {part.ctaLabel} →
                        </Link>
                      )}
                      {part.secondary && (
                        part.secondary.external ? (
                          <a
                            href={part.secondary.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center rounded-lg border border-slate-700 px-4 py-2 text-slate-200 hover:border-amber-400 hover:text-amber-200 transition-colors"
                          >
                            {part.secondary.label}
                          </a>
                        ) : (
                          <Link
                            href={part.secondary.url}
                            className="inline-flex items-center rounded-lg border border-slate-700 px-4 py-2 text-slate-200 hover:border-amber-400 hover:text-amber-200 transition-colors"
                          >
                            {part.secondary.label}
                          </Link>
                        )
                      )}
                    </div>
                  )}

                  {compact && !isCurrent && (
                    <div className="mt-1 text-xs">
                      {part.external ? (
                        <a {...linkProps} className="text-amber-300 hover:text-amber-200 underline">
                          {part.ctaLabel} →
                        </a>
                      ) : (
                        <Link {...linkProps} className="text-amber-300 hover:text-amber-200 underline">
                          {part.ctaLabel} →
                        </Link>
                      )}
                    </div>
                  )}
                </div>
              </article>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
