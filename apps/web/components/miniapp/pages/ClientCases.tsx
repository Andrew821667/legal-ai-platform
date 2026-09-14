"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { CheckCircle2, FileCheck2, FileText, MessageSquareText, RefreshCw, ShieldCheck, X } from "lucide-react";

import { EXTERNAL_LINKS } from "@/lib/links";

type Case = {
  id: string; practice: string; legal_area: string; category?: string | null;
  description: string; status: string; without_agreement: boolean; created_at: string;
  documents: { id: string; file_name?: string | null; created_at?: string | null }[];
};
type Agreement = {
  id: string; intake_id?: string | null; number: string; revision: number; status: string;
  subject: string; price_text: string; client_details_complete: boolean; hash: string;
  viewed_at?: string | null; signed_at?: string | null;
  messages: { id: string; role: string; text: string; created_at: string }[];
};
type Act = {
  id: string; agreement_id: string; number: string; status: string; description: string;
  amount_minor: number; currency: string; hash: string; viewed_at?: string | null;
  accepted_at?: string | null; objected_at?: string | null; objection_text?: string | null;
  claimed_paid_at?: string | null; paid_at?: string | null; cancelled_at?: string | null;
};
type Summary = {
  client: { lead_id?: string | null; name?: string | null; has_cases: boolean };
  nda: { signed: boolean; signed_at?: string | null; signer_full_name?: string | null };
  cases: Case[]; agreements: Agreement[]; acts: Act[];
};
type Doc = {
  id: string; text: string; hash?: string; document_hash?: string; status: string;
  accepted_at?: string | null; objected_at?: string | null; cancelled_at?: string | null;
  payment?: { phone?: string; bank?: string; recipient?: string };
};

const practiceLabels: Record<string, string> = {
  legal: "Юридическая практика", engineering: "Инженерная практика",
  hybrid: "Автоматизация юридической функции",
};
const statusLabels: Record<string, string> = {
  received: "Получено", needs_clarification: "Уточняем задачу", conflict_check: "Проверка",
  scope_preparation: "Готовим условия", proposal_sent: "Условия отправлены", accepted: "В работе",
  declined: "Отклонено", closed: "Завершено", sent: "Отправлен", viewed: "Просмотрен",
  signed: "Подписан", claimed_paid: "Оплата заявлена", paid: "Оплачен",
};

function money(value: number) {
  return new Intl.NumberFormat("ru-RU", { style: "currency", currency: "RUB", maximumFractionDigits: 2 }).format(value / 100);
}

function telegramInitData() {
  return window.Telegram?.WebApp?.initData || "";
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: { "x-telegram-init-data": telegramInitData(), ...(init?.headers || {}) },
    cache: "no-store",
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || "Не удалось выполнить действие");
  return body as T;
}

function Button({ children, onClick, tone = "primary", disabled = false }: {
  children: React.ReactNode; onClick: () => void; tone?: "primary" | "quiet" | "danger"; disabled?: boolean;
}) {
  const colors = tone === "primary" ? "bg-amber-500 text-slate-950" : tone === "danger"
    ? "border-red-500/50 text-red-200" : "border-slate-600 text-slate-100";
  return <button type="button" disabled={disabled} onClick={onClick}
    className={`min-h-10 rounded-lg border border-transparent px-3 py-2 text-sm font-semibold disabled:opacity-50 ${colors}`}>
    {children}
  </button>;
}

