"use client";

import { useEffect, useState } from "react";

type SummaryPhone = { client?: { phone?: string | null } };

/**
 * Телефон — единственное поле профиля, для которого кука (маска) — не
 * источник истины: полный номер живёт только в core-api (client-portal
 * summary), поэтому подтягивается отдельным клиентским запросом, а не
 * рендерится сразу на сервере вместе с именем/фото из client_profile.
 */
export default function CabinetProfileClient({ phoneMasked }: { phoneMasked?: string }) {
  const [phone, setPhone] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/client/summary", { cache: "no-store" })
      .then((response) => (response.ok ? (response.json() as Promise<SummaryPhone>) : null))
      .then((data) => {
        if (!cancelled && data?.client?.phone) setPhone(data.client.phone);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, []);

  const shown = phone ?? phoneMasked;
  if (!shown) return null;

  return (
    <p className="text-sm text-slate-600">
      Телефон: <span className="font-medium text-slate-900">{shown}</span>
    </p>
  );
}
