import type { Metadata } from "next";

const DEFAULT_SITE_URL = "https://ai-verdict.ru";
const BRAND = "AI Verdict";

function resolvePublicSiteUrl(value: string | undefined): string {
  try {
    const url = new URL(value || DEFAULT_SITE_URL);
    const hostname = url.hostname.toLowerCase();
    if (hostname === "localhost" || hostname === "127.0.0.1" || hostname === "0.0.0.0" || hostname === "::1") {
      return DEFAULT_SITE_URL;
    }
    return url.origin;
  } catch {
    return DEFAULT_SITE_URL;
  }
}

export const SEO_SITE_URL = resolvePublicSiteUrl(process.env.NEXT_PUBLIC_SITE_URL);

type PageMetadataOptions = {
  title: string;
  description: string;
  path: string;
  type?: "website" | "article" | "profile";
  index?: boolean;
  follow?: boolean;
  keywords?: string[];
  socialImage?: string;
};

export function createPageMetadata({
  title,
  description,
  path,
  type = "website",
  index = true,
  follow = true,
  keywords,
  socialImage = "/opengraph-image",
}: PageMetadataOptions): Metadata {
  const socialTitle = title.includes(BRAND) ? title : `${title} | ${BRAND}`;
  const canonicalUrl = new URL(path || "/", SEO_SITE_URL).toString();

  return {
    title,
    description,
    keywords,
    alternates: {
      canonical: canonicalUrl,
    },
    openGraph: {
      type,
      locale: "ru_RU",
      siteName: BRAND,
      url: canonicalUrl,
      title: socialTitle,
      description,
      images: [
        {
          url: socialImage,
          width: 1200,
          height: 630,
          alt: socialTitle,
        },
      ],
    },
    twitter: {
      card: "summary_large_image",
      title: socialTitle,
      description,
      images: [socialImage],
    },
    robots: {
      index,
      follow,
      nocache: !index,
      googleBot: {
        index,
        follow,
        "max-video-preview": -1,
        "max-image-preview": "large",
        "max-snippet": -1,
      },
    },
  };
}