export default function ClientCases() {
  const [data, setData] = useState<Summary | null>(null);
  const [doc, setDoc] = useState<Doc | null>(null);
  const [docKind, setDocKind] = useState<"nda" | "agreement" | "act" | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [note, setNote] = useState("");

  const load = useCallback(async () => {
    setError("");
    try { setData(await request<Summary>("/api/client/summary")); }
    catch (e) { setError(e instanceof Error ? e.message : "Кабинет недоступен"); }
  }, []);
  useEffect(() => { window.Telegram?.WebApp?.ready?.(); window.Telegram?.WebApp?.expand?.(); void load(); }, [load]);

  const run = async (fn: () => Promise<unknown>) => {
    setBusy(true); setError("");
    try { await fn(); await load(); }
    catch (e) { setError(e instanceof Error ? e.message : "Действие не выполнено"); }
    finally { setBusy(false); }
  };

  const openAgreement = (id: string) => run(async () => {
    const item = await request<Doc>(`/api/client/agreements/${id}`);
    if (item.status === "sent" && (item as Doc & { client_details_complete?: boolean }).client_details_complete) {
      await request(`/api/client/agreements/${id}`, { method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ action: "viewed", document_hash: item.hash }) });
      item.status = "viewed";
    }
    setDoc(item); setDocKind("agreement"); setNote("");
  });

  const openAct = (id: string) => run(async () => {
    const item = await request<Doc>(`/api/client/acts/${id}`);
    await request(`/api/client/acts/${id}`, { method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ action: "viewed", document_hash: item.document_hash }) });
    setDoc(item); setDocKind("act"); setNote("");
  });

  if (!data && !error) return <div className="flex min-h-48 items-center justify-center text-slate-300"><RefreshCw className="h-5 w-5 animate-spin" /></div>;
  if (!data) return <section className="rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-100">
    <p>{error}</p><div className="mt-3 flex flex-wrap gap-2"><Button tone="quiet" onClick={() => void load()}><RefreshCw className="mr-1 inline h-4 w-4"/>Повторить</Button><a href={EXTERNAL_LINKS.leadBot} className="inline-flex min-h-10 items-center px-2 font-semibold underline">Открыть бота-ассистента</a></div>
  </section>;

  return <section className="space-y-4">
    <header>
      <p className="text-sm text-slate-400">Личный кабинет</p>
      <h2 className="text-2xl font-semibold text-white">{data.client.name ? `${data.client.name}, ваши дела` : "Мои дела"}</h2>
      <p className="mt-1 text-sm text-slate-300">Здесь видны только обращения, связанные с вашим Telegram-аккаунтом.</p>
    </header>

    {error ? <p className="rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-100">{error}</p> : null}

    <article className="rounded-lg border border-slate-700 bg-slate-800/80 p-4">
      <div className="flex items-center gap-2"><ShieldCheck className="h-5 w-5 text-emerald-400" /><h3 className="font-semibold text-white">Конфиденциальность</h3></div>
      <p className="mt-2 text-sm text-slate-300">{data.nda.signed ? `NDA подписано${data.nda.signer_full_name ? `: ${data.nda.signer_full_name}` : ""}.` : "Перед документами и договором нужно подписать NDA."}</p>
      {!data.nda.signed && data.client.lead_id ? <div className="mt-3"><Button onClick={() => run(async () => {
        const item = await request<Doc>("/api/client/nda"); setDoc({ ...item, id: data.client.lead_id!, status: "unsigned" }); setDocKind("nda");
      })}>Прочитать NDA</Button></div> : null}
    </article>

    <div className="space-y-3">
      {data.cases.map((item) => <article key={item.id} className="rounded-lg border border-slate-700 bg-slate-800/80 p-4">
        <div className="flex items-start justify-between gap-3"><div><p className="text-xs text-amber-300">{practiceLabels[item.practice] || item.practice}</p><h3 className="mt-1 font-semibold text-white">{item.description.slice(0, 100)}</h3></div><span className="whitespace-nowrap text-xs text-slate-400">{statusLabels[item.status] || item.status}</span></div>
        {item.without_agreement ? <p className="mt-2 text-xs text-slate-400">Работа ведётся без отдельного соглашения.</p> : null}
        <p className="mt-3 text-xs text-slate-400">Документы: {item.documents.length}. Для безопасной загрузки отправьте файл в чат бота по этому обращению.</p>
        <a href={`${EXTERNAL_LINKS.leadBot}?start=case_${item.id}`} className="mt-3 inline-block text-sm font-semibold text-amber-300">Написать по делу</a>
      </article>)}
      {data.cases.length === 0 ? <p className="rounded-lg border border-slate-700 p-4 text-sm text-slate-300">Обращений пока нет.</p> : null}
    </div>

    {data.agreements.length ? <article className="rounded-lg border border-slate-700 bg-slate-800/80 p-4"><div className="flex items-center gap-2"><FileText className="h-5 w-5 text-amber-300"/><h3 className="font-semibold text-white">Договоры</h3></div><div className="mt-3 space-y-3">{data.agreements.map((item) => <div key={item.id} className="border-t border-slate-700 pt-3 first:border-0 first:pt-0"><div className="flex justify-between gap-3"><p className="text-sm text-white">№ {item.number}, редакция {item.revision}</p><span className="text-xs text-slate-400">{statusLabels[item.status] || item.status}</span></div><p className="mt-1 text-sm text-slate-300">{item.subject}</p>{!item.client_details_complete && item.status === "sent" ? <AgreementDetails id={item.id} busy={busy} run={run} /> : <div className="mt-3 flex flex-wrap gap-2"><Button onClick={() => openAgreement(item.id)}>Открыть</Button>{["sent", "viewed"].includes(item.status) ? <Question id={item.id} busy={busy} run={run} /> : null}</div>}</div>)}</div></article> : null}

    {data.acts.length ? <article className="rounded-lg border border-slate-700 bg-slate-800/80 p-4"><div className="flex items-center gap-2"><FileCheck2 className="h-5 w-5 text-emerald-400"/><h3 className="font-semibold text-white">Акты</h3></div><div className="mt-3 space-y-3">{data.acts.map((item) => <div key={item.id} className="border-t border-slate-700 pt-3 first:border-0 first:pt-0"><div className="flex justify-between gap-3"><p className="text-sm text-white">№ {item.number}</p><span className="text-xs text-slate-400">{item.cancelled_at ? "Отозван" : item.paid_at ? "Оплачен" : item.accepted_at ? "Работа принята" : item.objected_at ? "Есть замечания" : statusLabels[item.status] || item.status}</span></div><p className="mt-1 text-sm text-slate-300">{item.description}</p><p className="mt-1 text-sm font-semibold text-white">{money(item.amount_minor)}</p><div className="mt-3"><Button onClick={() => openAct(item.id)} disabled={Boolean(item.cancelled_at)}>Открыть акт</Button></div></div>)}</div></article> : null}

    {doc ? <DocumentPanel kind={docKind!} doc={doc} note={note} setNote={setNote} busy={busy} close={() => setDoc(null)} run={run} /> : null}
  </section>;
}

