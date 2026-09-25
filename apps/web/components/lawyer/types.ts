export type TodayItem = {
  agreement_id?: string;
  intake_id?: string;
  lead_id?: string | null;
  client: string;
  subject?: string;
  price_text?: string;
  question?: string;
  contact?: string | null;
  reason?: string | null;
  status?: string;
  legal_area?: string;
  practice?: string;
  category?: string | null;
  urgency?: string;
  days_waiting?: number | null;
  expires_at?: string | null;
  deadline_at?: string | null;
  days_left?: number | null;
  /** Ваш собственный аккаунт — проверка системы, а не клиент. */
  is_test?: boolean;
  // «Не доставлено в Telegram»
  delivery_id?: string;
  kind_label?: string;
  text?: string;
  delivery_status?: "pending" | "failed" | "sent";
  retryable?: boolean;
  attempts?: number;
  last_error?: string | null;
  // Акты: «клиент сообщил об оплате», «не оплачен в срок»
  act_id?: string;
  act_number?: string;
  amount_minor?: number;
  claimed_paid_at?: string | null;
  sent_at?: string | null;
  last_reminded_at?: string | null;
};

export type TodaySection = {
  key: string;
  title: string;
  hint: string;
  items: TodayItem[];
};

/** Связь ядра с Telegram по последней проверке; null — проверки ещё не было. */
export type TelegramHealth = {
  ok: boolean;
  checked_at: string | null;
  failing_since: string | null;
  last_error: string | null;
};

export type Today = { generated_at: string; sections: TodaySection[]; telegram?: TelegramHealth | null };

export type ClientRow = {
  lead_id: string;
  name: string;
  stage: string;
  waiting_on_me: boolean;
  contact: string | null;
  company: string | null;
  intakes: number;
  last_intake_at: string | null;
  nda_signed: boolean;
  agreement_status: string | null;
  legal_areas: string[];
  practices: string[];
  amount_minor: number | null;
  is_test?: boolean;
};

export type Clarification = { question: string; answer: string; created_at: string | null };

export type IntakeDocumentRow = {
  document_id: string;
  file_name: string | null;
  file_size: number | null;
  mime_type: string | null;
  nda_signed_at_upload: boolean;
  created_at: string | null;
};

/** Роль ЭТОГО обращения относительно связанного — не тип связи как таковой. */
export type IntakeLinkRow = {
  link_id: string;
  role: "main" | "subordinate" | "joint";
  note: string | null;
  linked_lead_id: string;
  linked_client: string;
  // Какое именно дело того клиента: у клиента может быть несколько обращений.
  linked_intake_id: string;
  linked_practice: string;
  linked_legal_area: string;
  linked_category: string | null;
  linked_intake_created_at: string | null;
  created_at: string | null;
};

export type IntakeCard = {
  intake_id: string;
  created_at: string | null;
  legal_area: string;
  practice: "legal" | "engineering" | "hybrid";
  category: string | null;
  client_type: string;
  urgency: string;
  deadline: string | null;
  deadline_at: string | null;
  region: string | null;
  status: string;
  conflict_status: string;
  description: string;
  internal_note: string | null;
  without_agreement: boolean;
  outreach_sent_at: string | null;
  outreach_blocked_reason: string | null;
  clarifications: Clarification[];
  documents: IntakeDocumentRow[];
  links: IntakeLinkRow[];
};

export type AgreementMessage = { role: string; text: string; created_at: string | null };

export type AgreementCard = {
  agreement_id: string;
  intake_id: string | null;
  /** Заполнено у допсоглашения — ссылка на договор, к которому оно. */
  parent_agreement_id?: string | null;
  number: string;
  status: string;
  template_kind: "legal_services" | "software_development" | "legal_automation";
  revision: number;
  subject: string;
  price_text: string;
  amount_minor: number | null;
  currency: string;
  payment_terms: string | null;
  scope_text: string | null;
  exclusions_text: string | null;
  schedule_text: string | null;
  expires_at: string | null;
  client_snapshot: Record<string, unknown>;
  signer_position: string | null;
  authority_basis: string | null;
  document_version: string | null;
  created_at: string | null;
  sent_at: string | null;
  viewed_at: string | null;
  /** Когда бот сам напомнил клиенту о неподписанном документе. */
  last_reminded_at?: string | null;
  signed_at: string | null;
  declined_at: string | null;
  decline_reason: string | null;
  messages: AgreementMessage[];
  acts: WorkAct[];
  /** Допсоглашения к этому договору, новые первыми. */
  supplements?: AgreementCard[];
};

