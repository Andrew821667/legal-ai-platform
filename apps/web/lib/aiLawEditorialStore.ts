import { existsSync, mkdirSync, readFileSync, renameSync, writeFileSync } from "node:fs";
import path from "node:path";

import {
  aiLawCommentSeeds,
  type AiLawComment,
  type AiLawCommentStatus,
  type AiLawEffectiveStage,
  type AiLawSection,
} from "./aiLawComments.ts";

type EditorialStore = {
  version: 1;
  comments: AiLawComment[];
};

const MAX_COMMENTS = 200;
const STATUSES = new Set<AiLawCommentStatus>(["draft", "verified", "published", "archived"]);
const SLUG_RE = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {};
}

function text(value: unknown, max = 12_000): string {
  return String(value ?? "").trim().slice(0, max);
}

function lines(value: unknown, maxItems = 100): string[] {
  return Array.isArray(value)
    ? value.map((item) => text(item, 4_000)).filter(Boolean).slice(0, maxItems)
    : [];
}

function pairs(value: unknown, left: string, right: string): Array<Record<string, string>> {
  if (!Array.isArray(value)) return [];
  return value.slice(0, 100).map((item) => {
    const row = asRecord(item);
    return { [left]: text(row[left]), [right]: text(row[right]) };
  });
}

function stages(value: unknown): AiLawEffectiveStage[] {
  if (!Array.isArray(value)) return [];
  return value.slice(0, 20).map((item) => {
    const row = asRecord(item);
    return {
      date: text(row.date, 10),
      label: text(row.label, 120),
      title: text(row.title, 240),
      legalBasis: text(row.legalBasis, 1_000),
      summary: text(row.summary, 4_000),
      points: lines(row.points, 30),
    };
  });
}

function sections(value: unknown): AiLawSection[] {
  if (!Array.isArray(value)) return [];
  return value.slice(0, 30).map((item) => {
    const row = asRecord(item);
    const bullets = lines(row.bullets, 50);
    return {
      heading: text(row.heading, 240),
      paragraphs: lines(row.paragraphs, 30),
      ...(bullets.length ? { bullets } : {}),
    };
  });
}

export function normalizeAiLawComment(value: unknown): AiLawComment {
  const row = asRecord(value);
  const source = asRecord(row.officialSource);
  const rawStatus = text(row.status, 20) as AiLawCommentStatus;
  return {
    slug: text(row.slug, 120).toLowerCase(),
    status: STATUSES.has(rawStatus) ? rawStatus : "draft",
    lawNumber: text(row.lawNumber, 80),
    lawDate: text(row.lawDate, 10),
    lawTitle: text(row.lawTitle, 1_000),
    title: text(row.title, 300),
    seoTitle: text(row.seoTitle, 180),
    description: text(row.description, 600),
    summary: text(row.summary, 4_000),
    publishedAt: text(row.publishedAt, 10),
    reviewedAt: text(row.reviewedAt, 10),
    readingTime: text(row.readingTime, 40),
    audience: lines(row.audience, 50),
    keywords: lines(row.keywords, 50),
    officialSource: {
      title: text(source.title, 240),
      url: text(source.url, 2_000),
      publicationId: text(source.publicationId, 160),
    },
    effectiveStages: stages(row.effectiveStages),
    sections: sections(row.sections),
    misconceptions: pairs(row.misconceptions, "claim", "reality") as AiLawComment["misconceptions"],
    actions: pairs(row.actions, "title", "description") as AiLawComment["actions"],
    watchItems: lines(row.watchItems, 100),
  };
}

function isDate(value: string): boolean {
  if (!DATE_RE.test(value)) return false;
  const parsed = new Date(`${value}T00:00:00.000Z`);
  return !Number.isNaN(parsed.getTime()) && parsed.toISOString().startsWith(value);
}

function isOfficialSource(value: string): boolean {
  try {
    const url = new URL(value);
    return url.protocol === "https:" && (
      url.hostname === "publication.pravo.gov.ru"
      || url.hostname === "pravo.gov.ru"
    );
  } catch {
    return false;
  }
}

