"use client";

import { usePathname } from "next/navigation";

import Footer from "@/components/Footer";
import Header from "@/components/Header";

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isMiniAppRoute = pathname.startsWith("/miniapp");

  if (isMiniAppRoute) {
    return <>{children}</>;
  }

  return (
    <>
      <Header />
      {children}
      <Footer />
    </>
  );
}

