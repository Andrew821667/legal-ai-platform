"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { minutesLeft, statusText, whenLabel, type Booking } from "@/lib/consultation";
import { formatRub } from "@/lib/money";

/**
 * Страница брони по её ключу: сколько осталось на оплату, QR для приложения
 * банка, «Я оплатил», отмена. Ключ в адресе знает только клиент — входить не
 * нужно, в том числе без Telegram.
 */
export default function BookingStatus({ token }: { token: string }) {
  const [booking, setBooking] = useState<Booking | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [, setTick] = useState(0);
  const [cancelled, setCancelled] = useState(false);

  const load = async () => {
    const response = await fetch(`/api/consultation/booking/${token}`, { cache: "no-store" });
    const data = (await response.json().catch(() => ({}))) as Booking & { detail?: string };
    if (!response.ok) {
      setBooking(null);
      setError(data.detail || "Запись не найдена.");
      return;
    }
    setError("");
    setBooking(data);
  };

  useEffect(() => {
    void load();
    // Остаток времени на оплату — раз в полминуты.
    const timer = window.setInterval(() => setTick((n) => n + 1), 30_000);
    return () => window.clearInterval(timer);
  }, [token]);

  const act = async (action: "claim" | "cancel") => {
    setBusy(true);
    try {
      const response = await fetch(`/api/consultation/booking/${token}/${action}`, { method: "POST" });
      const data = (await response.json().catch(() => ({}))) as { detail?: string };
      if (!response.ok) throw new Error(data.detail || "Не получилось — обновите страницу.");
      if (action === "cancel") {
        setCancelled(true);
        setBooking(null);
      } else {
        await load();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не получилось.");
    } finally {
      setBusy(false);
    }
  };

  if (cancelled) {
    return (
      <div className="rounded-xl border border-slate-700 bg-slate-900 p-6 text-slate-200">
        Запись отменена, время освобождено.{" "}
        <Link href="/consultation" className="text-amber-300 underline underline-offset-2">Выбрать другое время</Link>
      </div>
    );
  }
  if (!booking) {
    return (
      <div className="rounded-xl border border-slate-700 bg-slate-900 p-6 text-slate-200">
        {error || "Загружаю запись…"}{" "}
        {error ? (
          <Link href="/consultation" className="text-amber-300 underline underline-offset-2">Записаться заново</Link>
        ) : null}
      </div>
    );
  }

  const expired = booking.status === "held" && minutesLeft(booking.held_until) === 0;
  return (
    <div className="space-y-5">
      <section className="rounded-xl border border-slate-700 bg-slate-900 p-5 md:p-7">
        <p className="text-sm text-slate-400">Консультация юриста</p>
        <h2 className="mt-1 text-2xl font-semibold text-white">{whenLabel(booking.starts_at)}</h2>
        <p className="mt-1 text-slate-300">
          До {booking.duration_min} минут онлайн · {formatRub(booking.price_minor)}
        </p>
        <p className={`mt-4 rounded-lg p-3 text-sm ${booking.status === "confirmed" ? "bg-emerald-500/10 text-slate-100" : "bg-amber-500/10 text-amber-200"}`}>
          {statusText(booking)}
        </p>
      </section>

      {booking.status !== "confirmed" && !expired ? (
        <section className="rounded-xl border border-slate-700 bg-slate-900 p-5 md:p-7">
          <h3 className="text-lg font-semibold text-white">Оплата</h3>
          {booking.payment ? (
            <div className="mt-3 flex flex-col gap-5 md:flex-row md:items-start">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={`/api/consultation/booking/${token}/qr`}
                alt="QR-код для оплаты в приложении банка"
                width={220}
                height={220}
                className="rounded-lg bg-white p-2"
              />
              <div className="text-sm leading-6 text-slate-300">
                <p>Отсканируйте QR в приложении банка: получатель, сумма и назначение заполнятся сами.</p>
                <p className="mt-2">
                  В назначении платежа — код <b className="text-white">{booking.code}</b>: по нему юрист найдёт ваш
                  перевод.
                </p>
              </div>
            </div>
          ) : (
            <p className="mt-3 text-sm text-slate-300">
              Реквизиты для оплаты юрист пришлёт по контакту из заявки. Код для назначения платежа:{" "}
              <b className="text-white">{booking.code}</b>.
            </p>
          )}
          {booking.status === "held" ? (
            <div className="mt-5 flex flex-wrap gap-3">
              <button type="button" disabled={busy} onClick={() => void act("claim")}
                className="rounded-lg bg-amber-500 px-5 py-3 text-sm font-semibold text-slate-950 hover:bg-amber-400 disabled:opacity-60">
                Я оплатил
              </button>
              <button type="button" disabled={busy} onClick={() => void act("cancel")}
                className="rounded-lg border border-slate-600 px-5 py-3 text-sm font-semibold text-slate-200 hover:border-slate-400 disabled:opacity-60">
                Отменить запись
              </button>
            </div>
          ) : null}
        </section>
      ) : null}

      {expired ? (
        <p className="text-sm text-slate-300">
          Время бронирования истекло, и оно могло освободиться для других.{" "}
          <Link href="/consultation" className="text-amber-300 underline underline-offset-2">Выбрать время заново</Link>
        </p>
      ) : null}

      {error ? <p className="text-sm text-red-300">{error}</p> : null}

      <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 text-sm leading-6 text-slate-400">
        <p>Сохраните адрес этой страницы — по нему видно состояние записи.</p>
        <p className="mt-2">
          Если юрист не сможет провести консультацию в выбранное время, он предложит другое или вернёт оплату полностью.
          Перенос по вашей просьбе — не позднее чем за 24 часа до начала. Чек «Мой налог» юрист пришлёт после оплаты.
        </p>
      </section>
    </div>
  );
}
