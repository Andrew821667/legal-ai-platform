import { AGREEMENT_STATUS } from "../components/lawyer/labels.ts";

/**
 * Выгрузка договоров для отчётности.
 *
 * Ни одного экспорта в ядре не было — для бухгалтерии цифры переписывали с
 * экрана. Файл собирается из того же ответа, что показывает вкладка «Деньги»,
 * и открывается в русском Excel без мастера импорта: BOM, чтобы кириллица
 * читалась; точка с запятой — разделитель, который Excel в русской локали
 * ждёт по умолчанию; сумма — числом с запятой, чтобы по столбцу считалась
 * сумма.
 */

export type CsvAgreement = {
  number: string;
  client: string;
  subject: string;
  status: string;
  amount_minor: number | null;
  price_text: string | null;
  created_at: string | null;
  sent_at: string | null;
  signed_at: string | null;
};

const HEADER = [
  "Номер",
  "Клиент",
  "Предмет",
  "Статус",
  "Сумма, ₽",
  "Цена в документе",
  "Составлен",
  "Отправлен",
  "Подписан",
];

function cell(value: string | null | undefined): string {
  const text = value ?? "";
  // Кавычки — если внутри разделитель, кавычка или перенос; кавычка внутри удваивается.
  return /[;"\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

/** «12500,50» — число для Excel, а не подпись «12 500,50 ₽». */
export function csvAmount(minor: number | null): string {
  if (minor === null || minor === undefined) return "";
  const rubles = Math.trunc(minor / 100);
  const kopecks = Math.abs(minor % 100);
  return `${rubles},${String(kopecks).padStart(2, "0")}`;
}

/** Дата без времени, в формате, который Excel распознаёт как дату. */
export function csvDate(value: string | null | undefined): string {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleDateString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    timeZone: "Europe/Moscow",
  });
}

export function agreementsCsv(rows: CsvAgreement[]): string {
  const lines = [HEADER.map(cell).join(";")];
  for (const row of rows) {
    lines.push(
      [
        row.number,
        row.client,
        row.subject,
        AGREEMENT_STATUS[row.status] || row.status,
        csvAmount(row.amount_minor),
        row.price_text || "",
        csvDate(row.created_at),
        csvDate(row.sent_at),
        csvDate(row.signed_at),
      ]
        .map(cell)
        .join(";"),
    );
  }
  return `﻿${lines.join("\r\n")}\r\n`;
}

/** Имя файла с датой выгрузки: несколько выгрузок не перезаписывают друг друга. */
export function agreementsCsvFileName(now: Date = new Date()): string {
  const stamp = now.toLocaleDateString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    timeZone: "Europe/Moscow",
  });
  return `договоры-${stamp.split(".").reverse().join("-")}.csv`;
}
