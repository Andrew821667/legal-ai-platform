import Link from "next/link";

import { LEGAL_DOC_LINKS, LEGAL_OPERATOR_INN, LEGAL_OPERATOR_NAME } from "@/lib/legalProfile";

/** Текст согласия (см. lib/pd-consent.ts) — одинаковый во всех формах. */
export default function PdConsentText({ linkClassName = "underline underline-offset-2" }: { linkClassName?: string }) {
  return (
    <>
      Даю согласие {LEGAL_OPERATOR_NAME} (ИНН {LEGAL_OPERATOR_INN}) на обработку моих персональных данных на
      условиях{" "}
      <Link href={LEGAL_DOC_LINKS.pdConsent} target="_blank" className={linkClassName}>
        согласия на обработку персональных данных
      </Link>
      .
    </>
  );
}
