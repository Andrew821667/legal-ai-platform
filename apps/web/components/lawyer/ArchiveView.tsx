"use client";

import ConfirmButton from "./ConfirmButton";
import { Card } from "./ui";
import { shortDate } from "./labels";
import { lawyerAction } from "./useTelegram";
import type { ArchiveRow } from "./types";

/**
 * Архив — клиенты, которых юрист убрал кнопкой «Удалить» в карточке.
 *
 * Отсюда два пути: вернуть в список или удалить совсем. Второе необратимо,
 * поэтому перед ним названо, что именно пропадёт — прежде всего подписанные
 * документы, которые потом не восстановить ни из чего.
 */

function plural(n: number, one: string, few: string, many: string): string {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return one;
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return few;
  return many;
}

/** Что лежит у клиента — одной строкой. */
export function footprintText(row: Pick<ArchiveRow, "intakes" | "agreements" | "signed_agreements" | "acts" | "nda_signed">): string {
  const parts: string[] = [];
  if (row.intakes) parts.push(`${row.intakes} ${plural(row.intakes, "обращение", "обращения", "обращений")}`);
  if (row.agreements) {
    const signed = row.signed_agreements ? `, подписано ${row.signed_agreements}` : "";
    parts.push(`${row.agreements} ${plural(row.agreements, "договор", "договора", "договоров")}${signed}`);
  }
  if (row.acts) parts.push(`${row.acts} ${plural(row.acts, "акт", "акта", "актов")}`);
  if (row.nda_signed) parts.push("NDA подписан");
  return parts.join(" · ") || "ничего, кроме карточки";
}

export default function ArchiveView({
  rows,
  initData,
  onChanged,
  onOpen,
}: {
  rows: ArchiveRow[] | null;
  initData: string;
  onChanged: () => void;
  onOpen: (leadId: string) => void;
}) {
  if (rows === null) return null;
  if (rows.length === 0) {
    return (
      <Card>
        <p className="text-lw-base text-lw-muted">
          Архив пуст. Клиент попадает сюда кнопкой «Удалить» в шапке своей карточки.
        </p>
      </Card>
    );
  }

  return (
    <div className="space-y-2">
      <p className="px-1 text-lw-sm text-lw-muted">
        Здесь клиенты, убранные из списка. Вернуть — «Восстановить»; удалить совсем — отсюда же.
      </p>
      {rows.map((row) => (
        <Card key={row.lead_id}>
          <button type="button" onClick={() => onOpen(row.lead_id)} className="block w-full text-left">
            <p className="text-lw-lg font-bold text-lw-ink">
              {row.name}
              {row.is_test ? <span className="ml-2 align-middle text-lw-sm font-semibold text-lw-muted">Тест</span> : null}
            </p>
            {row.contact || row.company ? (
              <p className="text-lw-sm text-lw-muted">{[row.contact, row.company].filter(Boolean).join(" · ")}</p>
            ) : null}
            <p className="mt-1 text-lw-sm text-lw-muted">
              в архиве с {shortDate(row.archived_at)} · {footprintText(row)}
            </p>
          </button>
          <div className="mt-3 grid gap-2 sm:grid-cols-2">
            <ConfirmButton
              label="Восстановить"
              explain="Клиент вернётся в список со всеми обращениями и договорами."
              confirmLabel="Вернуть в список"
              busy="Возвращаю…"
              onConfirm={async () => {
                await lawyerAction(`/api/lawyer/clients/${row.lead_id}/restore`, initData);
                onChanged();
              }}
            />
            <ConfirmButton
              label="Удалить навсегда"
              danger
              explain={
                <>
                  <p className="font-semibold">Удалить «{row.name}» без возможности восстановления?</p>
                  <p className="mt-1">Пропадёт: {footprintText(row)}, переписка и история.</p>
                  {row.signed_agreements || row.acts || row.nda_signed ? (
                    <p className="mt-1 text-lw-danger">
                      Среди них подписанные документы — после удаления их не восстановить.
                    </p>
                  ) : null}
                </>
              }
              confirmLabel="Удалить навсегда"
              busy="Удаляю…"
              onConfirm={async () => {
                await lawyerAction(`/api/lawyer/clients/${row.lead_id}`, initData, undefined, "DELETE");
                onChanged();
              }}
            />
          </div>
        </Card>
      ))}
    </div>
  );
}
