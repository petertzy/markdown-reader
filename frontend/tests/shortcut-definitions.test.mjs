import { test } from "node:test";
import assert from "node:assert/strict";
import { bindingSignature, buildDefaultShortcuts } from "../src/lib/shortcut-definitions.mjs";

// The real shortcut table, as the app builds it on each platform.
const PLATFORMS = { macOS: buildDefaultShortcuts(true), "Windows/Linux": buildDefaultShortcuts(false) };

// Chords the OS or basic text editing owns; an app shortcut must never take them.
const RESERVED = {
  macOS: ["meta+q", "meta+h", "meta+m", "meta+c", "meta+v", "meta+a", "meta+x", "meta+tab", "meta+,"],
  "Windows/Linux": ["ctrl+c", "ctrl+v", "ctrl+a", "ctrl+x", "alt+f4"],
};

for (const [platform, shortcuts] of Object.entries(PLATFORMS)) {
  test(`${platform}: no two shortcuts share a key chord`, () => {
    const owner = new Map();
    for (const shortcut of shortcuts) {
      for (const binding of shortcut.bindings) {
        const signature = bindingSignature(binding);
        assert.ok(!owner.has(signature), `${signature} is bound to both ${owner.get(signature)} and ${shortcut.id}`);
        owner.set(signature, shortcut.id);
      }
    }
  });

  test(`${platform}: no shortcut takes a system or clipboard chord`, () => {
    for (const shortcut of shortcuts) {
      for (const binding of shortcut.bindings) {
        assert.ok(!RESERVED[platform].includes(bindingSignature(binding)), `${shortcut.id} uses ${bindingSignature(binding)}`);
      }
    }
  });

  test(`${platform}: every shortcut has a unique id, a label and a binding`, () => {
    assert.equal(new Set(shortcuts.map((shortcut) => shortcut.id)).size, shortcuts.length);
    for (const shortcut of shortcuts) {
      assert.ok(shortcut.label, `${shortcut.id} has no label`);
      assert.ok(shortcut.bindings.length > 0, `${shortcut.id} has no binding`);
    }
  });
}

test("both platforms expose the same commands", () => {
  const ids = (shortcuts) => shortcuts.map((shortcut) => shortcut.id);
  assert.deepEqual(ids(PLATFORMS.macOS), ids(PLATFORMS["Windows/Linux"]));
});

test("categories are contiguous, so the Shortcuts menu groups them cleanly", () => {
  const categories = PLATFORMS.macOS.map((shortcut) => shortcut.id.split(".")[0]);
  const runs = categories.filter((category, index) => category !== categories[index - 1]);
  assert.equal(new Set(runs).size, runs.length, `categories split apart: ${runs.join(", ")}`);
});

test("primary modifier is Cmd on macOS and Ctrl elsewhere", () => {
  const save = (shortcuts) => shortcuts.find((shortcut) => shortcut.id === "file.save").bindings[0];
  assert.equal(bindingSignature(save(PLATFORMS.macOS)), "meta+s");
  assert.equal(bindingSignature(save(PLATFORMS["Windows/Linux"])), "ctrl+s");
});
