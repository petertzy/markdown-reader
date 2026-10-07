import { test } from "node:test";
import assert from "node:assert/strict";

// Exercises the real tokenizer the chat panel imports, so this suite fails if
// the "where does a bare URL end" rule regresses. The scan used to live inline
// in AIPanel.tsx, which is TypeScript; CI runs the frontend suite on Node 20,
// which cannot import `.ts`, so it now lives in `src/lib/inline-markdown.mjs`
// (same pattern as http-timeout.mjs / preview-base-dir.mjs).
import { bareUrlSpan, tokenizeInlineMarkdown } from "../src/lib/inline-markdown.mjs";

// Only the hrefs, which is what a reader ends up clicking.
function hrefs(text) {
  return tokenizeInlineMarkdown(text)
    .filter((token) => token.type === "link")
    .map((token) => token.href);
}

test("a bare URL stops before the sentence punctuation that follows it", () => {
  // The bug: the /g match ran to the next space, so the trailing "." became part
  // of the href and the link pointed at a URL that does not exist.
  assert.deepEqual(hrefs("See https://example.com."), ["https://example.com"]);
  assert.deepEqual(hrefs("Ping https://example.com, then stop"), ["https://example.com"]);
  assert.deepEqual(hrefs("Ends https://example.com!"), ["https://example.com"]);
  assert.deepEqual(hrefs("Semi https://example.com; colon https://ex.com:"), [
    "https://example.com",
    "https://ex.com",
  ]);
});

test("the punctuation left out of the href is kept as text, not dropped", () => {
  // Guards the whole point of the fix: trimming the href must not swallow the
  // character, or the sentence silently loses its full stop.
  assert.deepEqual(tokenizeInlineMarkdown("See https://example.com."), [
    { type: "text", value: "See " },
    { type: "link", label: "https://example.com", href: "https://example.com" },
    { type: "text", value: "." },
  ]);
  assert.deepEqual(tokenizeInlineMarkdown("Ellipsis https://example.com/a... tail"), [
    { type: "text", value: "Ellipsis " },
    { type: "link", label: "https://example.com/a", href: "https://example.com/a" },
    { type: "text", value: "..." },
    { type: "text", value: " tail" },
  ]);
});

test("a closing bracket is judged by balance, not by position", () => {
  // RFC 3986 allows brackets in a path, so "/a(b)" must survive untouched...
  assert.equal(bareUrlSpan("https://example.com/a(b)"), "https://example.com/a(b)");
  assert.deepEqual(hrefs("Docs at https://example.com/a(b) here"), [
    "https://example.com/a(b)",
  ]);
  // ...while a ")" that closes the surrounding sentence is prose.
  assert.equal(bareUrlSpan("https://example.com/a)"), "https://example.com/a");
  assert.deepEqual(tokenizeInlineMarkdown("(see https://example.com/a)"), [
    { type: "text", value: "(see " },
    { type: "link", label: "https://example.com/a", href: "https://example.com/a" },
    { type: "text", value: ")" },
  ]);
  // The same rule covers square and curly brackets.
  assert.equal(bareUrlSpan("https://example.com/a]"), "https://example.com/a");
  assert.equal(bareUrlSpan("https://example.com/a}"), "https://example.com/a");
  assert.equal(bareUrlSpan("https://example.com/a[b]"), "https://example.com/a[b]");
  assert.equal(bareUrlSpan("https://example.com/a{b}"), "https://example.com/a{b}");
});

test("a closing quote around a URL belongs to the prose", () => {
  assert.deepEqual(hrefs('Quote "https://example.com" done'), ["https://example.com"]);
});

test("an authored markdown link keeps its label and its URL verbatim", () => {
  // The `)` already delimited this one, so it never needed trimming.
  assert.deepEqual(tokenizeInlineMarkdown("Ref [RFC](https://example.com) ok"), [
    { type: "text", value: "Ref " },
    { type: "link", label: "RFC", href: "https://example.com" },
    { type: "text", value: " ok" },
  ]);
});

test("emphasis and code spans are unchanged", () => {
  assert.deepEqual(tokenizeInlineMarkdown("**bold** and `code`"), [
    { type: "strong", value: "bold" },
    { type: "text", value: " and " },
    { type: "code", value: "code" },
  ]);
  assert.deepEqual(tokenizeInlineMarkdown("Mixed **bold** and `code` and https://a.io."), [
    { type: "text", value: "Mixed " },
    { type: "strong", value: "bold" },
    { type: "text", value: " and " },
    { type: "code", value: "code" },
    { type: "text", value: " and " },
    { type: "link", label: "https://a.io", href: "https://a.io" },
    { type: "text", value: "." },
  ]);
});

