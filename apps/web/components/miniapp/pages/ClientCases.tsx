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
  /** supplement — допсоглашение к подписанному договору: реквизиты уже есть, сразу открыть и подписать. */
  kind?: "agreement" | "supplement";
  subject: string; price_text: string; client_details_complete: boolean; hash: string;
  viewed_at?: string | null; signed_at?: string | null;
  messages: { id: string; role: string; text: string; created_at: string }[];
};
type Act = {
  id: string; agreement_id: string; number: string; status: string; description: string;
  amount_minor: number; currency: string; hash: string; viewed_at?: string | null;
  accepted_at?: string | null; objected_at?: string | null; objection_text?: string | null;
  claimed_paid_at?: string | null; paid_at?: string | null; cancelled_at?: string | null;
  /** advance — счёт на предоплату, без приёмки работы. */
  kind?: "act" | "advance";
};
type Summary = {
  client: { lead_id?: string | null; name?: string | null; has_cases: boolean };
  nda: { signed: boolean; signed_at?: string | null; signer_full_name?: string | null; pdn_consent_at?: string | null };
  cases: Case[]; agreements: Agreement[]; acts: Act[];
};
type Doc = {
  id: string; text: string; hash?: string; document_hash?: string; status: string; kind?: string;
  accepted_at?: string | null; objected_at?: string | null; cancelled_at?: string | null;
  payment?: { phone?: string; bank?: string; recipient?: string; qr?: boolean };
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
  // Вне Telegram (личный кабинет на сайте) window.Telegram не определён —
  // initData пуст, и requireClient сам уходит на cookie-fallback. Заголовок
  // всё равно не шлём пустым: меньше шума в запросе, и поведение не зависит
  // от того, как requireClient трактует пустую строку.
  const initData = telegramInitData();
  const response = await fetch(path, {
    ...init,
    headers: { ...(initData ? { "x-telegram-init-data": initData } : {}), ...(init?.headers || {}) },
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

type ClientCasesProps = {
  /** miniapp (по умолчанию) — внутри Telegram Mini App, тёмная тема,
   * узкий экран. site — личный кабинет на сайте (/cabinet): светлая тема
   * даётся оборачивающим .miniapp-light-ops в globals.css, здесь меняется
   * только то, что зависит от отсутствия чата Telegram вокруг. */
  variant?: "miniapp" | "site";
  /** Рендерится вместо списка дел, когда у аккаунта ещё нет ни одного лида
   * (новый посетитель, вошедший через Telegram) — форма «Передать задачу».
   * Render-prop, а не голый ReactNode: форме нужно дёрнуть load() именно
   * этого экземпляра ClientCases после успешной отправки, чтобы кабинет
   * сам обновился и показал только что созданное обращение. */
  emptyState?: (onCreated: () => void) => React.ReactNode;
};

export default function ClientCases({ variant = "miniapp", emptyState }: ClientCasesProps = {}) {
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
  useEffect(() => {
    if (variant === "miniapp") { window.Telegram?.WebApp?.ready?.(); window.Telegram?.WebApp?.expand?.(); }
    void load();
  }, [load, variant]);

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

  if (emptyState && !data.client.lead_id) return <section className="space-y-4">
    <header>
      <p className="text-sm text-slate-400">Личный кабинет</p>
      <h2 className="text-2xl font-semibold text-white">Добро пожаловать</h2>
      <p className="mt-1 text-sm text-slate-300">Вы вошли через Telegram, но пока ни одно обращение не связано с вашим аккаунтом.</p>
    </header>
    {error ? <p className="rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-100">{error}</p> : null}
    {emptyState(() => void load())}
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
      <p className="mt-2 text-sm text-slate-300">{data.nda.signed ? `NDA подписано${data.nda.signer_full_name ? `: ${data.nda.signer_full_name}` : ""}.${data.nda.pdn_consent_at ? " Отдельное согласие на обработку ПД зафиксировано." : ""}` : "Перед документами и договором нужно отдельно дать согласие на обработку ПД и подписать NDA."}</p>
      {!data.nda.signed && data.client.lead_id ? <div className="mt-3"><Button onClick={() => run(async () => {
        const item = await request<Doc>("/api/client/nda"); setDoc({ ...item, id: data.client.lead_id!, status: "unsigned" }); setDocKind("nda");
      })}>Прочитать NDA</Button></div> : null}
    </article>

    <div className="space-y-3">
      {data.cases.map((item) => <article key={item.id} className="rounded-lg border border-slate-700 bg-slate-800/80 p-4">
        <div className="flex items-start justify-between gap-3"><div><p className="text-xs text-amber-300">{practiceLabels[item.practice] || item.practice}</p><h3 className="mt-1 font-semibold text-white">{item.description.slice(0, 100)}</h3></div><span className="whitespace-nowrap text-xs text-slate-400">{statusLabels[item.status] || item.status}</span></div>
        {item.without_agreement ? <p className="mt-2 text-xs text-slate-400">Работа ведётся без отдельного соглашения.</p> : null}
        <CaseDocuments item={item} ndaSigned={data.nda.signed} onUploaded={() => void load()} />
        <a href={`${EXTERNAL_LINKS.leadBot}?start=case_${item.id}`} className="mt-3 inline-block text-sm font-semibold text-amber-300">Написать по делу</a>
      </article>)}
      {data.cases.length === 0 ? <p className="rounded-lg border border-slate-700 p-4 text-sm text-slate-300">Обращений пока нет.</p> : null}
    </div>

    {data.agreements.length ? <article className="rounded-lg border border-slate-700 bg-slate-800/80 p-4"><div className="flex items-center gap-2"><FileText className="h-5 w-5 text-amber-300"/><h3 className="font-semibold text-white">Договоры</h3></div><div className="mt-3 space-y-3">{data.agreements.map((item) => <div key={item.id} className="border-t border-slate-700 pt-3 first:border-0 first:pt-0"><div className="flex justify-between gap-3"><p className="text-sm text-white">{item.kind === "supplement" ? `Допсоглашение № ${item.number}` : `№ ${item.number}, редакция ${item.revision}`}</p><span className="text-xs text-slate-400">{statusLabels[item.status] || item.status}</span></div><p className="mt-1 text-sm text-slate-300">{item.subject}</p>{!item.client_details_complete && item.status === "sent" ? <AgreementDetails id={item.id} busy={busy} run={run} /> : <div className="mt-3 flex flex-wrap gap-2"><Button onClick={() => openAgreement(item.id)}>Открыть</Button>{["sent", "viewed"].includes(item.status) ? <Question id={item.id} busy={busy} run={run} /> : null}</div>}</div>)}</div></article> : null}

    {data.acts.length ? <article className="rounded-lg border border-slate-700 bg-slate-800/80 p-4"><div className="flex items-center gap-2"><FileCheck2 className="h-5 w-5 text-emerald-400"/><h3 className="font-semibold text-white">Акты</h3></div><div className="mt-3 space-y-3">{data.acts.map((item) => <div key={item.id} className="border-t border-slate-700 pt-3 first:border-0 first:pt-0"><div className="flex justify-between gap-3"><p className="text-sm text-white">{item.kind === "advance" ? "Счёт на предоплату" : "Акт"} № {item.number}</p><span className="text-xs text-slate-400">{item.cancelled_at ? "Отозван" : item.paid_at ? "Оплачен" : item.accepted_at ? "Работа принята" : item.objected_at ? "Есть замечания" : statusLabels[item.status] || item.status}</span></div><p className="mt-1 text-sm text-slate-300">{item.description}</p><p className="mt-1 text-sm font-semibold text-white">{money(item.amount_minor)}</p><div className="mt-3"><Button onClick={() => openAct(item.id)} disabled={Boolean(item.cancelled_at)}>{item.kind === "advance" ? "Открыть счёт" : "Открыть акт"}</Button></div></div>)}</div></article> : null}

    {doc ? <DocumentPanel kind={docKind!} doc={doc} note={note} setNote={setNote} busy={busy} close={() => setDoc(null)} run={run} variant={variant} /> : null}
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

function DocumentPanel({ kind, doc, note, setNote, busy, close, run, variant }: { kind: "nda" | "agreement" | "act"; doc: Doc; note: string; setNote: (v: string) => void; busy: boolean; close: () => void; run: (fn: () => Promise<unknown>) => Promise<void>; variant: "miniapp" | "site" }) {
  const act = (action: string, extra = {}) => run(async () => { await request(`/api/client/${kind === "act" ? "acts" : "agreements"}/${doc.id}`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ action, document_hash: doc.document_hash || doc.hash, ...extra }) }); close(); });
  const actOpen = kind === "act" && !doc.cancelled_at;
  // Счёт на предоплату нечего принимать — только оплатить.
  const canAccept = actOpen && doc.kind !== "advance" && !doc.accepted_at && !doc.objected_at;
  const canObject = canAccept;
  const canClaimPaid = actOpen && !doc.status.includes("paid");
  // На сайте панель открывается под фиксированной шапкой (z-50) — здесь
  // нужен z-[60] и отступ сверху вместо max-w-md, рассчитанного на
  // мобильный экран Mini App внутри Telegram.
  const isSite = variant === "site";
  return <div className={`fixed inset-0 ${isSite ? "z-[60]" : "z-50"} overflow-y-auto bg-slate-950/95 p-4`}><div className={`mx-auto pb-12 ${isSite ? "max-w-3xl pt-20" : "max-w-md"}`}><div className="sticky top-0 flex justify-end bg-slate-950 py-2"><button type="button" onClick={close} title="Закрыть документ" aria-label="Закрыть документ" className="flex h-10 w-10 items-center justify-center rounded-lg border border-slate-600 text-slate-100"><X className="h-5 w-5"/></button></div>{kind === "nda" ? <NdaSigningPanel doc={doc} busy={busy} close={close} run={run}/> : <><pre className="whitespace-pre-wrap font-sans text-sm leading-6 text-slate-100">{doc.text}</pre>{kind === "agreement" ? <div className="mt-5 space-y-3">{isSite ? <a href={`/api/client/agreements/${doc.id}/pdf`} className="inline-block text-sm font-semibold text-amber-300 underline">Скачать PDF</a> : null}{doc.status === "viewed" ? <Button disabled={busy} onClick={() => act("sign")}><CheckCircle2 className="mr-1 inline h-4 w-4"/>{doc.kind === "supplement" ? "Подписать допсоглашение" : "Подписать договор"}</Button> : null}{["sent","viewed"].includes(doc.status) ? <><textarea value={note} onChange={(e) => setNote(e.target.value)} maxLength={1000} placeholder="Причина отказа, если решили не принимать условия" className="w-full rounded bg-slate-800 p-3 text-sm"/><Button tone="danger" disabled={busy} onClick={() => act("decline", { reason: note })}>Отклонить условия</Button></> : null}</div> : <div className="mt-5 space-y-3">{canAccept || canClaimPaid ? <div className="flex flex-wrap gap-2">{canAccept ? <Button disabled={busy} onClick={() => act("accept")}>Принять работу</Button> : null}{canClaimPaid ? <Button tone="quiet" disabled={busy} onClick={() => act("claim-paid")}>Сообщить об оплате</Button> : null}</div> : null}{canObject ? <><textarea value={note} onChange={(e) => setNote(e.target.value)} maxLength={4000} placeholder="Замечания к выполненной работе" className="w-full rounded bg-slate-800 p-3 text-sm"/><Button tone="danger" disabled={busy || note.trim().length < 3} onClick={() => act("object", { text: note })}>Отправить замечания</Button></> : null}{kind === "act" && doc.payment?.qr && canClaimPaid ? <PaymentQr actId={doc.id} /> : null}{doc.payment?.phone ? <p className="text-sm text-slate-300">Перевод по номеру <strong className="text-white">{doc.payment.phone}</strong>{doc.payment.bank ? `, ${doc.payment.bank}` : ""}{doc.payment.recipient ? `, ${doc.payment.recipient}` : ""}.</p> : null}</div>}</>}</div></div>;
}

type NdaDetails = {
  signer_full_name: string;
  signer_contact: string;
  signer_identity_document: string;
  signer_org?: string;
};

function NdaSigningPanel({ doc, busy, close, run }: { doc: Doc; busy: boolean; close: () => void; run: (fn: () => Promise<unknown>) => Promise<void> }) {
  const [step, setStep] = useState<"details" | "consent" | "nda">("details");
  const [details, setDetails] = useState<NdaDetails | null>(null);
  const [shown, setShown] = useState<Doc>(doc);
  const [consentId, setConsentId] = useState("");
  const [checked, setChecked] = useState(false);

  const post = <T,>(body: Record<string, unknown>) => request<T>("/api/client/nda", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });

  const previewConsent = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const next = Object.fromEntries(form.entries()) as NdaDetails;
    void run(async () => {
      const preview = await post<Doc>({ action: "consent-preview", ...next });
      setDetails(next); setShown(preview); setChecked(false); setStep("consent");
    });
  };

  const acceptConsent = () => {
    if (!details) return;
    void run(async () => {
      const accepted = await post<{ consent_id: string }>({
        action: "consent-accept", lead_id: doc.id, document_hash: shown.hash,
        pdn_consent_accepted: true, ...details,
      });
      const preview = await post<Doc>({
        action: "nda-preview", lead_id: doc.id, pdn_consent_id: accepted.consent_id,
      });
      setConsentId(accepted.consent_id); setShown(preview); setStep("nda");
    });
  };

  const sign = () => void run(async () => {
    await post({ action: "sign", lead_id: doc.id, pdn_consent_id: consentId, document_hash: shown.hash });
    close();
  });

  return <div>
    <pre className="whitespace-pre-wrap font-sans text-sm leading-6 text-slate-100">{shown.text}</pre>
    {step === "details" ? <form onSubmit={previewConsent} className="mt-5 space-y-2">
      <input name="signer_full_name" required placeholder="ФИО полностью" autoComplete="name" className="w-full rounded bg-slate-800 p-3 text-sm"/>
      <input name="signer_contact" required placeholder="Телефон или email" autoComplete="email" className="w-full rounded bg-slate-800 p-3 text-sm"/>
      <textarea name="signer_identity_document" required maxLength={500} placeholder="Паспорт: серия, номер, кем и когда выдан" autoComplete="off" className="min-h-24 w-full rounded bg-slate-800 p-3 text-sm"/>
      <input name="signer_org" placeholder="Организация, если есть" autoComplete="organization" className="w-full rounded bg-slate-800 p-3 text-sm"/>
      <p className="text-xs leading-5 text-slate-400">Паспортные данные не передаются ИИ, веб-аналитике и рекламным системам.</p>
      <button disabled={busy} className="w-full rounded-lg bg-amber-500 p-3 font-semibold text-slate-950">Перейти к согласию</button>
    </form> : null}
    {step === "consent" ? <div className="mt-5 space-y-3 border-t border-slate-700 pt-4">
      <label className="flex items-start gap-3 text-sm leading-5 text-slate-200"><input type="checkbox" checked={checked} onChange={(event) => setChecked(event.target.checked)} className="mt-1 h-4 w-4"/><span>Я прочитал(а) отдельное согласие и даю согласие на обработку указанных персональных данных. <a href="/privacy" target="_blank" className="text-amber-300 underline">Политика обработки ПД</a></span></label>
      <button type="button" disabled={busy || !checked} onClick={acceptConsent} className="w-full rounded-lg bg-amber-500 p-3 font-semibold text-slate-950 disabled:opacity-50">Даю согласие на обработку ПД</button>
    </div> : null}
    {step === "nda" ? <div className="mt-5 space-y-3 border-t border-slate-700 pt-4"><p className="text-sm leading-5 text-emerald-300">Согласие на обработку ПД зафиксировано отдельно. Теперь можно подписать NDA.</p><button type="button" disabled={busy} onClick={sign} className="w-full rounded-lg bg-amber-500 p-3 font-semibold text-slate-950">Подписать NDA</button></div> : null}
  </div>;
}