export type WorkAct = {
  act_id: string;
  act_number: string;
  status: "draft" | "sent" | "claimed_paid" | "paid";
  description_text: string;
  amount_minor: number;
  currency: string;
  created_at: string | null;
  sent_at: string | null;
  claimed_paid_at: string | null;
  paid_at: string | null;
  paid_note: string | null;
  /** Когда последний раз напоминали клиенту об оплате. */
  last_reminded_at?: string | null;
};

export type ClientCard = {
  lead_id: string;
  name: string;
  /** Не пусто — клиент в архиве: в карточке «Восстановить» и «Удалить навсегда». */
  archived_at?: string | null;
  /** Ваш собственный аккаунт Telegram — тест, не в деньгах и счётчиках. */
  is_test?: boolean;
  stage: string;
  contact: string | null;
  company: string | null;
  email: string | null;
  phone: string | null;
  telegram_user_id: number | null;
  source: string | null;
  created_at: string | null;
  nda: {
    signed_at: string | null;
    signer_full_name: string | null;
    signer_contact: string | null;
    signer_org: string | null;
    identity_document_provided: boolean;
    pdn_consent_at: string | null;
    pdn_consent_version: string | null;
    pdn_consent_id: string | null;
    version: string;
    nda_id: string;
  } | null;
  intakes: IntakeCard[];
  agreements: AgreementCard[];
};

export type MoneyBucket = { count: number; minor: number; unpriced: number };

export type FinanceAgreement = {
  agreement_id: string;
  lead_id: string | null;
  client: string;
  number: string;
  subject: string;
  status: string;
  amount_minor: number | null;
  price_text: string;
  signed_at: string | null;
  sent_at: string | null;
  created_at: string | null;
};

export type Finance = {
  generated_at: string;
  currency: string;
  month_from: string;
  signed_this_month: MoneyBucket;
  signed_prev_month: MoneyBucket;
  signed_total: MoneyBucket;
  average_signed_minor: number | null;
  in_pipeline: MoneyBucket;
  drafts: MoneyBucket;
  declined_this_month: MoneyBucket;
  acts?: FinanceActs;
  agreements: FinanceAgreement[];
};

export type ActBucket = { count: number; minor: number };

export type OpenAct = {
  act_id: string;
  act_number: string;
  lead_id: string | null;
  client: string;
  amount_minor: number;
  status: "sent" | "claimed_paid";
  sent_at: string | null;
  claimed_paid_at: string | null;
  last_reminded_at: string | null;
  days_since_sent: number | null;
  overdue: boolean;
};

/** Деньги по актам: подписанный договор — ещё не деньги, оплаченный акт — деньги. */
export type FinanceActs = {
  payment_days: number;
  issued_this_month: ActBucket;
  paid_this_month: ActBucket;
  receivable: ActBucket;
  overdue: ActBucket;
  claimed: ActBucket;
  open: OpenAct[];
};

export type HistoryItem = {
  at: string | null;
  action: string;
  target_type: string;
  target_id: string | null;
  agreement_number: string | null;
  details: Record<string, unknown>;
};

export type History = { lead_id: string; items: HistoryItem[] };

/** Клиент в архиве и то, что пропадёт вместе с ним при удалении. */
export type ArchiveRow = {
  lead_id: string;
  name: string;
  contact: string | null;
  company: string | null;
  created_at: string | null;
  archived_at: string | null;
  intakes: number;
  agreements: number;
  signed_agreements: number;
  acts: number;
  nda_signed: boolean;
  is_test?: boolean;
};
