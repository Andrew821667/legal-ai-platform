import type { Metadata } from "next";
import Link from "next/link";
import MiniAppStateProvider from "@/components/miniapp/MiniAppStateProvider";
import MiniAppTopBar from "@/components/miniapp/MiniAppTopBar";
import MiniAppNav from "@/components/miniapp/MiniAppNav";
import { ROUTES } from "@/lib/links";

export const metadata: Metadata = {
  title: "Mini App",
  description: "Мини-приложение Legal AI PRO: контент, инструменты, решения и персональный контур.",
};

export default function MiniAppLayout({ children }: { children: React.ReactNode }) {
  return (
    <MiniAppStateProvider>
      <main className="min-h-screen bg-slate-950 text-slate-100">
        <div className="mx-auto w-full max-w-md px-4 pb-24 pt-6">
          <div className="mb-5 rounded-xl border border-slate-800 bg-slate-900/70 p-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-xs uppercase tracking-wide text-slate-400">Legal AI PRO</p>
                <h1 className="text-lg font-semibold text-white">Mini App</h1>
              </div>
              <Link
                href={ROUTES.contractAI}
                className="rounded-lg bg-amber-500 px-3 py-2 text-xs font-semibold text-slate-950 hover:bg-amber-400 transition-colors"
              >
                Contract_AI_System
              </Link>
            </div>
          </div>

          <MiniAppTopBar />
          {children}
        </div>

        <MiniAppNav />
      </main>
    </MiniAppStateProvider>
  );
}