/**
 * Платёжный QR акта (ГОСТ Р 56042): приложение банка само заполнит
 * получателя, сумму и назначение. Картинка грузится запросом с тем же
 * подтверждением личности, что и остальной кабинет: у <img src> в мини-аппе
 * Telegram заголовка с initData не было бы.
 */
function PaymentQr({ actId }: { actId: string }) {
  const [url, setUrl] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let revoked: string | null = null;
    const initData = telegramInitData();
    fetch(`/api/client/acts/${actId}/payment-qr`, {
      headers: initData ? { "x-telegram-init-data": initData } : {},
      cache: "no-store",
    })
      .then(async (response) => {
        if (!response.ok) throw new Error(String(response.status));
        revoked = URL.createObjectURL(await response.blob());
        setUrl(revoked);
      })
      .catch(() => setFailed(true));
    return () => {
      if (revoked) URL.revokeObjectURL(revoked);
    };
  }, [actId]);
  if (failed) return null;
  return <div className="rounded-lg border border-slate-700 bg-white p-3 text-center">
    {url ? <img src={url} alt="QR для оплаты" className="mx-auto h-56 w-56" /> : <p className="py-10 text-sm text-slate-500">Готовлю QR…</p>}
    <p className="mt-2 text-xs text-slate-600">Отсканируйте в приложении банка — получатель, сумма и назначение заполнятся сами. На телефоне: сохраните картинку и откройте её в приложении банка. После оплаты нажмите «Сообщить об оплате».</p>
  </div>;
}

