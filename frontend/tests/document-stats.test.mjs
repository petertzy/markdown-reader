import { test, mock } from "node:test";
import assert from "node:assert/strict";

const wordCountMock = mock.fn(async () => ({
  words: 10, chars_with_spaces: 50, chars_without_spaces: 45,
  heading_count: 2, reading_time: "1 min read",
}));

mock.module("../src/lib/api.ts", {
  namedExports: { Markdown: { wordCount: wordCountMock } },
});

const { fetchDocumentStats } = await import("../src/lib/documentStats.ts");

test("calls shared Markdown API with content", async () => {
  wordCountMock.mock.resetCalls();
  const res = await fetchDocumentStats("# Hi\n\ntext");
  assert.equal(wordCountMock.mock.callCount(), 1);
  assert.equal(res.heading_count, 2);
});

test("empty content returns zeros without calling API", async () => {
  wordCountMock.mock.resetCalls();
  const res = await fetchDocumentStats("   ");
  assert.equal(wordCountMock.mock.callCount(), 0);
  assert.equal(res.heading_count, 0);
  assert.equal(res.reading_time, "< 1 min read");
});