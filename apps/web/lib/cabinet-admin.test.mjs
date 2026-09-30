import assert from "node:assert/strict";
import { test } from "node:test";

import { isStaffTelegramId, staffTelegramIds } from "./cabinet-admin.ts";

test("администратор и юристы — из тех же переменных, что пускают в рабочее место", () => {
  const staff = staffTelegramIds({ ADMIN_TELEGRAM_ID: "111", LAWYER_TELEGRAM_IDS: "222, 333" });
  assert.deepEqual(staff, [111, 222, 333]);
  assert.equal(isStaffTelegramId(111, staff), true);
  assert.equal(isStaffTelegramId(333, staff), true);
});

test("клиент, пустой Telegram и пустой список — не администратор", () => {
  const staff = staffTelegramIds({ ADMIN_TELEGRAM_ID: "111" });
  assert.equal(isStaffTelegramId(444, staff), false);
  assert.equal(isStaffTelegramId(null, staff), false);
  assert.equal(isStaffTelegramId(undefined, staff), false);
  assert.equal(isStaffTelegramId(111, staffTelegramIds({})), false);
});
