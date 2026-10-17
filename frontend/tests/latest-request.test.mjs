import { test } from "node:test";
import assert from "node:assert/strict";

// Exercises the real guard the app imports. `useEditor.ts` is TypeScript and CI
// runs the frontend suite on Node 20, which cannot import `.ts`, so the guard
// lives in `src/lib/latest-request.mjs` (same pattern as http-timeout.mjs).
import { createLatestRequestGuard } from "../src/lib/latest-request.mjs";

// Models what the preview pane does: apply a response only if it belongs to the
// newest request. `render` resolves in the order given, deliberately out of
// request order.
function createPreview(renderOrder) {
  const guard = createLatestRequestGuard();
  let html = "";
  const pending = [];

  return {
    request(content) {
      const token = guard.issue();
      pending.push({ content, token });
    },
    settle() {
      for (const index of renderOrder) {
        const { content, token } = pending[index];
        if (guard.isCurrent(token)) html = content;
      }
    },
    get html() {
      return html;
    },
  };
}

test("nothing is in flight before the first request", () => {
  const guard = createLatestRequestGuard();
  assert.equal(guard.current(), null);
  assert.equal(guard.isCurrent(1), false, "a stale token is never accepted");
});

test("the only outstanding request is accepted", () => {
  const guard = createLatestRequestGuard();
  const token = guard.issue();
  assert.ok(guard.isCurrent(token));
});

test("tokens increase monotonically", () => {
  const guard = createLatestRequestGuard();
  assert.deepEqual([guard.issue(), guard.issue(), guard.issue()], [1, 2, 3]);
});

test("a slow earlier render cannot overwrite a newer one", () => {
  // Paste a large document (slow render), then undo it (fast render). The
  // response for the *first* request lands last and must be discarded.
  const preview = createPreview([1, 0]);
  preview.request("pasted 500KB of text");
  preview.request("reverted small text");
  preview.settle();
  assert.equal(preview.html, "reverted small text");
});

test("an in-order arrival still applies the newest response", () => {
  const preview = createPreview([0, 1]);
  preview.request("first");
  preview.request("second");
  preview.settle();
  assert.equal(preview.html, "second");
});

test("three rapid keystrokes leave only the last one applied", () => {
  const preview = createPreview([2, 0, 1]);
  preview.request("a");
  preview.request("ab");
  preview.request("abc");
  preview.settle();
  assert.equal(preview.html, "abc");
});

test("supersede retires pending work without issuing a new request", () => {
  const guard = createLatestRequestGuard();
  const token = guard.issue();
  guard.supersede();
  assert.equal(guard.isCurrent(token), false, "the pending response is now stale");
  // A supersede must still leave the channel usable.
  const next = guard.issue();
  assert.ok(guard.isCurrent(next));
  assert.notEqual(next, token);
});

test("supersede blocks a document's render from repainting into a new tab", () => {
  // Ctrl+N clears the preview synchronously, but the previous document's render
  // may still be in flight and would otherwise repaint the empty tab.
  const guard = createLatestRequestGuard();
  const staleRender = guard.issue();
  guard.supersede(); // newTab() clears previewHtml
  assert.equal(guard.isCurrent(staleRender), false);
});

test("two guards are independent", () => {
  // Preview and word count are separate channels; a word count must not
  // invalidate a render or vice versa.
  const preview = createLatestRequestGuard();
  const counts = createLatestRequestGuard();
  const renderToken = preview.issue();
  counts.issue();
  assert.ok(preview.isCurrent(renderToken), "an unrelated channel must not supersede");
});

test("several supersedes in a row keep rejecting earlier tokens", () => {
  const guard = createLatestRequestGuard();
  const token = guard.issue();
  guard.supersede();
  guard.supersede();
  guard.supersede();
  assert.equal(guard.isCurrent(token), false);
});
