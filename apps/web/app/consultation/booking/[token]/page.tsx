import type { Metadata } from "next";

import BookingStatus from "@/components/consultation/BookingStatus";
import { isLightOpsTheme } from "@/lib/visualTheme";

// Личная страница брони: адрес с ключом не индексируется и не кэшируется.
export const metadata: Metadata = {
  title: "Ваша запись на консультацию",
  robots: { index: false, follow: false, nocache: true },
  referrer: "no-referrer",
};

export const dynamic = "force-dynamic";

export default async function BookingPage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  return (
    <main className={`${isLightOpsTheme ? "visual-light-ops" : ""} min-h-screen bg-slate-900 text-slate-100`}>
      <div className="mx-auto w-full max-w-3xl px-4 pb-16 pt-24 sm:px-6 sm:pt-28">
        <p className="text-sm font-semibold uppercase tracking-wide text-amber-300">Запись на консультацию</p>
        <div className="mt-4">
          <BookingStatus token={token} />
        </div>
      </div>
    </main>
  );
}
