"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { CalendarClock } from "lucide-react";

import TurnstileWidget from "@/components/TurnstileWidget";
import { groupByDay, timeLabel, whenLabel, type FreeSlot } from "@/lib/consultation";
import { getLeadAttribution, trackLeadConversion } from "@/lib/lead-attribution";
import { formatRub } from "@/lib/money";

const HONEYPOT_FIELD_NAME =
  (process.env.NEXT_PUBLIC_LEAD_FORM_HONEYPOT_FIELD || "company_website").trim() || "company_website";
const TURNSTILE_SITE_KEY = (process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY || "").trim();
const CHALLENGE_MODE = (process.env.NEXT_PUBLIC_LEAD_FORM_CHALLENGE_MODE || "off").trim().toLowerCase();

/**
 * Запись на консультацию: свободное время юриста → короткая заявка → бронь
 * на время оплаты → страница брони с QR. Заявка создаётся тем же путём, что
 * форма юрпомощи (/api/legal-intakes), с тем же антиспамом.
 */
export default function ConsultationBooking() {
  const router = useRouter();
  const [slots, setSlots] = useState<FreeSlot[] | null>(null);
  const [price, setPrice] = useState<number | null>(null);
  const [holdMinutes, setHoldMinutes] = useState(30);
  const [loadError, setLoadError] = useState("");
  const [selected, setSelected] = useState<FreeSlot | null>(null);
  const [name, setName] = useState("");
  const [contact, setContact] = useState("");
  const [description, setDescription] = useState("");
  const [consent, setConsent] = useState(false);
  const [honeypot, setHoneypot] = useState("");
  const [challengeRequired, setChallengeRequired] = useState(CHALLENGE_MODE === "always");
  const [challengeToken, setChallengeToken] = useState("");
  const [startedAtMs] = useState(() => Date.now());
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const load = async () => {
    try {
      const response = await fetch("/api/consultation/slots", { cache: "no-store" });
      const data = (await response.json()) as {
        slots?: FreeSlot[];
        price_minor?: number;
        hold_minutes?: number;
        detail?: string;
      };
      if (!response.ok) throw new Error(data.detail || "Не удалось загрузить расписание.");
      setSlots(data.slots || []);
      setPrice(data.price_minor ?? null);
      setHoldMinutes(data.hold_minutes || 30);
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : "Не удалось загрузить расписание.");
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const days = useMemo(() => groupByDay(slots || []), [slots]);

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setError("");
    setNotice("");
    if (!selected) return setError("Выберите время.");
    if (description.trim().length < 20) return setError("Опишите вопрос хотя бы в нескольких предложениях.");
    if (!consent) return setError("Нужно согласие на обработку персональных данных.");
    if (challengeRequired && TURNSTILE_SITE_KEY && !challengeToken) {
      return setError("Подтвердите, что заявку отправляет человек.");
    }
    setSubmitting(true);
    const utm = getLeadAttribution();
    try {
      const response = await fetch("/api/legal-intakes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name,
          contact,
          description,
          client_type: "unknown",
          legal_area: "other",
          consultation_slot_id: selected.slot_id,
          source_context: "consultation_booking",
          consentAccepted: consent,
          turnstile_token: challengeToken,
          _started_at_ms: startedAtMs,
          [HONEYPOT_FIELD_NAME]: honeypot,
          ...utm,
        }),
      });
      const data = (await response.json()) as {
        detail?: string;
        message?: string;
        challenge_required?: boolean;
        slot_taken?: boolean;
        booking_token?: string;
        intake_id?: string;
      };
      if (!response.ok) {
        if (data.challenge_required) setChallengeRequired(true);
        if (data.slot_taken) {
          setSelected(null);
          void load();
        }
        throw new Error(data.detail || "Не удалось записаться.");
      }
      if (data.intake_id) trackLeadConversion("legal_help", utm, "legal_consultation");
      if (data.booking_token) {
        router.push(`/consultation/booking/${data.booking_token}`);
        return;
      }
      setNotice(data.message || "Заявка принята. Юрист свяжется с вами.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось записаться.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-8">
      <section className="rounded-xl border border-slate-700 bg-slate-900 p-5 md:p-7">
        <div className="flex items-center gap-2 text-amber-300">
          <CalendarClock className="h-5 w-5" />
          <h2 className="text-xl font-semibold text-white">Выберите время</h2>
        </div>
        {loadError ? <p className="mt-4 text-sm text-red-300">{loadError}</p> : null}
        {slots === null && !loadError ? <p className="mt-4 text-sm text-slate-400">Загружаю расписание…</p> : null}
        {slots !== null && days.length === 0 ? (
          <p className="mt-4 text-sm leading-6 text-slate-300">
            Свободного времени сейчас нет. Оставьте заявку в{" "}
            <Link href="/legal-help#legal-help-form" className="text-amber-300 underline underline-offset-2">
              форме юридической помощи
            </Link>{" "}
            — юрист предложит время сам.
          </p>
        ) : null}
        <div className="mt-5 space-y-4">
          {days.map((day) => (
            <div key={day.day}>
              <p className="text-sm font-semibold text-slate-200">{day.label}</p>
              <div className="mt-2 flex flex-wrap gap-2">
                {day.slots.map((slot) => (
                  <button
                    key={slot.slot_id}
                    type="button"
                    onClick={() => setSelected(slot)}
                    className={`rounded-lg border px-3 py-2 text-sm font-semibold ${
                      selected?.slot_id === slot.slot_id
                        ? "border-amber-400 bg-amber-500 text-slate-950"
                        : "border-slate-600 text-slate-100 hover:border-amber-400"
                    }`}
                  >
                    {timeLabel(slot.starts_at)}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
        {days.length ? <p className="mt-4 text-xs text-slate-400">Время московское.</p> : null}
      </section>

      {selected ? (
        <form onSubmit={onSubmit} className="space-y-4 rounded-xl border border-slate-700 bg-slate-900 p-5 md:p-7">
          <p className="text-lg font-semibold text-white">
            {whenLabel(selected.starts_at)} · {selected.duration_min} минут
            {price !== null ? ` · ${formatRub(price)}` : ""}
          </p>
          <label className="block">
            <span className="text-sm text-slate-300">Кратко опишите вопрос</span>
            <textarea
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              rows={4}
              maxLength={4000}
              placeholder="Что случилось, какие документы есть и какой результат нужен"
              className="mt-1 w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 text-slate-100"
            />
          </label>
          <div className="grid gap-4 md:grid-cols-2">
            <label className="block">
              <span className="text-sm text-slate-300">Имя</span>
              <input value={name} onChange={(event) => setName(event.target.value)} maxLength={120}
                className="mt-1 w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 text-slate-100" />
            </label>
            <label className="block">
              <span className="text-sm text-slate-300">Контакт для связи</span>
              <input value={contact} onChange={(event) => setContact(event.target.value)} maxLength={255} required
                placeholder="Телефон, email или @telegram"
                className="mt-1 w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 text-slate-100" />
            </label>
          </div>
          <input
            type="text"
            name={HONEYPOT_FIELD_NAME}
            value={honeypot}
            onChange={(event) => setHoneypot(event.target.value)}
            tabIndex={-1}
            autoComplete="off"
            className="hidden"
            aria-hidden="true"
          />
          <label className="flex items-start gap-3 text-sm text-slate-300">
            <input type="checkbox" checked={consent} onChange={(event) => setConsent(event.target.checked)} className="mt-1" />
            <span>
              Согласен на обработку данных для записи и связи со мной. Подробнее в{" "}
              <Link href="/privacy" className="text-amber-300 underline underline-offset-2">политике конфиденциальности</Link>.
            </span>
          </label>
          {challengeRequired && TURNSTILE_SITE_KEY ? (
            <TurnstileWidget siteKey={TURNSTILE_SITE_KEY} enabled={challengeRequired} onToken={setChallengeToken} />
          ) : null}
          {error ? <p className="rounded-lg border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-200">{error}</p> : null}
          {notice ? <p className="rounded-lg border border-emerald-500/40 bg-emerald-500/10 p-3 text-sm text-slate-100">{notice}</p> : null}
          <button type="submit" disabled={submitting}
            className="inline-flex rounded-lg bg-amber-500 px-5 py-3 text-sm font-semibold text-slate-950 hover:bg-amber-400 disabled:opacity-60">
            {submitting ? "Записываю…" : "Записаться и перейти к оплате"}
          </button>
          <p className="text-xs leading-5 text-slate-400">
            Время закрепляется за вами на {holdMinutes} минут для оплаты. Не указывайте в описании паспортные данные и
            реквизиты карт.
          </p>
        </form>
      ) : null}
    </div>
  );
}
