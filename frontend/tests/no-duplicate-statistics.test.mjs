import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { test } from "node:test";

const frontendRoot = new URL("../src/", import.meta.url);
const page = readFileSync(new URL("app/page.tsx", frontendRoot), "utf8");
const obsoleteStatsPath = new URL("components/DocumentStats.tsx", frontendRoot);

test("the editor renders document statistics exactly once through the status bar", () => {
  assert.equal(existsSync(obsoleteStatsPath), false, "obsolete DocumentStats component still exists");
  assert.doesNotMatch(page, /DocumentStats/, "editor page still references obsolete statistics renderer");
  assert.equal((page.match(/<StatusBar\b/g) ?? []).length, 1, "editor must render exactly one status bar");
  assert.match(page, /<StatusBar\s+stats=\{editor\.wordCount\}/, "status bar must receive editor statistics");
});
