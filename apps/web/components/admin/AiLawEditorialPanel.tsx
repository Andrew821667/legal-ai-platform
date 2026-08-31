"use client";

import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import {
  Archive,
  CheckCircle2,
  ExternalLink,
  FilePlus2,
  Loader2,
  Plus,
  RefreshCw,
  Save,
  Send,
  Trash2,
} from "lucide-react";

import type { AiLawComment, AiLawCommentStatus } from "@/lib/aiLawComments";

const inputClass = "w-full rounded border border-slate-600 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none focus:border-amber-500";
const textareaClass = `${inputClass} min-h-24 resize-y`;

const statusMeta: Record<AiLawCommentStatus, { label: string; className: string }> = {
  draft: { label: "Черновик", className: "border-slate-500 text-slate-300" },
  verified: { label: "Проверено", className: "border-sky-500 text-sky-300" },
  published: { label: "Опубликовано", className: "border-emerald-500 text-emerald-300" },
  archived: { label: "Архив", className: "border-rose-500 text-rose-300" },
};

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

function emptyComment(): AiLawComment {
  const date = today();
  return {
    slug: "",
    status: "draft",
    lawNumber: "",
    lawDate: date,
    lawTitle: "",
    title: "",
    seoTitle: "",
    description: "",
    summary: "",
    publishedAt: "",
    reviewedAt: "",
    readingTime: "7 минут",
    audience: [],
    keywords: [],
    officialSource: { title: "Официальный интернет-портал правовой информации", url: "", publicationId: "" },
    effectiveStages: [{ date, label: "Первый этап", title: "", legalBasis: "", summary: "", points: [] }],
    sections: [{ heading: "", paragraphs: [], bullets: [] }],
    misconceptions: [],
    actions: [{ title: "", description: "" }],
    watchItems: [],
  };
}

function splitLines(value: string): string[] {
  return value.split("\n").map((item) => item.trim()).filter(Boolean);
}

function splitParagraphs(value: string): string[] {
  return value.split(/\n\s*\n/).map((item) => item.trim()).filter(Boolean);
}

function Field({ label, children, wide = false }: { label: string; children: ReactNode; wide?: boolean }) {
  return (
    <label className={wide ? "block md:col-span-2" : "block"}>
      <span className="mb-1.5 block text-xs font-medium text-slate-300">{label}</span>
      {children}
    </label>
  );
}

function RemoveButton({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={label}
      aria-label={label}
      className="rounded p-2 text-slate-400 hover:bg-rose-500/10 hover:text-rose-300"
    >
      <Trash2 className="h-4 w-4" />
    </button>
  );
}

