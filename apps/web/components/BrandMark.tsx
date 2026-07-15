import type { CSSProperties } from "react";

type BrandMarkProps = {
  size?: number;
  className?: string;
  style?: CSSProperties;
  title?: string;
};

export default function BrandMark({
  size = 40,
  className,
  style,
  title,
}: BrandMarkProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      fill="none"
      className={className}
      style={style}
      role={title ? "img" : undefined}
      aria-hidden={title ? undefined : true}
    >
      {title ? <title>{title}</title> : null}
      <defs>
        <linearGradient id="brand-frame" x1="13" y1="13" x2="53" y2="45" gradientUnits="userSpaceOnUse">
          <stop stopColor="#67e8f9" />
          <stop offset="1" stopColor="#3b82f6" />
        </linearGradient>
        <linearGradient id="brand-verdict" x1="18" y1="27" x2="48" y2="44" gradientUnits="userSpaceOnUse">
          <stop stopColor="#fcd34d" />
          <stop offset="1" stopColor="#f59e0b" />
        </linearGradient>
      </defs>
      <rect x="1" y="1" width="62" height="62" rx="15" fill="#0a1423" stroke="#334155" strokeWidth="2" />
      <path
        d="M17 17h26c6 0 9 4 9 9v9"
        stroke="url(#brand-frame)"
        strokeWidth="5"
        strokeLinecap="round"
      />
      <path
        d="M14 25v18c0 6 4 9 10 9h15"
        stroke="#475569"
        strokeWidth="5"
        strokeLinecap="round"
      />
      <path
        d="m21 30 10 13 16-22"
        stroke="url(#brand-verdict)"
        strokeWidth="6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
