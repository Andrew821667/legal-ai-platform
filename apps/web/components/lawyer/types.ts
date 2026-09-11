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
  urgency?: string;
  days_waiting?: number | null;
  expires_at?: string | null;
  deadline_at?: string | null;
  days_left?: number | null;
};

export type TodaySection = {
  key: string;
  title: string;
  hint: string;
  items: TodayItem[];
};

export type Today = { generated_at: string; sections: TodaySection[] };

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
};

export type Clarification = { question: string; answer: string; created_at: string | null };

export type IntakeDocumentRow = {
  file_name: string | null;
  file_size: number | null;
  mime_type: string | null;
  nda_signed_at_upload: boolean;
  created_at: string | null;
};

export type IntakeCard = {
  intake_id: string;
  created_at: string | null;
  legal_area: string;
  client_type: string;
  urgency: string;
  deadline: string | null;
  deadline_at: string | null;
  region: string | null;
  status: string;
  conflict_status: string;
  description: string;
  internal_note: string | null;
  outreach_sent_at: string | null;
  outreach_blocked_reason: string | null;
  clarifications: Clarification[];
  documents: IntakeDocumentRow[];
};

export type AgreementMessage = { role: string; text: string; created_at: string | null };

export type AgreementCard = {
  agreement_id: string;
  intake_id: string | null;
  number: string;
  status: string;
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
  signed_at: string | null;
  declined_at: string | null;
  decline_reason: string | null;
  messages: AgreementMessage[];
};

export type ClientCard = {
  lead_id: string;
  name: string;
  stage: string;
  contact: string | null;
  company: string | null;
  telegram_user_id: number | null;
  source: string | null;
  created_at: string | null;
  nda: {
    signed_at: string | null;
    signer_full_name: string | null;
    signer_contact: string | null;
    signer_org: string | null;
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
  agreements: FinanceAgreement[];
};
