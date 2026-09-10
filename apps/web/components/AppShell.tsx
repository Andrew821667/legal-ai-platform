"use client";

import { useEffect } from "react";
import { usePathname } from "next/navigation";

import Footer from "@/components/Footer";
import Header from "@/components/Header";
import WebAssistant from "@/components/WebAssistant";
import { captureLeadAttribution } from "@/lib/lead-attribution";
import { isLightOpsTheme } from "@/lib/visualTheme";

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  // /lawyer — то же самое соображение, что и для /miniapp: это не страница
  // сайта, а самостоятельный экран, который в основном открывают внутри
  // Telegram или добавленным на экран «Домой». Шапка и подвал публичного
  // сайта там были бы лишним экраном поверх и без того тесного мобильного
  // вида — на скриншоте это было отчётливо видно.
  const isChromelessAppRoute = pathname.startsWith("/miniapp") || pathname.startsWith("/lawyer");
  const isInternalRoute = pathname.startsWith("/admin") || pathname.startsWith("/monitor");

  useEffect(() => {
    if (!isChromelessAppRoute && !isInternalRoute) captureLeadAttribution();
  }, [isInternalRoute, isChromelessAppRoute]);

  if (isChromelessAppRoute) {
    return <>{children}</>;
  }

  return (
    <>
      <Header />
      <div className={isLightOpsTheme && !isInternalRoute ? "visual-light-ops" : undefined}>{children}</div>
      <Footer />
      {!isInternalRoute && <WebAssistant />}
    </>
  );
}
