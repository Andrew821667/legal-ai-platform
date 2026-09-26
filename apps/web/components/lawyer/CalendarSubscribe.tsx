"use client";

import { useState } from "react";

import { lawyerFetch } from "./useTelegram";

/**
 * «Сроки в календаре телефона»: подписка на ленту ICS. Сроки по делам,
 * истекающие договоры и сроки оплаты актов появятся в календаре сами, с
 * напоминаниями накануне и в день срока. Имён клиентов в событиях нет —
 * календарь синхронизируется с облаком.
 */
export default function CalendarSubscribe({ initData }: { initData: string }) {
  const [urls, setUrls] = useState<{ https: string; webcal: string } | null>(null);
  const [note, setNote] = useState<string | null>(null);

  const load = async () => {
    setNote(null);
    try {
      setUrls(await lawyerFetch<{ https: string; webcal: string }>("/api/lawyer/calendar-link", initData));
    } catch (err) {
      setNote(err instanceof Error ? err.message : "Не удалось получить адрес");
    }
  };

  const copy = async () => {
    if (!urls) return;
    try {
      await navigator.clipboard.writeText(urls.https);
      setNote("Адрес скопирован. В Google Календаре: «Другие календари» → «Добавить по URL».");
    } catch {
      setNote(urls.https);
    }
  };

  return (
    <div className="rounded-xl bg-lw-cell p-3 text-lw-sm text-lw-muted">
      <p className="text-lw-ink">Сроки в календаре телефона</p>
      <p className="mt-1">
        Сроки по делам, истекающие договоры и оплата актов — с напоминанием накануне и в день срока. Имён клиентов в
        календаре нет, только номер и ссылка на карточку.
      </p>
      {urls ? (
        <div className="mt-2 flex flex-wrap gap-2">
          <a href={urls.webcal} className="lw-btn !px-4 !py-2 !text-[15px]">
            Подписаться
          </a>
          <button type="button" onClick={() => void copy()} className="lw-btn-quiet !px-4 !py-2">
            Скопировать адрес
          </button>
        </div>
      ) : (
        <button type="button" onClick={() => void load()} className="mt-2 text-lw-primary underline underline-offset-2">
          Показать адрес подписки
        </button>
      )}
      {urls ? (
        <p className="mt-2">Адрес личный: не пересылайте его — по нему видны все сроки практики.</p>
      ) : null}
      {note ? <p className="mt-2 break-all">{note}</p> : null}
    </div>
  );
}