/**
 * Документы по делу: что уже передано и загрузка нового. Раньше здесь было
 * «отправьте файл в чат бота по этому обращению» — лишний шаг и путаница,
 * к какому делу файл. Файл уходит юристу в Telegram и сразу виден в деле.
 */
function CaseDocuments({ item, ndaSigned, onUploaded }: { item: Case; ndaSigned: boolean; onUploaded: () => void }) {
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<{ ok: boolean; text: string } | null>(null);
  const upload = async (file: File) => {
    setBusy(true); setNote(null);
    try {
      const form = new FormData();
      form.set("file", file);
      await request(`/api/client/cases/${item.id}/documents`, { method: "POST", body: form });
      setNote({ ok: true, text: `«${file.name}» передан юристу.` });
      onUploaded();
    } catch (e) {
      setNote({ ok: false, text: e instanceof Error ? e.message : "Не удалось загрузить файл" });
    } finally {
      setBusy(false);
    }
  };
  return <div className="mt-3 space-y-2">
    <p className="text-xs text-slate-400">Документы: {item.documents.length}</p>
    {item.documents.length ? <ul className="space-y-1 text-xs text-slate-300">{item.documents.slice(-5).map((doc) => <li key={doc.id} className="truncate">📎 {doc.file_name || "файл"}</li>)}</ul> : null}
    {ndaSigned ? <label className={`inline-flex min-h-10 cursor-pointer items-center rounded-lg border border-slate-600 px-3 py-2 text-sm font-semibold text-slate-100 ${busy ? "opacity-50" : ""}`}>
      <input type="file" className="hidden" disabled={busy} accept=".pdf,.doc,.docx,.rtf,.odt,.txt,.xls,.xlsx,.csv,.ods,.jpg,.jpeg,.png,.heic,.webp,.zip"
        onChange={(e) => { const file = e.target.files?.[0]; e.target.value = ""; if (file) void upload(file); }} />
      {busy ? "Загружаю…" : "Загрузить документ"}
    </label> : <p className="text-xs text-slate-400">Документы принимаются после подписания NDA.</p>}
    {ndaSigned ? <p className="text-xs text-slate-500">PDF, Word, Excel, фото или ZIP до 20 МБ. Файл сразу увидит юрист.</p> : null}
    {note ? <p className={`text-xs ${note.ok ? "text-emerald-400" : "text-red-300"}`}>{note.text}</p> : null}
  </div>;
}
