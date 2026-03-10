import { randomBytes } from "node:crypto";
import { createInterface } from "node:readline/promises";
import { stdin as input, stdout as output } from "node:process";

import { generateTotpSecret, hashAdminPassword } from "../lib/admin-auth.ts";

async function resolvePassword() {
  const cliPassword = process.argv[2];
  if (cliPassword) {
    return cliPassword;
  }

  const envPassword = process.env.ADMIN_PANEL_PASSWORD_INPUT;
  if (envPassword) {
    return envPassword;
  }

  const rl = createInterface({ input, output });
  try {
    const password = await rl.question("Admin password: ");
    return password;
  } finally {
    rl.close();
  }
}

const password = await resolvePassword();
if (!password) {
  console.error("Password is required. Pass it as an argument or set ADMIN_PANEL_PASSWORD_INPUT.");
  process.exit(1);
}

const issuer = process.env.ADMIN_PANEL_TOTP_ISSUER || "Legal AI PRO";
const accountName = process.env.ADMIN_PANEL_TOTP_ACCOUNT || "admin";
const totpSecret = generateTotpSecret();
const sessionSecret = randomBytes(32).toString("base64url");
const passwordHash = hashAdminPassword(password);
const otpAuthUrl = `otpauth://totp/${encodeURIComponent(issuer)}:${encodeURIComponent(accountName)}?secret=${totpSecret}&issuer=${encodeURIComponent(issuer)}&algorithm=SHA1&digits=6&period=30`;

console.log(`ADMIN_PANEL_PASSWORD_HASH=${passwordHash}`);
console.log(`ADMIN_PANEL_TOTP_SECRET=${totpSecret}`);
console.log(`ADMIN_PANEL_SESSION_SECRET=${sessionSecret}`);
console.log(`ADMIN_PANEL_TOTP_OTPURL=${otpAuthUrl}`);
