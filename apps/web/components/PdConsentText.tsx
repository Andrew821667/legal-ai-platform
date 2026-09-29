import Link from "next/link";

/** Текст согласия (см. lib/pd-consent.ts) — одинаковый во всех формах. */
export default function PdConsentText({ linkClassName = "underline underline-offset-2" }: { linkClassName?: string }) {
  return (
    <>
      Даю согласие на обработку моих персональных данных для рассмотрения обращения и связи со мной. Подробнее —
      в{" "}
      <Link href="/privacy" target="_blank" className={linkClassName}>
        политике конфиденциальности
      </Link>
      .
    </>
  );
}
