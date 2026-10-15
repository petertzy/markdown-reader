import { test } from "node:test";
import assert from "node:assert/strict";
import {
  createProjectWorkRunGuard,
  projectTabsAreFresh,
  taskMatchesProject,
} from "../src/lib/project-work-guard.mjs";

test("project review is invalidated when an open document changes", () => {
  const snapshot = [{ id: "one", filePath: "/project/one.md", content: "One" }];
  assert.equal(projectTabsAreFresh(snapshot, [{ ...snapshot[0] }]), true);
  assert.equal(projectTabsAreFresh(snapshot, [{ ...snapshot[0], content: "User edit" }]), false);
});

test("a proposal from project A cannot be applied under project B with unchanged tabs", () => {
  const tabs = [{ id: "one", filePath: "/project-a/one.md", content: "One" }];
  assert.equal(projectTabsAreFresh(tabs, [{ ...tabs[0] }]), true);
  assert.equal(taskMatchesProject("/project-a", "/project-b"), false);
});

test("a late project A completion cannot replace a newer project B task", () => {
  const guard = createProjectWorkRunGuard();
  const projectARun = guard.begin();
  guard.invalidate(); // Discard A while its request is still pending.
  const projectBRun = guard.begin();

  assert.equal(guard.isCurrent(projectBRun), true);
  assert.equal(guard.isCurrent(projectARun), false);
});