test("no URL is empty, and none ends in prose punctuation", () => {
  // A degenerate match must never turn into an empty or mangled href.
  for (const url of ["https://.", "https://,", "https://?!.", "https://a.io/"]) {
    assert.ok(bareUrlSpan(url).startsWith("https://"), `${url} lost its scheme`);
  }
  for (const text of [
    "See https://example.com.",
    "Ends https://a.io!",
    "Mid https://a.io/path#frag, next",
    "(https://a.io/x)",
  ]) {
    for (const href of hrefs(text)) {
      assert.notEqual(href, "", "href must never be empty");
      assert.doesNotMatch(href, /[?!.,:;*_~'"]$/, `href kept trailing prose: ${href}`);
    }
  }
});

test("every character in the trailing set is trimmed, and only at the end", () => {
  // Each entry is a deliberate decision, so pin all of them rather than
  // leaving any character of the set to chance.
  for (const char of "?!.,:;*_~'\"") {
    assert.equal(
      bareUrlSpan(`https://example.com${char}`),
      "https://example.com",
      `trailing ${char} was not trimmed`
    );
    // The same character inside the URL is legitimate and must survive.
    assert.equal(
      bareUrlSpan(`https://example.com${char}x`),
      `https://example.com${char}x`,
      `${char} was trimmed from the middle of a URL`
    );
  }
});

test("a port and interior punctuation stay part of the URL", () => {
  assert.equal(bareUrlSpan("https://example.com:8080/v1"), "https://example.com:8080/v1");
  assert.equal(
    bareUrlSpan("https://example.com/search?q=a,b;c"),
    "https://example.com/search?q=a,b;c"
  );
  assert.equal(bareUrlSpan("https://example.com/"), "https://example.com/");
});

test("the two trims alternate, so neither can hide behind the other", () => {
  // "https://a.io)," needs the "," removed before the stray ")" is visible;
  // trimming brackets first would leave that ")" inside the href.
  assert.equal(bareUrlSpan("https://a.io),"), "https://a.io");
  assert.equal(bareUrlSpan("https://a.io)."), "https://a.io");
  assert.equal(bareUrlSpan("https://a.io.,)"), "https://a.io");
  assert.equal(bareUrlSpan('https://a.io!"'), "https://a.io");
});

test("successive scans of the same text agree", () => {
  // The pattern is compiled per call rather than shared at module level, so no
  // lastIndex can survive from one scan into the next.
  const text = "First https://a.io. Then https://b.io!";
  const first = tokenizeInlineMarkdown(text);
  assert.deepEqual(tokenizeInlineMarkdown(text), first);
  assert.deepEqual(hrefs(text), ["https://a.io", "https://b.io"]);
  assert.deepEqual(tokenizeInlineMarkdown(""), []);
  assert.deepEqual(tokenizeInlineMarkdown(text), first);
});

test("a bare URL stops before emphasis or code that follows it", () => {
  // The old `[^\s]+` class swallowed the opening marker, so "https://a.io**now"
  // became the href and the leftover "**" leaked back into the prose. The URL
  // must end at the marker so the strong/code span is parsed on its own.
  assert.deepEqual(tokenizeInlineMarkdown("See https://a.io**now** then"), [
    { type: "text", value: "See " },
    { type: "link", label: "https://a.io", href: "https://a.io" },
    { type: "strong", value: "now" },
    { type: "text", value: " then" },
  ]);
  assert.deepEqual(tokenizeInlineMarkdown("Run https://a.io`x=1` now"), [
    { type: "text", value: "Run " },
    { type: "link", label: "https://a.io", href: "https://a.io" },
    { type: "code", value: "x=1" },
    { type: "text", value: " now" },
  ]);
});

test("an authored link keeps balanced parentheses inside its URL", () => {
  // A "(film)"-style path is part of the URL; only the paren that closes the
  // markdown link may terminate it. Before the fix the path was cut at the
  // first ")" and that closing paren leaked into the prose.
  assert.deepEqual(hrefs("[Foo](https://en.wikipedia.org/wiki/Foo_(film))"), [
    "https://en.wikipedia.org/wiki/Foo_(film)",
  ]);
  assert.deepEqual(
    tokenizeInlineMarkdown("Ref [Foo](https://en.wikipedia.org/wiki/Foo_(film)) ok"),
    [
      { type: "text", value: "Ref " },
      { type: "link", label: "Foo", href: "https://en.wikipedia.org/wiki/Foo_(film)" },
      { type: "text", value: " ok" },
    ]
  );
  // A URL without parens is untouched, and a stray ")" that closes a bracket
  // the URL opened itself still belongs to the href.
  assert.deepEqual(hrefs("[RFC](https://example.com) here"), ["https://example.com"]);
  assert.deepEqual(hrefs("[A](https://a.io/a(b)c) end"), ["https://a.io/a(b)c"]);
});