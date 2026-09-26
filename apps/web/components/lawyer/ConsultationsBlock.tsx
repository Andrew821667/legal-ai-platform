"use client";

import { useEffect, useState } from "react";

import { dayLabel, moscowStarts, parseTimes, timeLabel } from "@/lib/consultation";
import { formatRub } from "@/lib/money";
import { lawyerAction, lawyerFetch } from "./useTelegram";

/**
 * «Консультации»: юрист открывает время, клиенты записываются на сайте
 * (/consultation) и платят по QR. Здесь — всё открытое время и записи:
 * закрыть свободное, снять бронь, подтвердить оплату.
 */

type SlotRow = {
  slot_id: string;
  starts_at: string;
  duration_min: number;
  status: "free" | "held" | "claimed" | "confirmed";
  code: string | null;
  price_minor: number | null;
  held_until: string | null;
  client: string | null;
  lead_id: string | null;
  receipt_at: string | null;
};

const STATUS: Record<SlotRow["status"], string> = {
  free: "свободно",
  held: "бронь, ждёт оплаты",
  claimed: "клиент сообщил об оплате",
  confirmed: "оплачено",
};

export default function ConsultationsBlock({
  initData,
  onChanged,
  version,
}: {
  initData: string;
  onChanged?: () => void;
  /** Метка обновления «Задач»: подтвердили оплату там — перечитать и здесь. */
  version?: string;
}) {
  const [rows, setRows] = useState<SlotRow[] | null>(null);
  const [price, setPrice] = useState<number | null>(null);
  const [date, setDate] = useState("");
  const [times, setTimes] = useState("");
  const [duration, setDuration] = useState(60);
  const [note, setNote] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = async () => {
    try {
      const data = await lawyerFetch<{ slots: SlotRow[]; price_minor: number }>("/api/lawyer/consultations", initData);
      setRows(data.slots);
      setPrice(data.price_minor);
    } catch (err) {
      setNote(err instanceof Error ? err.message : "Не удалось загрузить консультации");
    }
  };

  useEffect(() => {
    void load();
  }, [initData, version]);

  const parsed = parseTimes(times);

  const open = async () => {
    const starts = moscowStarts(date, parsed);
    if (!starts.length) return setNote("Укажите дату и время, например «10:00, 12:00, 15:30».");
    setBusy(true);
    setNote(null);
    try {
      const result = await lawyerAction<{ created: unknown[]; skipped: number }>("/api/lawyer/consultations", initData, {
        starts_at: starts,
        duration_min: duration,
      });
      setNote(
        `Открыто: ${result.created.length}.` +
          (result.skipped ? ` Пропущено ${result.skipped} — прошедшее или уже открытое время.` : ""),
      );
      setTimes("");
      await load();
    } catch (err) {
      setNote(err instanceof Error ? err.message : "Не удалось открыть время");
    } finally {
      setBusy(false);
    }
  };

  const act = async (row: SlotRow, action: "close" | "release" | "confirm") => {
    if (action === "release" && row.status === "confirmed" &&
        !window.confirm("Оплата уже подтверждена. Снять бронь? Деньги клиенту нужно будет вернуть самостоятельно.")) {
      return;
    }
    try {
      if (action === "close") {
        await lawyerAction(`/api/lawyer/consultations/slots/${row.slot_id}`, initData, undefined, "DELETE");
      } else {
        await lawyerAction(`/api/lawyer/consultations/${row.slot_id}/${action}`, initData, {});
      }
      await load();
      onChanged?.();
    } catch (err) {
      setNote(err instanceof Error ? err.message : "Не получилось");
    }
  };

  const upcoming = (rows || []).filter((row) => new Date(row.starts_at).getTime() > Date.now() - 2 * 3_600_000);
  const byDay = new Map<string, SlotRow[]>();
  for (const row of upcoming) {
    const key = dayLabel(row.starts_at);
    byDay.set(key, [...(byDay.get(key) || []), row]);
  }

  return (
    <div className="rounded-xl bg-lw-cell p-3 text-lw-sm text-lw-muted">
      <p className="text-lw-ink">Консультации{price ? ` · ${formatRub(price)}` : ""}</p>
      <p className="mt-1">
        Клиенты записываются на открытое время на странице ai-verdict.ru/consultation и платят по QR. Бронь без оплаты
        снимается сама.
      </p>

      <div className="mt-2 flex flex-wrap items-center gap-2">
        <input type="date" value={date} onChange={(event) => setDate(event.target.value)} className="lw-input !w-auto !py-1.5" />
        <input
          value={times}
          onChange={(event) => setTimes(event.target.value)}
          placeholder="10:00, 12:00, 15:30"
          className="lw-input min-w-0 flex-1 !py-1.5"
        />
        <select value={duration} onChange={(event) => setDuration(Number(event.target.value))} className="lw-input !w-auto !py-1.5">
          {[30, 45, 60, 90].map((minutes) => (
            <option key={minutes} value={minutes}>
              {minutes} мин
            </option>
          ))}
        </select>
        <button type="button" disabled={busy} onClick={() => void open()} className="lw-btn !px-4 !py-2 !text-[15px]">
          Открыть{parsed.length ? ` (${parsed.length})` : ""}
        </button>
      </div>

      {rows && upcoming.length === 0 ? <p className="mt-2">Открытого времени нет.</p> : null}
      {[...byDay.entries()].map(([day, items]) => (
        <div key={day} className="mt-3">
          <p className="text-lw-ink">{day}</p>
          <ul className="mt-1 space-y-1">
            {items.map((row) => (
              <li key={row.slot_id} className="flex flex-wrap items-baseline justify-between gap-2">
                <span>
                  <b className="text-lw-ink">{timeLabel(row.starts_at)}</b> · {row.duration_min} мин ·{" "}
                  <span className={row.status === "confirmed" ? "text-lw-success" : row.status === "free" ? "" : "text-lw-warning"}>
                    {STATUS[row.status]}
                  </span>
                  {row.client ? ` · ${row.client}` : ""}
                  {row.code && row.status !== "free" ? ` · код ${row.code}` : ""}
                  {row.status === "confirmed" && !row.receipt_at ? " · чек не отмечен" : ""}
                </span>
                <span className="flex gap-2">
                  {row.status === "free" ? (
                    <button type="button" onClick={() => void act(row, "close")} className="underline underline-offset-2">
                      закрыть
                    </button>
                  ) : (
                    <>
                      {row.status === "held" || row.status === "claimed" ? (
                        <button type="button" onClick={() => void act(row, "confirm")} className="text-lw-primary underline underline-offset-2">
                          оплата пришла
                        </button>
                      ) : null}
                      <button type="button" onClick={() => void act(row, "release")} className="underline underline-offset-2">
                        снять бронь
                      </button>
                    </>
                  )}
                </span>
              </li>
            ))}
          </ul>
        </div>
      ))}
      {note ? <p className="mt-2">{note}</p> : null}
    </div>
  );
}
