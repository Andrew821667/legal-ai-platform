import Link from "next/link";

type LegalDisclaimerProps = {
  variant?: "compact" | "panel";
  className?: string;
};

export default function LegalDisclaimer({
  variant = "compact",
  className = "",
}: LegalDisclaimerProps) {
  const baseClass =
    variant === "panel"
      ? "rounded-xl border border-amber-500/25 bg-amber-500/10 px-4 py-3 text-sm text-slate-700"
      : "text-xs leading-relaxed text-slate-500";

  return (
    <div className={`${baseClass} ${className}`.trim()}>
      <p>
        Материалы сайта, мини-app и ботов AI Verdict носят информационный характер и не заменяют
        индивидуальную юридическую консультацию. Решения по конкретному кейсу принимаются только
        после анализа документов, фактов и применимого права. Условия обработки персональных данных
        и использования сервиса:{" "}
        <Link href="/privacy" className="underline underline-offset-2 hover:text-amber-700">
          политика конфиденциальности
        </Link>{" "}
        и{" "}
        <Link href="/terms" className="underline underline-offset-2 hover:text-amber-700">
          условия использования
        </Link>
        .
      </p>
    </div>
  );
}
