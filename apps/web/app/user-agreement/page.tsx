import type { Metadata } from "next";
import Link from "next/link";

import LegalPageFrame from "@/components/LegalPageFrame";
import { createPageMetadata } from "@/lib/seo";
import {
  LEGAL_BRAND,
  LEGAL_DOC_LINKS,
  LEGAL_OPERATOR_NAME,
  LEGAL_OPERATOR_STATUS,
  LEGAL_SITE_URL,
  LEGAL_UPDATED_AT,
} from "@/lib/legalProfile";

export const metadata: Metadata = createPageMetadata({
  title: "Пользовательское соглашение",
  description:
    "Условия использования сайта, Telegram-ботов, AI-инструментов и информационных материалов платформы AI Verdict.",
  path: LEGAL_DOC_LINKS.userAgreement,
  type: "article",
});

export default function UserAgreementPage() {
  return (
    <LegalPageFrame
      title="Пользовательское соглашение"
      description="Базовые условия использования сайта, ботов и материалов проекта."
      updatedAt={LEGAL_UPDATED_AT}
    >
      <section className="rounded-xl bg-white p-8 shadow-sm">
        <h2 className="mb-4 text-2xl font-bold text-slate-900">1. Кто предоставляет сервис</h2>
        <p className="text-slate-700">
          Сервис предоставляет <strong>{LEGAL_OPERATOR_NAME}</strong> ({LEGAL_OPERATOR_STATUS}),
          действующий под брендом <strong>{LEGAL_BRAND}</strong> через сайт{" "}
          <strong>{LEGAL_SITE_URL}</strong>, Telegram-боты и связанные интерфейсы.
        </p>
      </section>

      <section className="rounded-xl bg-white p-8 shadow-sm">
        <h2 className="mb-4 text-2xl font-bold text-slate-900">2. Что считается использованием сервиса</h2>
        <ul className="list-disc space-y-2 pl-6 text-slate-700">
          <li>посещение сайта и мини-app;</li>
          <li>отправка формы, сообщения или документов;</li>
          <li>использование бота, переход по CTA и получение материалов.</li>
        </ul>
      </section>

      <section className="rounded-xl bg-white p-8 shadow-sm">
        <h2 className="mb-4 text-2xl font-bold text-slate-900">3. Ограничение ответственности</h2>
        <p className="text-slate-700">
          Материалы проекта носят информационный характер и не являются автоматической юридической
          услугой по конкретному делу. Для персональной правовой позиции требуется отдельная
          консультация и анализ документов.
        </p>
      </section>

      <section className="rounded-xl bg-white p-8 shadow-sm">
        <h2 className="mb-4 text-2xl font-bold text-slate-900">4. Где смотреть полные условия</h2>
        <p className="text-slate-700">
          Полный договорный и сервисный контур описан в{" "}
          <Link href={LEGAL_DOC_LINKS.terms} className="text-amber-700 underline">
            условиях использования
          </Link>
          . Политика обработки данных доступна в{" "}
          <Link href={LEGAL_DOC_LINKS.privacy} className="text-amber-700 underline">
            политике конфиденциальности
          </Link>
          .
        </p>
      </section>
    </LegalPageFrame>
  );
}
