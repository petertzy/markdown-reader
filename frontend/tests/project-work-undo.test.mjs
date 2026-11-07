import { test } from "node:test";
import assert from "node:assert/strict";
import { captureProjectWorkUndo, revertProjectWork } from "../src/lib/project-work-undo.mjs";

const tab = (id, filePath, content, dirty = false) => ({ id, filePath, content, dirty });

test("undo restores edited tabs and closes tabs that Project Work opened", () => {
  const before = [tab("a", "/p/a.md", "A")];
  const changes = [
    { file_path: "/p/a.md", content: "A by AI" },
    { file_path: "/p/new.md", content: "New by AI" },
  ];
  const record = captureProjectWorkUndo(before, changes);
  const afterApply = [tab("a", "/p/a.md", "A by AI", true), tab("n", "/p/new.md", "New by AI", true)];

  const { tabs, reverted, skipped } = revertProjectWork(afterApply, record);

  assert.deepEqual(tabs, [tab("a", "/p/a.md", "A", false)]);
  assert.deepEqual(reverted, ["/p/a.md", "/p/new.md"]);
  assert.deepEqual(skipped, []);
});

test("undo never discards edits the user made after accepting", () => {
  const record = captureProjectWorkUndo([tab("a", "/p/a.md", "A")], [{ file_path: "/p/a.md", content: "AI" }]);
  const edited = [tab("a", "/p/a.md", "AI plus user typing", true)];

  const { tabs, skipped } = revertProjectWork(edited, record);

  assert.equal(tabs, edited);
  assert.deepEqual(skipped, ["/p/a.md"]);
});

test("a saved AI result stays dirty after undo, and a saved new file is kept", () => {
  const record = captureProjectWorkUndo(
    [tab("a", "/p/a.md", "A")],
    [{ file_path: "/p/a.md", content: "AI" }, { file_path: "/p/new.md", content: "New" }]
  );
  const saved = [tab("a", "/p/a.md", "AI", false), tab("n", "/p/new.md", "New", false)];

  const { tabs, skipped } = revertProjectWork(saved, record);

  assert.deepEqual(tabs, [tab("a", "/p/a.md", "A", true), tab("n", "/p/new.md", "New", false)]);
  assert.deepEqual(skipped, ["/p/new.md"]);
});
