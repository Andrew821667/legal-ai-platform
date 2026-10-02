"use client";

import { useCallback, useEffect, useState } from "react";

import { shortDate } from "./labels";
import { Card, SectionTitle } from "./ui";
import { lawyerAction, lawyerFetch } from "./useTelegram";

type FileRow = {
  id: string;
  intake_id: string | null;
  direction: "to_client" | "from_client";
  file_name: string;
  size: number;
  note: string | null;
  created_at: string | null;
  downloaded_at: string | null;
};

const ACCEPT = ".pdf,.doc,.docx,.rtf,.odt,.txt,.xls,.xlsx,.csv,.ods,.jpg,.jpeg,.png,.heic,.webp,.zip";

function fileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} Б`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} КБ`;
  return `${(bytes / (1024 * 1024)).toFixed(1).replace(".", ",")} МБ`;
}

/**
 * «Файлы» в карточке клиента: документы, загруженные клиентом в кабинете, и
 * результаты работы, которые юрист передаёт клиенту. Файлы хранятся у нас,
 * зашифрованными; в Telegram клиенту — только уведомление «документ в
 * кабинете». Раньше передать результат клиенту без Telegram было нечем.
 *
 * Скачивание — обычной ссылкой в браузере (сессия юриста в куке). Внутри
 * Telegram ссылка без подтверждения личности не откроется — как и PDF
 * договора, файл скачивается из рабочего места в браузере.
 */
export default function CaseFilesBlock({
  leadId,
  initData,
  insideTelegram,
  intakes,
  onChanged,
}: {
  leadId: string;
  initData: string;
  insideTelegram: boolean;
  intakes: { intake_id: string; label: string }[];
  onChanged?: () => void;
}) {
  const [files, setFiles] = useState<FileRow[] | null>(null);
  const [intakeId, setIntakeId] = useState(intakes[0]?.intake_id || "");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);

  const load = useCallback(async () => {
    try {
      setFiles((await lawyerFetch<{ files: FileRow[] }>(`/api/lawyer/clients/${leadId}/files`, initData)).files);
    } catch (err) {
      setMessage({ ok: false, text: err instanceof Error ? err.message : "Не удалось загрузить список файлов" });
    }
  }, [leadId, initData]);

  useEffect(() => {
    void load();
  }, [load]);

  const send = async (file: File) => {
    setBusy(true);
    setMessage(null);
    try {
      const form = new FormData();
      form.set("file", file);
      if (intakeId) form.set("intake_id", intakeId);
      if (note.trim()) form.set("note", note.trim());
      const response = await fetch(`/api/lawyer/clients/${leadId}/files`, {
        method: "POST",
        headers: { "x-telegram-init-data": initData },
        body: form,
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(body?.detail || `Ошибка ${response.status}`);
      setNote("");
      setMessage({
        ok: true,
        text: (body.delivered || []).includes("telegram_notice")
          ? `«${file.name}» — в кабинете клиента; в Telegram ушло уведомление без имени файла.`
          : `«${file.name}» — в кабинете клиента. Telegram у клиента нет — сообщите ему, что документ в кабинете.`,
      });
      await load();
      onChanged?.();
    } catch (err) {
      setMessage({ ok: false, text: err instanceof Error ? err.message : "Не получилось отправить файл" });
    } finally {
      setBusy(false);
    }
  };

  const remove = async (row: FileRow) => {
    if (!window.confirm(`Удалить «${row.file_name}»? Клиент перестанет его видеть.`)) return;
    try {
      await lawyerAction(`/api/lawyer/files/${row.id}`, initData, undefined, "DELETE");
      await load();
    } catch (err) {
      setMessage({ ok: false, text: err instanceof Error ? err.message : "Не удалось удалить" });
    }
  };

  const rows = files || [];
  return (
    <section>
      <SectionTitle count={rows.length}>Файлы</SectionTitle>
      <Card>
        {files === null ? <p className="text-lw-sm text-lw-muted">Загружаю…</p> : null}
        {files && rows.length === 0 ? (
          <p className="text-lw-sm text-lw-muted">Файлов пока нет. Результат работы клиенту — кнопкой ниже.</p>
        ) : null}
        <ul className="space-y-2">
          {rows.map((row) => (
            <li key={row.id} className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1 text-lw-sm">
              {insideTelegram ? (
                <span className="min-w-0 truncate text-lw-ink">{row.file_name}</span>
              ) : (
                <a
                  href={`/api/lawyer/files/${row.id}`}
                  className="min-w-0 truncate text-lw-ink underline underline-offset-2 hover:text-lw-primary"
                >
                  {row.file_name}
                </a>
              )}
              <span className="flex shrink-0 items-baseline gap-2 text-lw-muted">
                <span>{row.direction === "to_client" ? "клиенту" : "от клиента"}</span>
                <span>{fileSize(row.size)}</span>
                <span>{shortDate(row.created_at)}</span>
                {row.direction === "to_client" ? (
                  <span className={row.downloaded_at ? "text-lw-success" : ""}>
                    {row.downloaded_at ? "скачан" : "не скачан"}
                  </span>
                ) : null}
                {row.direction === "to_client" ? (
                  <button type="button" onClick={() => void remove(row)} className="underline underline-offset-2 hover:text-lw-danger">
                    удалить
                  </button>
                ) : null}
              </span>
              {row.note ? <span className="w-full text-lw-muted">{row.note}</span> : null}
            </li>
          ))}
        </ul>
        {insideTelegram && rows.length ? (
          <p className="mt-2 text-lw-sm text-lw-muted">Скачать файлы можно в рабочем месте в браузере.</p>
        ) : null}
        <div className="mt-3 space-y-2">
          {intakes.length > 1 ? (
            <select value={intakeId} onChange={(event) => setIntakeId(event.target.value)} className="lw-input w-full">
              {intakes.map((item) => (
                <option key={item.intake_id} value={item.intake_id}>
                  {item.label}
                </option>
              ))}
            </select>
          ) : null}
          <input
            value={note}
            onChange={(event) => setNote(event.target.value)}
            maxLength={1000}
            placeholder="Пояснение к файлу (необязательно)"
            className="lw-input w-full"
          />
          <div className="flex flex-wrap items-center gap-3">
            <label className={`lw-btn !px-4 !py-2 !text-[15px] cursor-pointer ${busy ? "opacity-60" : ""}`}>
              <input
                type="file"
                className="hidden"
                accept={ACCEPT}
                disabled={busy}
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  event.target.value = "";
                  if (file) void send(file);
                }}
              />
              {busy ? "Отправляю…" : "Отправить файл клиенту"}
            </label>
            {message ? (
              <span className={`text-lw-sm ${message.ok ? "text-lw-muted" : "text-lw-danger"}`}>{message.text}</span>
            ) : null}
          </div>
        </div>
      </Card>
    </section>
  );
}