export default function AiLawEditorialPanel() {
  const [rows, setRows] = useState<AiLawComment[]>([]);
  const [comment, setComment] = useState<AiLawComment>(() => emptyComment());
  const [selectedSlug, setSelectedSlug] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const response = await fetch("/api/admin/ai-law-comments", { cache: "no-store" });
      const data = await response.json();
      if (!response.ok) throw new Error(data?.detail || "Не удалось загрузить материалы");
      const nextRows = Array.isArray(data?.comments) ? data.comments as AiLawComment[] : [];
      setRows(nextRows);
      if (selectedSlug) {
        const selected = nextRows.find((item) => item.slug === selectedSlug);
        if (selected) setComment(structuredClone(selected));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось загрузить материалы");
    } finally {
      setLoading(false);
    }
  }, [selectedSlug]);

  useEffect(() => {
    void load();
  }, [load]);

  const counts = useMemo(() => Object.fromEntries(
    Object.keys(statusMeta).map((status) => [status, rows.filter((item) => item.status === status).length]),
  ) as Record<AiLawCommentStatus, number>, [rows]);

  const choose = (row: AiLawComment) => {
    setSelectedSlug(row.slug);
    setComment(structuredClone(row));
    setMessage("");
    setError("");
  };

  const create = () => {
    setSelectedSlug(null);
    setComment(emptyComment());
    setMessage("");
    setError("");
  };

  const save = async (status = comment.status) => {
    setSaving(true);
    setMessage("");
    setError("");
    try {
      const next = structuredClone(comment);
      next.status = status;
      if ((status === "verified" || status === "published") && !next.reviewedAt) next.reviewedAt = today();
      if (status === "published" && !next.publishedAt) next.publishedAt = today();
      const response = await fetch("/api/admin/ai-law-comments", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ comment: next }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data?.detail || "Не удалось сохранить материал");
      const saved = data.comment as AiLawComment;
      setComment(saved);
      setSelectedSlug(saved.slug);
      setRows((current) => [saved, ...current.filter((item) => item.slug !== saved.slug)]);
      const indexNow = data.indexNow === "accepted" ? " URL отправлен в IndexNow." : "";
      setMessage(`${statusMeta[saved.status].label}. Изменения сохранены.${indexNow}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось сохранить материал");
    } finally {
      setSaving(false);
    }
  };

  const archive = async () => {
    if (!window.confirm("Перенести материал в архив и убрать его из публичного раздела?")) return;
    await save("archived");
  };

  const set = <K extends keyof AiLawComment>(key: K, value: AiLawComment[K]) => {
    setComment((current) => ({ ...current, [key]: value }));
  };

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-700 pb-4">
        <div>
          <h3 className="text-lg font-semibold text-white">Комментарии законодательства об ИИ</h3>
          <div className="mt-2 flex flex-wrap gap-2 text-xs">
            {(Object.keys(statusMeta) as AiLawCommentStatus[]).map((status) => (
              <span key={status} className={`rounded border px-2 py-1 ${statusMeta[status].className}`}>
                {statusMeta[status].label}: {counts[status]}
              </span>
            ))}
          </div>
        </div>
        <div className="flex gap-2">
          <button type="button" onClick={() => void load()} title="Обновить" className="rounded border border-slate-600 p-2 text-slate-300 hover:border-slate-400">
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          </button>
          <button type="button" onClick={create} className="inline-flex items-center gap-2 rounded bg-amber-600 px-3 py-2 text-sm font-semibold text-white hover:bg-amber-500">
            <FilePlus2 className="h-4 w-4" />
            Новый материал
          </button>
        </div>
      </div>

      <div className="grid gap-5 xl:grid-cols-[18rem_minmax(0,1fr)]">
        <aside className="max-h-[70vh] overflow-y-auto border-r border-slate-700 pr-3">
          {loading && !rows.length ? (
            <p className="flex items-center gap-2 py-4 text-sm text-slate-400"><Loader2 className="h-4 w-4 animate-spin" />Загрузка</p>
          ) : rows.map((row) => (
            <button
              key={row.slug}
              type="button"
              onClick={() => choose(row)}
              className={`mb-2 w-full border-l-2 px-3 py-3 text-left ${selectedSlug === row.slug ? "border-amber-500 bg-slate-700/60" : "border-slate-700 bg-slate-900/40 hover:border-slate-500"}`}
            >
              <span className={`text-xs ${statusMeta[row.status].className.split(" ").at(-1)}`}>{statusMeta[row.status].label}</span>
              <span className="mt-1 block text-sm font-medium leading-5 text-slate-100">{row.title || row.slug}</span>
              <span className="mt-1 block text-xs text-slate-500">{row.lawNumber || "Без номера"}</span>
            </button>
          ))}
        </aside>

        <form className="min-w-0 space-y-7" onSubmit={(event) => { event.preventDefault(); void save(); }}>
          <section className="space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <span className={`rounded border px-2.5 py-1 text-xs ${statusMeta[comment.status].className}`}>{statusMeta[comment.status].label}</span>
              {comment.status === "published" ? (
                <a href={`/ai-law/${comment.slug}`} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-sm text-sky-300 hover:text-sky-200">
                  Открыть материал <ExternalLink className="h-4 w-4" />
                </a>
              ) : null}
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <Field label="Slug">
                <input className={inputClass} value={comment.slug} disabled={selectedSlug !== null} onChange={(event) => set("slug", event.target.value.toLowerCase().replace(/\s+/g, "-"))} placeholder="nomer-fz-ai-2026" />
              </Field>
              <Field label="Время чтения">
                <input className={inputClass} value={comment.readingTime} onChange={(event) => set("readingTime", event.target.value)} />
              </Field>
              <Field label="Номер акта">
                <input className={inputClass} value={comment.lawNumber} onChange={(event) => set("lawNumber", event.target.value)} placeholder="243-ФЗ" />
              </Field>
              <Field label="Дата акта">
                <input type="date" className={inputClass} value={comment.lawDate} onChange={(event) => set("lawDate", event.target.value)} />
              </Field>
              <Field label="Полное название акта" wide>
                <input className={inputClass} value={comment.lawTitle} onChange={(event) => set("lawTitle", event.target.value)} />
              </Field>
              <Field label="Заголовок материала" wide>
                <input className={inputClass} value={comment.title} onChange={(event) => set("title", event.target.value)} />
              </Field>
              <Field label="SEO-заголовок" wide>
                <input className={inputClass} value={comment.seoTitle} onChange={(event) => set("seoTitle", event.target.value)} />
              </Field>
              <Field label="SEO-описание" wide>
                <textarea className={textareaClass} value={comment.description} onChange={(event) => set("description", event.target.value)} />
              </Field>
              <Field label="Краткое резюме" wide>
                <textarea className={textareaClass} value={comment.summary} onChange={(event) => set("summary", event.target.value)} />
              </Field>
              <Field label="Дата юридической проверки">
                <input type="date" className={inputClass} value={comment.reviewedAt} onChange={(event) => set("reviewedAt", event.target.value)} />
              </Field>
              <Field label="Дата публикации">
                <input type="date" className={inputClass} value={comment.publishedAt} onChange={(event) => set("publishedAt", event.target.value)} />
              </Field>
            </div>
          </section>

          <section className="border-t border-slate-700 pt-6">
            <h4 className="mb-4 font-semibold text-white">Официальный источник</h4>
            <div className="grid gap-4 md:grid-cols-2">
              <Field label="Название источника">
                <input className={inputClass} value={comment.officialSource.title} onChange={(event) => set("officialSource", { ...comment.officialSource, title: event.target.value })} />
              </Field>
              <Field label="Номер опубликования">
                <input className={inputClass} value={comment.officialSource.publicationId} onChange={(event) => set("officialSource", { ...comment.officialSource, publicationId: event.target.value })} />
              </Field>
              <Field label="Ссылка на pravo.gov.ru" wide>
                <input type="url" className={inputClass} value={comment.officialSource.url} onChange={(event) => set("officialSource", { ...comment.officialSource, url: event.target.value })} />
              </Field>
            </div>
          </section>

          <section className="grid gap-4 border-t border-slate-700 pt-6 md:grid-cols-2">
            <Field label="Кого касается, по одному пункту в строке">
              <textarea className={textareaClass} value={comment.audience.join("\n")} onChange={(event) => set("audience", splitLines(event.target.value))} />
            </Field>
            <Field label="Поисковые фразы, по одной в строке">
              <textarea className={textareaClass} value={comment.keywords.join("\n")} onChange={(event) => set("keywords", splitLines(event.target.value))} />
            </Field>
          </section>

          <section className="space-y-4 border-t border-slate-700 pt-6">
            <div className="flex items-center justify-between">
              <h4 className="font-semibold text-white">Этапы вступления в силу</h4>
              <button type="button" onClick={() => set("effectiveStages", [...comment.effectiveStages, { date: today(), label: "Новый этап", title: "", legalBasis: "", summary: "", points: [] }])} className="inline-flex items-center gap-1 text-sm text-amber-300 hover:text-amber-200"><Plus className="h-4 w-4" />Этап</button>
            </div>
            {comment.effectiveStages.map((stage, idx) => (
              <div key={`${idx}-${stage.date}`} className="border-l-2 border-amber-600 bg-slate-900/40 p-4">
                <div className="mb-3 flex items-center justify-between"><span className="text-sm font-medium text-slate-200">Этап {idx + 1}</span><RemoveButton label="Удалить этап" onClick={() => set("effectiveStages", comment.effectiveStages.filter((_, itemIdx) => itemIdx !== idx))} /></div>
                <div className="grid gap-3 md:grid-cols-2">
                  <Field label="Дата"><input type="date" className={inputClass} value={stage.date} onChange={(event) => set("effectiveStages", comment.effectiveStages.map((item, itemIdx) => itemIdx === idx ? { ...item, date: event.target.value } : item))} /></Field>
                  <Field label="Метка"><input className={inputClass} value={stage.label} onChange={(event) => set("effectiveStages", comment.effectiveStages.map((item, itemIdx) => itemIdx === idx ? { ...item, label: event.target.value } : item))} /></Field>
                  <Field label="Название" wide><input className={inputClass} value={stage.title} onChange={(event) => set("effectiveStages", comment.effectiveStages.map((item, itemIdx) => itemIdx === idx ? { ...item, title: event.target.value } : item))} /></Field>
                  <Field label="Правовое основание" wide><input className={inputClass} value={stage.legalBasis} onChange={(event) => set("effectiveStages", comment.effectiveStages.map((item, itemIdx) => itemIdx === idx ? { ...item, legalBasis: event.target.value } : item))} /></Field>
                  <Field label="Описание" wide><textarea className={textareaClass} value={stage.summary} onChange={(event) => set("effectiveStages", comment.effectiveStages.map((item, itemIdx) => itemIdx === idx ? { ...item, summary: event.target.value } : item))} /></Field>
                  <Field label="Положения, по одному в строке" wide><textarea className={textareaClass} value={stage.points.join("\n")} onChange={(event) => set("effectiveStages", comment.effectiveStages.map((item, itemIdx) => itemIdx === idx ? { ...item, points: splitLines(event.target.value) } : item))} /></Field>
                </div>
              </div>
            ))}
          </section>

          <section className="space-y-4 border-t border-slate-700 pt-6">
            <div className="flex items-center justify-between">
              <h4 className="font-semibold text-white">Содержательные разделы</h4>
              <button type="button" onClick={() => set("sections", [...comment.sections, { heading: "", paragraphs: [], bullets: [] }])} className="inline-flex items-center gap-1 text-sm text-amber-300 hover:text-amber-200"><Plus className="h-4 w-4" />Раздел</button>
            </div>
            {comment.sections.map((section, idx) => (
              <div key={idx} className="border-l-2 border-sky-700 bg-slate-900/40 p-4">
                <div className="mb-3 flex items-center justify-between"><span className="text-sm font-medium text-slate-200">Раздел {idx + 1}</span><RemoveButton label="Удалить раздел" onClick={() => set("sections", comment.sections.filter((_, itemIdx) => itemIdx !== idx))} /></div>
                <div className="space-y-3">
                  <Field label="Заголовок"><input className={inputClass} value={section.heading} onChange={(event) => set("sections", comment.sections.map((item, itemIdx) => itemIdx === idx ? { ...item, heading: event.target.value } : item))} /></Field>
                  <Field label="Абзацы, разделяйте пустой строкой"><textarea className={textareaClass} value={section.paragraphs.join("\n\n")} onChange={(event) => set("sections", comment.sections.map((item, itemIdx) => itemIdx === idx ? { ...item, paragraphs: splitParagraphs(event.target.value) } : item))} /></Field>
                  <Field label="Список, по одному пункту в строке"><textarea className={textareaClass} value={(section.bullets || []).join("\n")} onChange={(event) => set("sections", comment.sections.map((item, itemIdx) => itemIdx === idx ? { ...item, bullets: splitLines(event.target.value) } : item))} /></Field>
                </div>
              </div>
            ))}
          </section>

          <section className="space-y-4 border-t border-slate-700 pt-6">
            <div className="flex items-center justify-between">
              <h4 className="font-semibold text-white">Мифы и неверные трактовки</h4>
              <button type="button" onClick={() => set("misconceptions", [...comment.misconceptions, { claim: "", reality: "" }])} className="inline-flex items-center gap-1 text-sm text-amber-300 hover:text-amber-200"><Plus className="h-4 w-4" />Миф</button>
            </div>
            {comment.misconceptions.map((item, idx) => (
              <div key={idx} className="grid gap-3 border-l-2 border-rose-700 bg-slate-900/40 p-4 md:grid-cols-[1fr_1fr_auto]">
                <Field label="Неверное утверждение"><textarea className={textareaClass} value={item.claim} onChange={(event) => set("misconceptions", comment.misconceptions.map((row, itemIdx) => itemIdx === idx ? { ...row, claim: event.target.value } : row))} /></Field>
                <Field label="Корректная трактовка"><textarea className={textareaClass} value={item.reality} onChange={(event) => set("misconceptions", comment.misconceptions.map((row, itemIdx) => itemIdx === idx ? { ...row, reality: event.target.value } : row))} /></Field>
                <RemoveButton label="Удалить миф" onClick={() => set("misconceptions", comment.misconceptions.filter((_, itemIdx) => itemIdx !== idx))} />
              </div>
            ))}
          </section>

          <section className="space-y-4 border-t border-slate-700 pt-6">
            <div className="flex items-center justify-between">
              <h4 className="font-semibold text-white">Практические действия</h4>
              <button type="button" onClick={() => set("actions", [...comment.actions, { title: "", description: "" }])} className="inline-flex items-center gap-1 text-sm text-amber-300 hover:text-amber-200"><Plus className="h-4 w-4" />Действие</button>
            </div>
            {comment.actions.map((action, idx) => (
              <div key={idx} className="grid gap-3 border-l-2 border-emerald-700 bg-slate-900/40 p-4 md:grid-cols-[0.8fr_1.2fr_auto]">
                <Field label="Заголовок"><input className={inputClass} value={action.title} onChange={(event) => set("actions", comment.actions.map((row, itemIdx) => itemIdx === idx ? { ...row, title: event.target.value } : row))} /></Field>
                <Field label="Описание"><textarea className={textareaClass} value={action.description} onChange={(event) => set("actions", comment.actions.map((row, itemIdx) => itemIdx === idx ? { ...row, description: event.target.value } : row))} /></Field>
                <RemoveButton label="Удалить действие" onClick={() => set("actions", comment.actions.filter((_, itemIdx) => itemIdx !== idx))} />
              </div>
            ))}
          </section>

          <section className="border-t border-slate-700 pt-6">
            <Field label="Что отслеживать дальше, по одному пункту в строке">
              <textarea className={textareaClass} value={comment.watchItems.join("\n")} onChange={(event) => set("watchItems", splitLines(event.target.value))} />
            </Field>
          </section>

          {error ? <pre className="whitespace-pre-wrap rounded border border-rose-500/50 bg-rose-500/10 p-3 text-sm text-rose-200">{error}</pre> : null}
          {message ? <p className="rounded border border-emerald-500/50 bg-emerald-500/10 p-3 text-sm text-emerald-200">{message}</p> : null}

          <div className="sticky bottom-0 flex flex-wrap gap-2 border-t border-slate-600 bg-slate-800/95 py-4 backdrop-blur">
            <button type="submit" disabled={saving} className="inline-flex items-center gap-2 rounded border border-slate-500 px-4 py-2 text-sm font-semibold text-slate-100 hover:border-slate-300 disabled:opacity-50">
              {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}Сохранить
            </button>
            {comment.status === "draft" || comment.status === "archived" ? (
              <button type="button" disabled={saving} onClick={() => void save("verified")} className="inline-flex items-center gap-2 rounded bg-sky-700 px-4 py-2 text-sm font-semibold text-white hover:bg-sky-600 disabled:opacity-50"><CheckCircle2 className="h-4 w-4" />Проверено</button>
            ) : null}
            {comment.status === "verified" ? (
              <button type="button" disabled={saving} onClick={() => void save("published")} className="inline-flex items-center gap-2 rounded bg-emerald-700 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-600 disabled:opacity-50"><Send className="h-4 w-4" />Опубликовать</button>
            ) : null}
            {comment.status === "published" ? (
              <button type="button" disabled={saving} onClick={() => void save("verified")} className="inline-flex items-center gap-2 rounded border border-sky-600 px-4 py-2 text-sm font-semibold text-sky-200 hover:bg-sky-600/10 disabled:opacity-50">Снять с публикации</button>
            ) : null}
            {selectedSlug && comment.status !== "archived" ? (
              <button type="button" disabled={saving} onClick={() => void archive()} className="ml-auto inline-flex items-center gap-2 rounded border border-rose-700 px-4 py-2 text-sm font-semibold text-rose-300 hover:bg-rose-500/10 disabled:opacity-50"><Archive className="h-4 w-4" />В архив</button>
            ) : null}
          </div>
        </form>
      </div>
    </div>
  );
}
