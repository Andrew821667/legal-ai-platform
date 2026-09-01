import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), "../../..");

const publicCopyFiles = [
  "apps/web/app/page.tsx",
  "apps/web/app/about/page.tsx",
  "apps/web/app/services/page.tsx",
  "apps/web/app/solutions/page.tsx",
  "apps/web/app/for-business/page.tsx",
  "apps/web/app/legal-help/page.tsx",
  "apps/web/components/PlatformMap.tsx",
  "apps/web/components/Footer.tsx",
  "apps/web/components/PracticeIntersection.tsx",
  "apps/web/components/ProductProof.tsx",
  "apps/web/components/WebAssistant.tsx",
  "apps/web/components/miniapp/pages/MiniAppHomeClient.tsx",
  "apps/web/components/miniapp/pages/MiniAppSolutionsClient.tsx",
  "apps/web/lib/platformParts.ts",
  "apps/web/lib/faqData.ts",
  "apps/web/lib/serviceDetailData.ts",
  "apps/lead-bot/lead_bot/run.py",
  "apps/lead-bot/legacy/content.py",
  "apps/lead-bot/legacy/platform_map.py",
];

const staleFormulas = [
  "это не отдельный бот, а полноценная платформа",
  "две практики. одна ключевая специализация",
  "две практики, одно ключевое пересечение",
  "ключевое пересечение практик",
  "на их стыке",
  "мы не только разрабатываем",
];

test("key public copy does not restore stale marketing formulas", () => {
  const hits = [];

  for (const relativePath of publicCopyFiles) {
    const source = readFileSync(resolve(repoRoot, relativePath), "utf8").toLowerCase();
    for (const formula of staleFormulas) {
      if (source.includes(formula)) {
        hits.push(`${relativePath}: ${formula}`);
      }
    }
  }

  assert.deepEqual(hits, []);
});
