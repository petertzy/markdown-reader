import { test } from "node:test";
import assert from "node:assert/strict";
import { projectTabsAreFresh } from "../src/lib/project-work-guard.mjs";

test("project review is invalidated when an open document changes", () => {
  const snapshot = [{ id: "one", filePath: "/project/one.md", content: "One" }];
  assert.equal(projectTabsAreFresh(snapshot, [{ ...snapshot[0] }]), true);
  assert.equal(projectTabsAreFresh(snapshot, [{ ...snapshot[0], content: "User edit" }]), false);
});