export function validateAiLawComment(comment: AiLawComment): string[] {
  const errors: string[] = [];
  if (!SLUG_RE.test(comment.slug)) {
    errors.push("Slug должен содержать только латиницу, цифры и дефисы");
  }
  if (!comment.title) errors.push("Укажите заголовок материала");
  if (comment.status === "draft" || comment.status === "archived") return errors;

  const required: Array<[string, string]> = [
    [comment.lawNumber, "Укажите номер нормативного акта"],
    [comment.lawTitle, "Укажите полное название нормативного акта"],
    [comment.seoTitle, "Укажите SEO-заголовок"],
    [comment.description, "Укажите SEO-описание"],
    [comment.summary, "Укажите краткое резюме"],
    [comment.readingTime, "Укажите время чтения"],
    [comment.officialSource.title, "Укажите название официального источника"],
    [comment.officialSource.publicationId, "Укажите номер официального опубликования"],
  ];
  for (const [value, message] of required) {
    if (!value) errors.push(message);
  }

  if (!isDate(comment.lawDate)) errors.push("Дата нормативного акта указана неверно");
  if (!isDate(comment.reviewedAt)) errors.push("Дата юридической проверки указана неверно");
  if (comment.reviewedAt && comment.lawDate && comment.reviewedAt < comment.lawDate) {
    errors.push("Дата проверки не может быть раньше даты нормативного акта");
  }
  if (!isOfficialSource(comment.officialSource.url)) {
    errors.push("Для публикации нужна HTTPS-ссылка на pravo.gov.ru или publication.pravo.gov.ru");
  }
  if (!comment.audience.length) errors.push("Укажите, кого касается нормативный акт");
  if (!comment.keywords.length) errors.push("Добавьте поисковые ключевые фразы");
  if (!comment.effectiveStages.length) errors.push("Добавьте хотя бы один этап вступления в силу");
  if (!comment.sections.length) errors.push("Добавьте хотя бы один содержательный раздел");
  if (!comment.actions.length) errors.push("Добавьте хотя бы одно практическое действие");

  const stageDates: string[] = [];
  for (const [idx, stage] of comment.effectiveStages.entries()) {
    const label = `Этап ${idx + 1}`;
    if (!isDate(stage.date)) errors.push(`${label}: неверная дата`);
    if (!stage.label || !stage.title || !stage.legalBasis || !stage.summary) {
      errors.push(`${label}: заполните название, основание и описание`);
    }
    if (!stage.points.length) errors.push(`${label}: добавьте конкретные положения`);
    stageDates.push(stage.date);
  }
  if (stageDates.join("|") !== [...stageDates].sort().join("|")) {
    errors.push("Этапы вступления в силу должны идти по датам");
  }

  for (const [idx, section] of comment.sections.entries()) {
    if (!section.heading || !section.paragraphs.length) {
      errors.push(`Раздел ${idx + 1}: заполните заголовок и текст`);
    }
  }
  for (const [idx, action] of comment.actions.entries()) {
    if (!action.title || !action.description) {
      errors.push(`Действие ${idx + 1}: заполните заголовок и описание`);
    }
  }
  for (const [idx, item] of comment.misconceptions.entries()) {
    if (!item.claim || !item.reality) {
      errors.push(`Миф ${idx + 1}: заполните утверждение и корректное объяснение`);
    }
  }

  if (comment.status === "published") {
    if (!isDate(comment.publishedAt)) errors.push("Дата публикации указана неверно");
    if (comment.publishedAt && comment.lawDate && comment.publishedAt < comment.lawDate) {
      errors.push("Дата публикации не может быть раньше даты нормативного акта");
    }
  }
  return [...new Set(errors)];
}

function getStorePath(): string {
  const configured = text(process.env.AI_LAW_EDITORIAL_STORE_PATH, 2_000);
  if (configured) return configured;
  const securityStore = text(process.env.ADMIN_SECURITY_STORE_PATH, 2_000);
  if (securityStore) return path.join(path.dirname(securityStore), "ai-law-comments.json");
  return path.join(process.cwd(), ".data", "ai-law-comments.json");
}

function loadStoredComments(): AiLawComment[] {
  const filePath = getStorePath();
  if (!existsSync(filePath)) return [];
  try {
    const parsed = JSON.parse(readFileSync(filePath, "utf-8")) as Partial<EditorialStore>;
    if (!Array.isArray(parsed.comments)) return [];
    return parsed.comments.slice(0, MAX_COMMENTS).map(normalizeAiLawComment);
  } catch (error) {
    console.error("[ai-law-editorial] Failed to read editorial store", error);
    return [];
  }
}

function saveStoredComments(comments: AiLawComment[]): void {
  const filePath = getStorePath();
  mkdirSync(path.dirname(filePath), { recursive: true, mode: 0o700 });
  const tmpPath = `${filePath}.tmp`;
  const store: EditorialStore = { version: 1, comments };
  writeFileSync(tmpPath, `${JSON.stringify(store, null, 2)}\n`, { mode: 0o600 });
  renameSync(tmpPath, filePath);
}

export function listAiLawEditorialComments(): AiLawComment[] {
  const merged = new Map(aiLawCommentSeeds.map((comment) => [comment.slug, structuredClone(comment)]));
  for (const comment of loadStoredComments()) merged.set(comment.slug, comment);
  return [...merged.values()].sort((left, right) => {
    const leftDate = left.reviewedAt || left.publishedAt || left.lawDate;
    const rightDate = right.reviewedAt || right.publishedAt || right.lawDate;
    return rightDate.localeCompare(leftDate) || left.title.localeCompare(right.title, "ru");
  });
}

export function listPublishedAiLawComments(): AiLawComment[] {
  return listAiLawEditorialComments().filter((comment) => comment.status === "published");
}

export function getPublishedAiLawComment(slug: string): AiLawComment | undefined {
  return listPublishedAiLawComments().find((comment) => comment.slug === slug);
}

export function getAiLawEditorialComment(slug: string): AiLawComment | undefined {
  return listAiLawEditorialComments().find((comment) => comment.slug === slug);
}

export function getAiLawReviewedAt(comments = listPublishedAiLawComments()): string {
  return comments.reduce(
    (latest, comment) => comment.reviewedAt > latest ? comment.reviewedAt : latest,
    "1970-01-01",
  );
}

export function saveAiLawComment(value: unknown): AiLawComment {
  const comment = normalizeAiLawComment(value);
  const errors = validateAiLawComment(comment);
  if (errors.length) throw new Error(errors.join("\n"));

  const comments = loadStoredComments();
  const idx = comments.findIndex((item) => item.slug === comment.slug);
  if (idx === -1 && comments.length >= MAX_COMMENTS) {
    throw new Error(`Редакционное хранилище ограничено ${MAX_COMMENTS} материалами`);
  }
  if (idx === -1) comments.push(comment);
  else comments[idx] = comment;
  saveStoredComments(comments);
  return comment;
}
