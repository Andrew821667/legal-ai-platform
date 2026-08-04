"use client";

import { usePathname } from "next/navigation";

import Footer from "@/components/Footer";
import Header from "@/components/Header";
import WebAssistant from "@/components/WebAssistant";
import { isLightOpsTheme } from "@/lib/visualTheme";

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isMiniAppRoute = pathname.startsWith("/miniapp");
  const isInternalRoute = pathname.startsWith("/admin") || pathname.startsWith("/monitor");

  if (isMiniAppRoute) {
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