function AgreementDetails({ id, busy, run }: { id: string; busy: boolean; run: (fn: () => Promise<unknown>) => Promise<void> }) {
  const [kind, setKind] = useState("person");
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault(); const form = new FormData(event.currentTarget); const body = Object.fromEntries(form.entries());
    void run(() => request(`/api/client/agreements/${id}`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ action: "details", client_type: kind, ...body }) }));
  };
  return <form onSubmit={submit} className="mt-3 space-y-2 rounded-lg border border-slate-600 p-3"><p className="text-sm font-semibold text-white">Заполните реквизиты стороны</p><select value={kind} onChange={(e) => setKind(e.target.value)} className="w-full rounded bg-slate-900 p-2 text-sm"><option value="person">Физическое лицо</option><option value="organization">Организация</option></select>{[["full_name","ФИО подписанта"],["contact","Телефон или email"],["address","Адрес"]].map(([name,label]) => <input key={name} name={name} required placeholder={label} className="w-full rounded bg-slate-900 p-2 text-sm"/>)}{kind === "person" ? <input name="identity_document" required placeholder="Паспорт: серия, номер, кем и когда выдан" className="w-full rounded bg-slate-900 p-2 text-sm"/> : [["org_name","Организация"],["inn","ИНН"],["ogrn","ОГРН/ОГРНИП"],["position","Должность"],["authority_basis","Основание полномочий"]].map(([name,label]) => <input key={name} name={name} required placeholder={label} className="w-full rounded bg-slate-900 p-2 text-sm"/>)}<button disabled={busy} className="rounded-lg bg-amber-500 px-3 py-2 text-sm font-semibold text-slate-950">Сохранить и получить редакцию</button></form>;
}

function Question({ id, busy, run }: { id: string; busy: boolean; run: (fn: () => Promise<unknown>) => Promise<void> }) {
  const [open, setOpen] = useState(false); const [text, setText] = useState("");
  if (!open) return <Button tone="quiet" onClick={() => setOpen(true)}><MessageSquareText className="mr-1 inline h-4 w-4"/>Задать вопрос</Button>;
  return <div className="w-full space-y-2"><textarea value={text} onChange={(e) => setText(e.target.value)} maxLength={4000} placeholder="Вопрос по условиям" className="w-full rounded bg-slate-900 p-2 text-sm"/><Button disabled={busy || !text.trim()} onClick={() => run(async () => { await request(`/api/client/agreements/${id}`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ action: "question", text }) }); setText(""); setOpen(false); })}>Отправить вопрос</Button></div>;
}

