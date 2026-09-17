"use client";

import ClientCases from "@/components/miniapp/pages/ClientCases";

/**
 * Тонкая обёртка вместо использования ClientCases напрямую в page.tsx —
 * здесь и только здесь в будущем (этап 5) появится emptyState для нового
 * посетителя без единого лида, без изменений в самой странице.
 */
export default function CabinetHome() {
  return <ClientCases variant="site" />;
}
