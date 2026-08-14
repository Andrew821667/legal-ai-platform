import type { Metadata } from "next";
import "./globals.css";
import AppShell from "@/components/AppShell";
import GoogleAnalytics from "@/components/GoogleAnalytics";
import YandexMetrika from "@/components/YandexMetrika";
import StructuredData from "@/components/StructuredData";
import { LEGAL_OPERATOR_NAME, reportLegalProfileWarnings } from "@/lib/legalProfile";
import { SEO_SITE_URL } from "@/lib/seo";

const siteUrl = SEO_SITE_URL;
const yandexMetrikaId = process.env.NEXT_PUBLIC_YM_COUNTER_ID || "110733908";

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  applicationName: "AI Verdict",
  title: {
    default: "Автоматизация юридической работы | AI Verdict",
    template: "%s | AI Verdict",
  },
  description:
    "AI Verdict объединяет юридическую и инженерную практики. На их стыке автоматизируем юридическую функцию; отдельно оказываем юридическую помощь и создаем прикладные программные системы.",
  keywords: [
    "ИИ в юридической сфере",
    "искусственный интеллект в юриспруденции",
    "юридический ИИ",
    "Legal AI",
    "автоматизация юридической работы",
    "AI для юристов",
    "legal tech",
    "автоматизация договоров",
    "автоматизация судебной работы",
    "автоматизация комплаенс",
    "внедрение ИИ в юридический отдел",
    "анализ договоров ИИ",
    "разработка телеграм ботов",
    "автоматизация бизнес процессов",
    "интеграция CRM ERP",
    "разработка mini app",
  ],
  authors: [{ name: LEGAL_OPERATOR_NAME, url: "/team" }],
  creator: "AI Verdict",
  publisher: "AI Verdict",
  category: "legal technology",
  referrer: "origin-when-cross-origin",
  formatDetection: {
    telephone: false,
    email: false,
    address: false,
  },
  manifest: "/manifest.webmanifest",
  icons: {
    icon: "/icon.svg",
  },
  openGraph: {
    type: "website",
    locale: "ru_RU",
    url: siteUrl,
    title: "Автоматизация юридической работы | AI Verdict",
    description:
      "Юридическая и инженерная практики на стыке права, AI и прикладной разработки.",
    siteName: "AI Verdict",
    images: [
      {
        url: `${siteUrl}/opengraph-image`,
        width: 1200,
        height: 630,
        alt: "AI Verdict",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "Автоматизация юридической работы | AI Verdict",
    description:
      "Юридическая и инженерная практики на стыке права, AI и прикладной разработки.",
    images: [`${siteUrl}/twitter-image`],
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      "max-video-preview": -1,
      "max-image-preview": "large",
      "max-snippet": -1,
    },
  },
  verification: {
    google: "mTUEyeu5VGZOmD8i8uGmxG-XhDHU6MacydZDAWry8U0",
    yandex: "2559d6caccd0ac2b9",
    other: {
      "msvalidate.01": "CD03C5F5623FD1B0202D61D79DA9745E",
    },
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  reportLegalProfileWarnings();

  return (
    <html lang="ru" className="scroll-smooth">
      <head>
        <StructuredData siteUrl={siteUrl} />
      </head>
      <body className="antialiased">
        {process.env.NEXT_PUBLIC_GA_MEASUREMENT_ID && (
          <GoogleAnalytics measurementId={process.env.NEXT_PUBLIC_GA_MEASUREMENT_ID} />
        )}

        <YandexMetrika counterId={yandexMetrikaId} />

        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
