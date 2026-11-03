import { test } from "node:test";
import assert from "node:assert/strict";

// Mirrors the pure paste-classification logic in FocusModePane.tsx. The
// frontend test runner executes on Node 20 and cannot import TypeScript.
function isMarkdownContent(text) {
  const value = text.trim();
  if (!value) return false;

  return [
    /^#{1,6}\s+\S/m,
    /^```[^\n]*\n[\s\S]*?\n```\s*$/m,
    /^\s*>\s+\S/m,
    /^\s*(?:[-+*]|\d+\.)\s+\S/m,
    /^\s*([-*_]\s*){3,}$/m,
    /\*\*[^*\n]+\*\*|__[^_\n]+__/,
    /(?<!\*)\*[^*\n]+\*(?!\*)|(?<!_)_[^_\n]+_(?!_)/,
    /`[^`\n]+`/,
    /!?\[[^\]\n]+\]\([^\s)]+(?:\s+["'][^"']*["'])?\)/,
    /^\s*\|.+\|\s*\n\s*\|\s*:?-{3,}:?\s*\|/m,
  ].some((pattern) => pattern.test(value));
}

function shouldParseMarkdownPaste(plainText, html) {
  if (!isMarkdownContent(plainText)) return false;
  const hasRichStructure = /<(?:p|h[1-6]|ul|ol|li|table|thead|tbody|tr|td|th|blockquote|pre|code|strong|em|a)\b/i.test(html);
  return !hasRichStructure;
}

test("recognizes standalone Markdown constructs", () => {
  for (const value of [
    "# Heading",
    "**bold text**",
    "- one item",
    "[example](https://example.com)",
    "`inline code`",
    "```js\nconst value = 1\n```",
    "| Name | Value |\n| --- | --- |\n| A | B |",
    "  - parent\n    - child",
  ]) {
    assert.equal(isMarkdownContent(value), true, value);
  }
});

test("parses Markdown when the clipboard has no HTML or only a wrapper", () => {
  assert.equal(shouldParseMarkdownPaste("# Heading", ""), true);
  assert.equal(shouldParseMarkdownPaste("**bold**", "<div><span>**bold**</span></div>"), true);
});

test("preserves semantic rich HTML even when its text looks like Markdown", () => {
  assert.equal(shouldParseMarkdownPaste("**bold**", "<p><strong>bold</strong></p>"), false);
  assert.equal(shouldParseMarkdownPaste("- item", "<ul><li>item</li></ul>"), false);
  assert.equal(shouldParseMarkdownPaste("# Heading", "<h1>Heading</h1>"), false);
});

test("does not treat ordinary text as Markdown", () => {
  for (const value of ["C# is great", "version 1.2.3", "a * b", "plain text"]) {
    assert.equal(isMarkdownContent(value), false, value);
    assert.equal(shouldParseMarkdownPaste(value, ""), false, value);
  }
});
