import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import {
  createFinishTracker,
  createProjectScope,
  isProjectTranslationFinished,
} from "../src/lib/project-translation-refresh.mjs";

// A translation writes its output folders on the backend. The project tree only
// reloads when the refresh token changes, so the UI must be told when a running
// translation reaches a terminal state, and must ignore responses that belong to
// a project the user has already left.

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

test("only explicitly terminal statuses count as finishing", () => {
  assert.equal(isProjectTranslationFinished(task("a", "running"), task("a", "paused")), false);
  assert.equal(isProjectTranslationFinished(task("a", "running"), task("a", "queued")), false);
});

test("a terminal status from a different task never counts as this task finishing", () => {
  assert.equal(isProjectTranslationFinished(task("a", "running"), task("b", "completed")), false);
  assert.equal(isProjectTranslationFinished(task("b", "running"), task("a", "completed")), false);
});

test("a finished translation reports exactly one refresh across repeated snapshots", () => {
  const tracker = createFinishTracker();
  const snapshots = [
    task("a", "running"),
    task("a", "running"),
    task("a", "completed"),
    task("a", "completed"),
    task("a", "completed"),
  ];
  const fired = snapshots.map((snapshot) => tracker.observe(snapshot));
  assert.deepEqual(fired, [false, false, true, false, false]);
});

test("each translation task reports its own completion once", () => {
  const tracker = createFinishTracker();
  const fired = [
    tracker.observe(task("a", "running")),
    tracker.observe(task("a", "completed")),
    tracker.observe(task("b", "running")),
    tracker.observe(task("b", "failed")),
  ];
  assert.deepEqual(fired, [false, true, false, true]);
});

test("resetting the tracker on project change drops the previous task's transition", () => {
  const tracker = createFinishTracker();
  tracker.observe(task("a", "running"));
  tracker.reset();
  assert.equal(tracker.observe(task("a", "completed")), false);
});

test("a request started in one project is stale once the project changes", () => {
  const scope = createProjectScope();
  scope.setRoot("/projects/a");
  const token = scope.token();
  assert.equal(scope.isCurrent(token), true);

  scope.setRoot("/projects/b");
  assert.equal(scope.isCurrent(token), false);
});

test("returning to the original project does not revive requests from before the switch", () => {
  const scope = createProjectScope();
  scope.setRoot("/projects/a");
  const token = scope.token();

  scope.setRoot("/projects/b");
  scope.setRoot("/projects/a");
  assert.equal(scope.isCurrent(token), false);
  assert.equal(scope.isCurrent(scope.token()), true);
});

test("setting the same root again keeps in-flight requests current", () => {
  const scope = createProjectScope();
  scope.setRoot("/projects/a");
  const token = scope.token();
  scope.setRoot("/projects/a");
  assert.equal(scope.isCurrent(token), true);
});

test("translation hook guards every async write and reports completions once", () => {
  const hook = read("../src/hooks/useProjectTranslation.ts");
  assert.match(hook, /useProjectTranslation\(projectRoot: string \| null, onFinished\?: \(\) => void\)/);
  assert.match(hook, /onFinishedRef\.current = onFinished;/);
  assert.match(hook, /scopeRef\.current\.setRoot\(projectRoot\);/);
  assert.match(hook, /\}, \[projectRoot\]\);/);
  assert.match(hook, /trackerRef\.current\.reset\(\);\s*setTask\(null\);/);
  assert.match(hook, /if \(trackerRef\.current\.observe\(task\)\) onFinishedRef\.current\?\.\(\);/);

  // No async result may reach state without passing the project-scope check.
  assert.doesNotMatch(hook, /setTask\(await /);
  assert.doesNotMatch(hook, /\n\s*setError\(reason/);
  assert.match(hook, /if \(scope\.isCurrent\(token\)\) setTask\(next\);/);
  assert.match(hook, /if \(scope\.isCurrent\(token\)\) setError\(/);
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
