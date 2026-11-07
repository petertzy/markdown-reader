import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { isProjectTranslationFinished } from "../src/lib/project-translation-refresh.mjs";

// A translation writes its output folders on the backend. The project tree only
// reloads when the refresh token changes, so the UI must be told when a running
// translation reaches a terminal state.

const read = (path) => readFileSync(fileURLToPath(new URL(path, import.meta.url)), "utf8");
const task = (id, status) => ({ id, status });

test("project tree refreshes when a running translation finishes", () => {
  assert.equal(isProjectTranslationFinished(task("a", "running"), task("a", "completed")), true);
  assert.equal(isProjectTranslationFinished(task("a", "running"), task("a", "cancelled")), true);
  assert.equal(isProjectTranslationFinished(task("a", "running"), task("a", "failed")), true);
  assert.equal(isProjectTranslationFinished(task("a", "running"), task("a", "running")), false);
  assert.equal(isProjectTranslationFinished(null, task("a", "completed")), false);
  assert.equal(isProjectTranslationFinished(task("a", "completed"), task("a", "completed")), false);
  assert.equal(isProjectTranslationFinished(task("a", "running"), null), false);
});

test("a terminal status from a different task never counts as this task finishing", () => {
  assert.equal(isProjectTranslationFinished(task("a", "running"), task("b", "completed")), false);
  assert.equal(isProjectTranslationFinished(task("b", "running"), task("a", "completed")), false);
});

test("translation hook resets on project change and fires the callback on transitions", () => {
  const hook = read("../src/hooks/useProjectTranslation.ts");
  assert.match(hook, /useProjectTranslation\(projectRoot: string \| null, onFinished\?: \(\) => void\)/);
  assert.match(hook, /onFinishedRef\.current = onFinished;/);
  assert.match(hook, /\}, \[projectRoot\]\);/);
  assert.match(hook, /previousTaskRef\.current = null;\s*setTask\(null\);/);
  assert.match(
    hook,
    /if \(isProjectTranslationFinished\(previousTaskRef\.current, task\)\) onFinishedRef\.current\?\.\(\);\s*previousTaskRef\.current = task;\s*\}, \[task\]\);/,
  );
});

test("translation state is held at page level and passed through AIPanel", () => {
  const page = read("../src/app/page.tsx");
  const panel = read("../src/components/AIPanel.tsx");
  const review = read("../src/components/ProjectTranslationReview.tsx");

  assert.match(
    page,
    /useProjectTranslation\(project\.projectRoot, \(\) => setProjectRefreshToken\(\(token\) => token \+ 1\)\)/,
  );
  assert.match(page, /projectTranslation=\{projectTranslation\}/);
  assert.match(panel, /projectTranslation: ReturnType<typeof useProjectTranslation>;/);
  assert.match(panel, /<ProjectTranslationReview[^>]*translation=\{projectTranslation\}/);
  assert.match(review, /translation: ReturnType<typeof useProjectTranslation>;/);
});
