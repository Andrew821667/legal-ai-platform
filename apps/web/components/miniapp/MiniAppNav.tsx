"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ROUTES } from "@/lib/links";

const tabs = [
  { href: ROUTES.miniApp, label: "Главная", icon: "🏠" },
  { href: ROUTES.miniAppContent, label: "Контент", icon: "📰" },
  { href: ROUTES.miniAppTools, label: "Инструменты", icon: "🧰" },
  { href: ROUTES.miniAppSolutions, label: "Решения", icon: "⚙️" },
  { href: ROUTES.miniAppProfile, label: "Мое", icon: "👤" },
];

export default function MiniAppNav() {
  const pathname = usePathname();

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-40 border-t border-slate-800 bg-slate-950/95 backdrop-blur">
      <div className="mx-auto flex w-full max-w-md items-center justify-between px-3 py-2">
        {tabs.map((tab) => {
          const isActive = pathname === tab.href;

          return (
            <Link
              key={tab.href}
              href={tab.href}
              className={`flex min-w-[62px] flex-col items-center gap-1 rounded-lg px-2 py-1.5 text-[11px] font-medium transition-colors ${
                isActive
                  ? "bg-amber-500/20 text-amber-300"
                  : "text-slate-400 hover:bg-slate-800/80 hover:text-slate-200"
              }`}
            >
              <span className="text-base leading-none">{tab.icon}</span>
              <span>{tab.label}</span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
