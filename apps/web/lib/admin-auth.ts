import { createHash } from "node:crypto";

import bcrypt from "bcryptjs";

const BCRYPT_ROUNDS = 12;

export function hashAdminSecret(value: string): string {
  return createHash("sha256").update(value).digest("hex");
}

export function hashAdminPassword(password: string): string {
  return bcrypt.hashSync(password.normalize("NFKC"), BCRYPT_ROUNDS);
}

export function verifyAdminPassword(password: string, storedHash: string): boolean {
  if (!storedHash) {
    return false;
  }
  return bcrypt.compareSync(password.normalize("NFKC"), storedHash);
}

export function resolveAdminClientContext(headers: Headers): {
  clientKey: string;
  ipHash: string;
  userAgentHash: string;
} {
  const forwarded = String(headers.get("x-forwarded-for") || "")
    .split(",")[0]
    ?.trim()
    .slice(0, 120);
  const real = String(headers.get("x-real-ip") || "").trim().slice(0, 120);
  const ip = forwarded || real || "unknown";
  const userAgent = String(headers.get("user-agent") || "unknown").slice(0, 500);
  const ipHash = hashAdminSecret(`ip:${ip}`);
  const userAgentHash = hashAdminSecret(`ua:${userAgent}`);
  return {
    clientKey: hashAdminSecret(`${ipHash}:${userAgentHash}`),
    ipHash,
    userAgentHash,
  };
}
