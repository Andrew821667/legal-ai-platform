import type { Metadata } from "next";
import "./globals.css";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import GoogleAnalytics from "@/components/GoogleAnalytics";
import YandexMetrika from "@/components/YandexMetrika";
import StructuredData from "@/components/StructuredData";

const siteUrl = process.env.NEXT_PUBLIC_SITE_URL || "https://legalaipro.ru";

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: {
    default: "Автоматизация юридической работы | Legal AI PRO",
    template: "%s | Legal AI PRO",
  },
  description:
    "Внедряем AI для юридических команд: договоры, судебная работа, комплаенс, документооборот. Практический опыт, измеримый ROI.",
  keywords: [
    "автоматизация юридической работы",
    "AI для юристов",
    "legal tech",
    "автоматизация договоров",
    "автоматизация судебной работы",
    "автоматизация комплаенс",
    "YandexGPT для юристов",
    "GigaChat для юристов",
    "внедрение ИИ в юридический отдел",
    "анализ договоров ИИ",
  ],
  authors: [{ name: "Legal AI PRO" }],
  creator: "Legal AI PRO",
  publisher: "Legal AI PRO",
  manifest: "/manifest.webmanifest",
  icons: {
    icon: "/icon.svg",
  },
  openGraph: {
    type: "website",
    locale: "ru_RU",
    url: siteUrl,
    title: "Автоматизация юридической работы | Legal AI PRO",
    description:
      "AI-решения для юридических процессов: быстрее проверка документов, меньше рутины, прозрачная экономия.",
    siteName: "Legal AI PRO",
    images: [
      {
        url: `${siteUrl}/opengraph-image`,
        width: 1200,
        height: 630,
        alt: "Legal AI PRO",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "Автоматизация юридической работы | Legal AI PRO",
    description:
      "AI-решения для юридических процессов: договоры, судебная работа, комплаенс.",
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
    yandex: "3448a4683f1cad05",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ru" className="scroll-smooth">
      <head>
        <StructuredData siteUrl={siteUrl} />
      </head>
      <body className="antialiased">
        {process.env.NEXT_PUBLIC_GA_MEASUREMENT_ID && (
          <GoogleAnalytics measurementId={process.env.NEXT_PUBLIC_GA_MEASUREMENT_ID} />
        )}

        {process.env.NEXT_PUBLIC_YM_COUNTER_ID && (
          <YandexMetrika counterId={process.env.NEXT_PUBLIC_YM_COUNTER_ID} />
        )}

        <Header />
        {children}
        <Footer />
      </body>
    </html>
  );
}
