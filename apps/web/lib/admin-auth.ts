import { createHash, createHmac, randomBytes } from "node:crypto";

import bcrypt from "bcryptjs";

const BCRYPT_ROUNDS = 12;
const TOTP_STEP_SECONDS = 30;
const TOTP_DIGITS = 6;

function normalizeBase32(value: string): string {
  return value.toUpperCase().replace(/[^A-Z2-7]/g, "");
}

function decodeBase32(value: string): Buffer {
  const normalized = normalizeBase32(value);
  if (!normalized) {
    throw new Error("TOTP secret is empty");
  }

  let bits = "";
  for (const char of normalized) {
    const code =
      char >= "A" && char <= "Z"
        ? char.charCodeAt(0) - 65
        : char.charCodeAt(0) - 24;
    if (code < 0 || code > 31) {
      throw new Error("TOTP secret contains invalid base32 characters");
    }
    bits += code.toString(2).padStart(5, "0");
  }

  const bytes: number[] = [];
  for (let index = 0; index + 8 <= bits.length; index += 8) {
    bytes.push(Number.parseInt(bits.slice(index, index + 8), 2));
  }
  return Buffer.from(bytes);
}

function formatHotp(secret: Buffer, counter: number): string {
  const counterBuffer = Buffer.alloc(8);
  counterBuffer.writeUInt32BE(Math.floor(counter / 2 ** 32), 0);
  counterBuffer.writeUInt32BE(counter >>> 0, 4);
  const digest = createHmac("sha1", secret).update(counterBuffer).digest();
  const offset = digest[digest.length - 1] & 0x0f;
  const code =
    ((digest[offset] & 0x7f) << 24)
    | ((digest[offset + 1] & 0xff) << 16)
    | ((digest[offset + 2] & 0xff) << 8)
    | (digest[offset + 3] & 0xff);
  return String(code % 10 ** TOTP_DIGITS).padStart(TOTP_DIGITS, "0");
}

export function generateTotpCode(secret: string, nowMs: number = Date.now()): string {
  const decodedSecret = decodeBase32(secret);
  const currentCounter = Math.floor(nowMs / 1000 / TOTP_STEP_SECONDS);
  return formatHotp(decodedSecret, currentCounter);
}

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

export function normalizeTotpCode(value: string): string {
  return value.replace(/\D/g, "").slice(0, TOTP_DIGITS);
}

export function verifyTotpCode(
  secret: string,
  code: string,
  nowMs: number = Date.now(),
  windowSteps: number = 1,
): boolean {
  const normalizedCode = normalizeTotpCode(code);
  if (normalizedCode.length !== TOTP_DIGITS) {
    return false;
  }

  const decodedSecret = decodeBase32(secret);
  const currentCounter = Math.floor(nowMs / 1000 / TOTP_STEP_SECONDS);
  for (let offset = -windowSteps; offset <= windowSteps; offset += 1) {
    if (formatHotp(decodedSecret, currentCounter + offset) === normalizedCode) {
      return true;
    }
  }
  return false;
}

export function generateTotpSecret(length: number = 20): string {
  const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
  const raw = randomBytes(length);
  let result = "";
  for (const byte of raw) {
    result += alphabet[byte % alphabet.length];
  }
  return result;
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
