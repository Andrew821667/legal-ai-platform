import Link from "next/link";
import { ReactNode } from "react";

type LegalPageFrameProps = {
  title: string;
  description: string;
  updatedAt: string;
  children: ReactNode;
};

export default function LegalPageFrame({
  title,
  description,
  updatedAt,
  children,
}: LegalPageFrameProps) {
  return (
    <main className="min-h-screen bg-slate-50">
      <div className="mx-auto max-w-4xl px-4 py-20 sm:px-6 lg:px-8">
        <div className="mb-12">
          <h1 className="mb-4 text-4xl font-bold text-slate-900 md:text-5xl">{title}</h1>
          <p className="text-lg text-slate-600">{description}</p>
          <p className="mt-4 text-sm text-slate-500">Последнее обновление: {updatedAt}</p>
        </div>

        <div className="space-y-8">{children}</div>

        <div className="mt-12 border-t border-slate-200 pt-8">
          <Link
            href="/"
            className="inline-flex items-center font-semibold text-amber-600 transition-colors hover:text-amber-700"
          >
            ← Вернуться на главную
          </Link>
        </div>
      </div>
    </main>
  );
}
