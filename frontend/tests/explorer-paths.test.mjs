import { test } from "node:test";
import assert from "node:assert/strict";

// Imports the exact module `ProjectExplorer` and `useEditor` use (issue #455).
import {
  isWithin,
  joinPath,
  remapPath,
  relativePath,
  remapTabsAfterRename,
  renamedPath,
  resolveTabsAfterDelete,
} from "../src/lib/explorer-paths.mjs";

function tab(id, filePath, extra = {}) {
  return { id, label: filePath?.split(/[/\\]/).pop() ?? id, filePath, dirty: false, content: "", ...extra };
}

test("relativePath works with POSIX and Windows separators", () => {
  assert.equal(relativePath("/home/me/proj", "/home/me/proj/docs/a.md"), "docs/a.md");
  assert.equal(relativePath("C:\\proj", "C:\\proj\\docs\\a.md"), "docs\\a.md");
  assert.equal(relativePath("C:\\proj\\", "C:\\proj\\a.md"), "a.md");
  assert.equal(relativePath("/proj", "/proj"), ".");
});

test("relativePath does not treat a sibling with a shared prefix as inside", () => {
  assert.equal(relativePath("/proj", "/project-two/a.md"), "/project-two/a.md");
});

test("joinPath and renamedPath keep the folder's separator", () => {
  assert.equal(joinPath("C:\\proj\\docs", "new.md"), "C:\\proj\\docs\\new.md");
  assert.equal(joinPath("/proj/docs/", "new.md"), "/proj/docs/new.md");
  assert.equal(renamedPath("C:\\proj\\docs\\a.md", "b.md"), "C:\\proj\\docs\\b.md");
  assert.equal(renamedPath("/proj/docs", "guides"), "/proj/guides");
});

test("renaming a file updates its tab's path, label and preview folder", () => {
  const tabs = [tab("t1", "/proj/docs/a.md"), tab("t2", "/proj/other.md")];
  const [renamed, untouched] = remapTabsAfterRename(tabs, "/proj/docs/a.md", "/proj/docs/b.md");
  assert.equal(renamed.filePath, "/proj/docs/b.md");
  assert.equal(renamed.label, "b.md");
  assert.equal(renamed.previewBaseDir, "/proj/docs/");
  assert.equal(untouched, tabs[1], "unaffected tabs keep their identity");
});

test("renaming a folder moves every tab inside it, including converted documents", () => {
  const tabs = [
    tab("t1", "C:\\proj\\docs\\a.md"),
    tab("t2", "C:\\proj\\docs\\deep\\b.md"),
    tab("t3", null, { label: "c.md", sourceFilePath: "C:\\proj\\docs\\c.docx" }),
    tab("t4", "C:\\proj\\docs-old\\d.md"),
  ];
  const next = remapTabsAfterRename(tabs, "C:\\proj\\docs", "C:\\proj\\guides");
  assert.equal(next[0].filePath, "C:\\proj\\guides\\a.md");
  assert.equal(next[1].filePath, "C:\\proj\\guides\\deep\\b.md");
  assert.equal(next[2].filePath, null);
  assert.equal(next[2].sourceFilePath, "C:\\proj\\guides\\c.docx");
  assert.equal(next[2].previewBaseDir, "C:\\proj\\guides\\");
  assert.equal(next[3], tabs[3], "a folder sharing the name prefix is not inside");
});

test("deleting closes clean tabs and detaches tabs with unsaved changes", () => {
  const tabs = [
    tab("clean", "/proj/docs/a.md"),
    tab("dirty", "/proj/docs/b.md", { dirty: true }),
    tab("elsewhere", "/proj/c.md"),
  ];
  const { tabs: next, closeIds } = resolveTabsAfterDelete(tabs, "/proj/docs");
  assert.deepEqual(closeIds, ["clean"]);
  const dirty = next.find((t) => t.id === "dirty");
  // Keeping the path would make Save silently recreate the deleted file.
  assert.equal(dirty.filePath, null);
  assert.equal(dirty.dirty, true);
  assert.equal(next.find((t) => t.id === "elsewhere"), tabs[2]);
});

test("isWithin and remapPath follow an entry that was moved", () => {
  assert.equal(isWithin("C:\\proj\\docs\\a.md", "C:\\proj\\docs"), true);
  assert.equal(isWithin("C:\\proj\\docs", "C:\\proj\\docs"), true);
  assert.equal(isWithin("C:\\proj\\docs-old", "C:\\proj\\docs"), false);
  assert.equal(remapPath("/proj/docs/deep", "/proj/docs", "/proj/archive/docs"), "/proj/archive/docs/deep");
  assert.equal(remapPath("/proj/other", "/proj/docs", "/proj/archive/docs"), "/proj/other");
});

test("moving a file into another folder updates its open tab", () => {
  const tabs = [tab("t1", "/proj/docs/a.md", { dirty: true })];
  const [moved] = remapTabsAfterRename(tabs, "/proj/docs/a.md", "/proj/archive/a.md");
  assert.equal(moved.filePath, "/proj/archive/a.md");
  assert.equal(moved.previewBaseDir, "/proj/archive/");
  assert.equal(moved.dirty, true, "unsaved edits are kept");
});
