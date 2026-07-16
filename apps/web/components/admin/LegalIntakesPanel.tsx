"use client";

import { useEffect, useMemo, useState } from "react";
import { RefreshCw, Save, Search, Scale } from "lucide-react";

type IntakeStatus =
  | "received"
  | "needs_clarification"
  | "conflict_check"
  | "scope_preparation"
  | "proposal_sent"
  | "accepted"
  | "declined"
  | "closed";
type ConflictStatus = "unchecked" | "clear" | "potential" | "conflict";

type LegalIntake = {
  id: string;
  created_at: string;
  client_type: string;
  legal_area: string;
  description: string;
  urgency: string;
  deadline: string | null;
  region: string | null;
  status: IntakeStatus;
  conflict_status: ConflictStatus;
  assigned_to: string | null;
  internal_note: string | null;
  lead_name: string | null;
  lead_contact: string | null;
  lead_company: string | null;
  lead_source: string;
};

const statusLabels: Record<IntakeStatus, string> = {
  received: "Получено",
  needs_clarification: "Нужно уточнение",
  conflict_check: "Проверка конфликта",
  scope_preparation: "Оценка объема",
  proposal_sent: "Условия направлены",
  accepted: "Принято в работу",
  declined: "Отказ",
  closed: "Закрыто",
};
const conflictLabels: Record<ConflictStatus, string> = {
  unchecked: "Не проверен",
  clear: "Конфликта нет",
  potential: "Возможен конфликт",
  conflict: "Конфликт подтвержден",
};
const areaLabels: Record<string, string> = {
  contracts: "Договоры",
  disputes: "Споры и суды",
  corporate: "Корпоративное право",
  employment: "Трудовое право",
  tax_compliance: "Налоги и комплаенс",
  real_estate: "Недвижимость",
  it_ip_data: "IT, IP и данные",
  family_inheritance: "Семья и наследство",
  debt_bankruptcy: "Долги и банкротство",
  other: "Другое",
};
const clientLabels: Record<string, string> = {
  company: "Компания",
  entrepreneur: "ИП",
  individual: "Частное лицо",
  unknown: "Не определено",
};

export default function LegalIntakesPanel() {
  const [items, setItems] = useState<LegalIntake[]>([]);
  const [filter, setFilter] = useState<"all" | IntakeStatus>("all");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState<Record<string, boolean>>({});
  const [error, setError] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const params = filter === "all" ? "" : `?status=${encodeURIComponent(filter)}`;
      const response = await fetch(`/api/admin/legal-intakes${params}`, { cache: "no-store" });
      const data = await response.json();
      if (!response.ok) throw new Error(data?.detail || "Не удалось загрузить обращения");
      setItems(Array.isArray(data.intakes) ? data.intakes : []);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Не удалось загрузить обращения");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, [filter]);

  const updateLocal = (id: string, patch: Partial<LegalIntake>) => {
    setItems((current) => current.map((item) => (item.id === id ? { ...item, ...patch } : item)));
  };

  const save = async (item: LegalIntake) => {
    setSaving((current) => ({ ...current, [item.id]: true }));
    setError("");
    try {
      const response = await fetch("/api/admin/legal-intakes", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          id: item.id,
          status: item.status,
          conflict_status: item.conflict_status,
          assigned_to: item.assigned_to || null,
          internal_note: item.internal_note || null,
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data?.detail || "Не удалось сохранить обращение");
      updateLocal(item.id, data.intake);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Не удалось сохранить обращение");
    } finally {
      setSaving((current) => ({ ...current, [item.id]: false }));
    }
  };

  const filtered = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) return items;
    return items.filter((item) =>
      [item.lead_name, item.lead_contact, item.lead_company, item.description, item.region]
        .filter(Boolean)
        .join(" ")
        .toLowerCase()
        .includes(query),
    );
  }, [items, search]);

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 rounded-lg border border-slate-700 bg-slate-800/60 p-4 lg:flex-row">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
          <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Имя, контакт или задача" className="w-full rounded-lg border border-slate-700 bg-slate-800 py-2.5 pl-9 pr-3 text-sm text-slate-200" />
        </div>
        <select value={filter} onChange={(event) => setFilter(event.target.value as "all" | IntakeStatus)} className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-2.5 text-sm text-slate-200">
          <option value="all">Все этапы</option>
          {Object.entries(statusLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
        <button onClick={() => void load()} className="inline-flex items-center justify-center gap-2 rounded-lg border border-slate-700 bg-slate-800 px-4 py-2.5 text-sm text-slate-200">
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          Обновить
        </button>
      </div>

      {error && <p className="rounded-lg border border-red-700/50 bg-red-900/30 p-3 text-sm text-red-200">{error}</p>}
      {!loading && filtered.length === 0 && <p className="rounded-lg border border-slate-700 bg-slate-800/40 p-5 text-sm text-slate-400">Обращений по текущему фильтру нет.</p>}

      {filtered.map((item) => (
        <article key={item.id} className="rounded-lg border border-slate-700 bg-slate-800/50 p-4">
          <div className="flex flex-col gap-4 xl:flex-row xl:justify-between">
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2 text-xs text-slate-400">
                <span className="inline-flex items-center gap-1 text-amber-300"><Scale className="h-4 w-4" />{clientLabels[item.client_type] || item.client_type}</span>
                <span>{areaLabels[item.legal_area] || item.legal_area}</span>
                <span>{new Date(item.created_at).toLocaleString("ru-RU")}</span>
                <span>{item.lead_source}</span>
              </div>
              <h3 className="mt-2 text-base font-semibold text-white">{item.lead_name || "Без имени"}</h3>
              <p className="mt-1 text-sm text-amber-200">{item.lead_contact || "Контакт не указан"}{item.lead_company ? ` · ${item.lead_company}` : ""}</p>
              <p className="mt-3 whitespace-pre-wrap text-sm leading-relaxed text-slate-200">{item.description}</p>
              {(item.deadline || item.region) && <p className="mt-2 text-xs text-slate-400">{item.deadline ? `Срок: ${item.deadline}` : ""}{item.deadline && item.region ? " · " : ""}{item.region ? `Регион: ${item.region}` : ""}</p>}
            </div>

            <div className="grid w-full gap-3 xl:w-[360px]">
              <select value={item.status} onChange={(event) => updateLocal(item.id, { status: event.target.value as IntakeStatus })} className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-200">
                {Object.entries(statusLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              </select>
              <select value={item.conflict_status} onChange={(event) => updateLocal(item.id, { conflict_status: event.target.value as ConflictStatus })} className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-200">
                {Object.entries(conflictLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              </select>
              <input value={item.assigned_to || ""} onChange={(event) => updateLocal(item.id, { assigned_to: event.target.value })} placeholder="Ответственный" className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-200" />
              <textarea value={item.internal_note || ""} onChange={(event) => updateLocal(item.id, { internal_note: event.target.value })} rows={3} placeholder="Внутренняя заметка" className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-200" />
              <button onClick={() => void save(item)} disabled={Boolean(saving[item.id])} className="inline-flex items-center justify-center gap-2 rounded-lg bg-amber-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">
                <Save className="h-4 w-4" />
                {saving[item.id] ? "Сохранение..." : "Сохранить"}
              </button>
            </div>
          </div>
        </article>
      ))}
    </div>
  );
}