function DocumentPanel({ kind, doc, note, setNote, busy, close, run }: { kind: "nda" | "agreement" | "act"; doc: Doc; note: string; setNote: (v: string) => void; busy: boolean; close: () => void; run: (fn: () => Promise<unknown>) => Promise<void> }) {
  const signNda = (event: FormEvent<HTMLFormElement>) => { event.preventDefault(); const body = Object.fromEntries(new FormData(event.currentTarget).entries()); void run(async () => { await request("/api/client/nda", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ lead_id: doc.id, document_hash: doc.hash, ...body }) }); close(); }); };
  const act = (action: string, extra = {}) => run(async () => { await request(`/api/client/${kind === "act" ? "acts" : "agreements"}/${doc.id}`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ action, document_hash: doc.document_hash || doc.hash, ...extra }) }); close(); });
  const actOpen = kind === "act" && !doc.cancelled_at;
  const canAccept = actOpen && !doc.accepted_at && !doc.objected_at;
  const canObject = canAccept;
  const canClaimPaid = actOpen && !doc.status.includes("paid");
  return <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-950/95 p-4"><div className="mx-auto max-w-md pb-12"><div className="sticky top-0 flex justify-end bg-slate-950 py-2"><button type="button" onClick={close} title="Закрыть документ" aria-label="Закрыть документ" className="flex h-10 w-10 items-center justify-center rounded-lg border border-slate-600 text-slate-100"><X className="h-5 w-5"/></button></div><pre className="whitespace-pre-wrap font-sans text-sm leading-6 text-slate-100">{doc.text}</pre>{kind === "nda" ? <form onSubmit={signNda} className="mt-5 space-y-2">{[["signer_full_name","ФИО полностью"],["signer_contact","Телефон или email"],["signer_org","Организация, если есть"]].map(([name,label], index) => <input key={name} name={name} required={index < 2} placeholder={label} className="w-full rounded bg-slate-800 p-3 text-sm"/>)}<button disabled={busy} className="w-full rounded-lg bg-amber-500 p-3 font-semibold text-slate-950">Подписать NDA</button></form> : kind === "agreement" ? <div className="mt-5 space-y-3">{doc.status === "viewed" ? <Button disabled={busy} onClick={() => act("sign")}><CheckCircle2 className="mr-1 inline h-4 w-4"/>Подписать договор</Button> : null}{["sent","viewed"].includes(doc.status) ? <><textarea value={note} onChange={(e) => setNote(e.target.value)} maxLength={1000} placeholder="Причина отказа, если решили не принимать условия" className="w-full rounded bg-slate-800 p-3 text-sm"/><Button tone="danger" disabled={busy} onClick={() => act("decline", { reason: note })}>Отклонить условия</Button></> : null}</div> : <div className="mt-5 space-y-3">{canAccept || canClaimPaid ? <div className="flex flex-wrap gap-2">{canAccept ? <Button disabled={busy} onClick={() => act("accept")}>Принять работу</Button> : null}{canClaimPaid ? <Button tone="quiet" disabled={busy} onClick={() => act("claim-paid")}>Сообщить об оплате</Button> : null}</div> : null}{canObject ? <><textarea value={note} onChange={(e) => setNote(e.target.value)} maxLength={4000} placeholder="Замечания к выполненной работе" className="w-full rounded bg-slate-800 p-3 text-sm"/><Button tone="danger" disabled={busy || note.trim().length < 3} onClick={() => act("object", { text: note })}>Отправить замечания</Button></> : null}{doc.payment?.phone ? <p className="text-sm text-slate-300">Перевод по номеру <strong className="text-white">{doc.payment.phone}</strong>{doc.payment.bank ? `, ${doc.payment.bank}` : ""}{doc.payment.recipient ? `, ${doc.payment.recipient}` : ""}.</p> : null}</div>}</div></div>;
}
