import { coreGet } from "@/lib/lawyer-core";
import { agreementsCsv, agreementsCsvFileName } from "@/lib/lawyer-csv";
import type { CsvAgreement } from "@/lib/lawyer-csv";

/**
 * Выгрузка договоров — общая часть двух маршрутов: скачать в Safari и
 * отправить в чат из Telegram. Данные те же, что у вкладки «Деньги».
 */

export type CsvFile = { name: string; type: string; bytes: Uint8Array<ArrayBuffer> };

export async function agreementsCsvFile(): Promise<CsvFile | Response> {
  const upstream = await coreGet("/api/v1/lawyer/finance");
  if (!upstream.ok) return upstream;
  const finance = (await upstream.json()) as { agreements: CsvAgreement[] };
  return {
    name: agreementsCsvFileName(),
    type: "text/csv; charset=utf-8",
    bytes: new TextEncoder().encode(agreementsCsv(finance.agreements || [])),
  };
}
