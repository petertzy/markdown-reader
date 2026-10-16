import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import vm from "node:vm";
import ts from "typescript";
import { splitTextIntoTranslationUnits } from "../src/lib/translation-units.mjs";

const source = readFileSync(new URL("../src/hooks/useAIChat.ts", import.meta.url), "utf8");
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
}).outputText;
const plain = (value) => JSON.parse(JSON.stringify(value));

function deferred() {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

// Run the complete hook with persistent slots and explicit render snapshots.
// API responses are controlled; sentence splitting uses the production module.
function harness(fixtures = {}) {
  const slots = [];
  let cursor = 0;
  let current;
  const react = {
    useState(initial) {
      const index = cursor++;
      if (!slots[index]) {
        const slot = { value: typeof initial === "function" ? initial() : initial };
        slot.set = (next) => { slot.value = typeof next === "function" ? next(slot.value) : next; };
        slots[index] = slot;
      }
      return [slots[index].value, slots[index].set];
    },
    useRef(initial) {
      const index = cursor++;
      if (!slots[index]) slots[index] = { current: initial };
      return slots[index];
    },
    useCallback(callback, dependencies) {
      const index = cursor++;
      const previous = slots[index];
      if (!previous || dependencies.some((value, i) => !Object.is(value, previous.dependencies[i]))) {
        slots[index] = { callback, dependencies };
      }
      return slots[index].callback;
    },
  };
  const calls = { chat: [], translate: [], sentences: [] };
  const AI = {
    chat: async (payload) => {
      calls.chat.push(plain(payload));
      return fixtures.chat ? fixtures.chat(payload) : {
        assistant_message: `Reply: ${payload.message}`,
        proposed_action: { type: "none", content: "", reason: "" },
        used_provider: "fixture",
        used_sources: [],
      };
    },
    translate: (...args) => {
      calls.translate.push(args);
      if (!fixtures.translate) throw new Error("Unexpected translation request");
      return fixtures.translate(...args);
    },
    translateSentenceBatch: (...args) => {
      calls.sentences.push(args);
      if (!fixtures.sentences) throw new Error("Unexpected sentence request");
      return fixtures.sentences(...args);
    },
  };
  const exports = {};
  vm.runInNewContext(compiled, {
    exports, AbortController, Error,
    require(name) {
      if (name === "react") return react;
      if (name === "@/lib/api") return { AI };
      if (name === "@/lib/translation-units.mjs") return { splitTextIntoTranslationUnits };
      throw new Error(`Unexpected hook dependency: ${name}`);
    },
  }, { filename: "useAIChat.ts", timeout: 1000 });
  const runner = {
    calls,
    render() { cursor = 0; current = exports.useAIChat(); return current; },
    get current() { return current; },
    messages: () => plain(current.messages),
    conversation: () => Array.from(current.messages, ({ role, content }) => ({ role, content })),
  };
  runner.render();
  return runner;
}

async function seedConversation(h) {
  await h.current.sendMessage("Keep this conversation.", "Document.");
  h.render();
  return h.messages();
}

function sentenceDocument(count = 2) {
  const units = Array.from({ length: count }, (_, i) => `${String.fromCharCode(65 + i).repeat(1600)}.`);
  const content = units.join("\n\n");
  assert.deepEqual(splitTextIntoTranslationUnits(content), units);
  return { content, units };
}

function rejectOnAbort(signal) {
  return new Promise((_, reject) => {
    signal.addEventListener("abort", () => reject(new Error("Synthetic cancellation")), { once: true });
  });
}

test("should preserve direct conversations mentioning translation and assistant edit metadata", async () => {
  const action = { type: "replace_selection", content: "Edited selection.", reason: "direct request" };
  const sources = [{ rel_path: "note.md", title: "Note", section: "Example" }];
  const h = harness({ chat: async () => ({ assistant_message: "Direct answer.", proposed_action: action, used_provider: "fixture", used_sources: sources }) });
  await h.current.sendMessage("Translate this in our conversation.", "Document.", "Selection.", { useKnowledgeBase: true, knowledgeTopK: 3 });
  h.render();
  assert.deepEqual(h.conversation(), [
    { role: "user", content: "Translate this in our conversation." },
    { role: "assistant", content: "Direct answer." },
  ]);
  assert.deepEqual(h.current.messages[1].proposedAction, action);
  assert.deepEqual(h.current.messages[1].sources, sources);
  assert.equal(h.current.messages[1].provider, "fixture");
  assert.deepEqual(h.calls.chat[0], {
    message: "Translate this in our conversation.", document_text: "Document.", selected_text: "Selection.", chat_history: [], use_knowledge_base: true, knowledge_top_k: 3,
  });
  await h.current.sendMessage("Follow up.");
  h.render();
  assert.deepEqual(h.calls.chat[1].chat_history, h.conversation().slice(0, 2));
  assert.equal(h.current.loading, false);
  assert.equal(h.current.error, null);
  await h.current.sendMessage("  ");
  h.render();
  assert.equal(h.calls.chat.length, 2);
  h.current.clearHistory(); h.render();
  assert.deepEqual(h.messages(), []);
});

test("should leave direct history unchanged while full translation is pending and after success", async () => {
  const gate = deferred();
  const h = harness({ translate: () => gate.promise });
  const before = await seedConversation(h);
  const pending = h.current.translate("Article.", "auto", "Chinese");
  h.render();
  const pendingMessages = h.messages();
  const pendingLoading = h.current.loading;
  gate.resolve({ translated: "Translated article." });
  assert.equal(await pending, "Translated article.");
  h.render();
  assert.equal(pendingLoading, true);
  assert.equal(h.current.loading, false);
  assert.equal(h.current.error, null);
  assert.deepEqual(h.calls.translate, [["Article.", "auto", "Chinese"]]);
  assert.deepEqual(pendingMessages, before);
  assert.deepEqual(h.messages(), before);
});

test("should retain direct history and existing null/error semantics when full translation fails", async () => {
  const h = harness({ translate: async () => { throw new Error("Synthetic translation failure"); } });
  const before = await seedConversation(h);
  assert.equal(await h.current.translate("Article.", "auto", "Chinese"), null);
  h.render();
  assert.equal(h.current.loading, false);
  assert.equal(h.current.error, "Synthetic translation failure");
  assert.deepEqual(h.messages(), before);
});

test("should send only earlier direct conversations as history after a translation and rerender", async () => {
  const h = harness({ translate: async () => ({ translated: "Translated article." }) });
  await seedConversation(h);
  const before = h.conversation();
  await h.current.translate("Article.", "auto", "Chinese"); h.render();
  await h.current.sendMessage("Continue our conversation."); h.render();
  assert.deepEqual(h.calls.chat[1].chat_history, before);
  assert.equal(h.current.messages.length, 4);
});

test("should preserve real sentence batch order, progress and joined results without adding Chat messages", async () => {
  const { content, units } = sentenceDocument();
  let batch = 0;
  const h = harness({ sentences: async (items) => ({ pairs: items.map((source) => ({ source, translated: `Translation ${++batch}` })) }) });
  const before = await seedConversation(h);
  const progress = [];
  const result = await h.current.translateSentences(content, "auto", "Chinese", (value) => progress.push(plain(value)));
  h.render();
  assert.deepEqual(h.calls.sentences.map(([items]) => plain(items)), units.map((unit) => [unit]));
  assert.deepEqual(progress, [{ currentBatch: 0, totalBatches: 2 }, { currentBatch: 1, totalBatches: 2 }, { currentBatch: 2, totalBatches: 2 }]);
  assert.deepEqual(plain(result), { pairs: units.map((source, i) => ({ source, translated: `Translation ${i + 1}` })), translated: "Translation 1\n\nTranslation 2" });
  assert.equal(h.current.loading, false);
  assert.equal(h.current.lastOperation, "translation");
  assert.equal(h.current.error, null);
  assert.deepEqual(h.messages(), before);
});

test("should return null and preserve direct history when a later sentence batch fails", async () => {
  const { content } = sentenceDocument();
  let batch = 0;
  const h = harness({ sentences: async (items) => {
    if (++batch === 2) throw new Error("Synthetic batch failure");
    return { pairs: items.map((source) => ({ source, translated: "First translation." })) };
  } });
  const before = await seedConversation(h);
  assert.equal(await h.current.translateSentences(content, "auto", "Chinese"), null);
  h.render();
  assert.equal(h.calls.sentences.length, 2);
  assert.equal(h.current.error, "Synthetic batch failure");
  assert.equal(h.current.loading, false);
  assert.equal(h.current.lastOperation, "translation");
  assert.deepEqual(h.messages(), before);
});

test("should abort an unfinished first sentence batch without extra requests or Chat operation messages", async () => {
  const { content } = sentenceDocument();
  const h = harness({ sentences: (_items, _source, _target, signal) => rejectOnAbort(signal) });
  const before = await seedConversation(h);
  const pending = h.current.translateSentences(content, "auto", "Chinese"); h.render();
  const signal = h.calls.sentences[0][3];
  h.current.cancelTranslation();
  assert.equal(signal.aborted, true);
  assert.deepEqual(plain(await pending), { pairs: [], translated: "" });
  h.render();
  assert.equal(h.calls.sentences.length, 1);
  assert.equal(h.current.loading, false);
  assert.equal(h.current.error, null);
  assert.deepEqual(h.messages(), before);
});

test("should retain completed sentence pairs on cancellation without requesting another batch or changing Chat", async () => {
  const { content, units } = sentenceDocument(3);
  const enteredSecond = deferred();
  let batch = 0;
  const h = harness({ sentences: (items, _source, _target, signal) => {
    if (++batch === 1) return Promise.resolve({ pairs: items.map((source) => ({ source, translated: "Completed translation." })) });
    enteredSecond.resolve();
    return rejectOnAbort(signal);
  } });
  const before = await seedConversation(h);
  const pending = h.current.translateSentences(content, "auto", "Chinese");
  await enteredSecond.promise; h.render();
  h.current.cancelTranslation();
  assert.equal(h.calls.sentences[1][3].aborted, true);
  assert.deepEqual(plain(await pending), { pairs: [{ source: units[0], translated: "Completed translation." }], translated: "Completed translation." });
  h.render();
  assert.equal(h.calls.sentences.length, 2);
  assert.equal(h.current.loading, false);
  assert.equal(h.current.error, null);
  assert.deepEqual(h.messages(), before);
});

test("should retain the last operation source after completion and clear earlier errors on the next operation", async () => {
  const chatGate = deferred();
  const translationGate = deferred();
  const h = harness({ chat: () => chatGate.promise, translate: () => translationGate.promise });
  assert.equal(h.current.lastOperation, null);
  const chat = h.current.sendMessage("Direct question."); h.render();
  assert.equal(h.current.lastOperation, "chat");
  assert.equal(h.current.loading, true);
  chatGate.reject(new Error("Synthetic chat failure")); await chat; h.render();
  assert.equal(h.current.lastOperation, "chat");
  assert.equal(h.current.error, "Synthetic chat failure");
  assert.equal(h.current.loading, false);
  const translation = h.current.translate("Article.", "auto", "Chinese"); h.render();
  assert.equal(h.current.lastOperation, "translation");
  assert.equal(h.current.error, null);
  assert.equal(h.current.loading, true);
  translationGate.resolve({ translated: "Translated article." }); await translation; h.render();
  assert.equal(h.current.lastOperation, "translation");
  assert.equal(h.current.loading, false);
  assert.equal(h.current.error, null);
});

function startPreparedTranslation(h, mode, prepare, onProgress) {
  return mode === "full"
    ? h.current.translate("Article.", "auto", "Chinese", prepare)
    : h.current.translateSentences("Article.", "auto", "Chinese", onProgress, prepare);
}

function preparationHarness() {
  return harness({
    translate: async () => ({ translated: "Translated article." }),
    sentences: async (items) => ({ pairs: items.map((source) => ({ source, translated: "Translated article." })) }),
  });
}

for (const mode of ["full", "sentences"]) {
  test(`should keep ${mode} translation busy without API calls until preparation completes`, async () => {
    const h = preparationHarness();
    const before = await seedConversation(h);
    const gate = deferred();
    let preparations = 0;
    const progress = [];
    const pending = startPreparedTranslation(h, mode, () => { preparations++; return gate.promise; }, (value) => progress.push(plain(value)));
    h.render();
    const during = { loading: h.current.loading, error: h.current.error, source: h.current.lastOperation, requests: h.calls.translate.length + h.calls.sentences.length, progress: [...progress], messages: h.messages() };
    gate.resolve();
    const result = await pending; h.render();
    assert.equal(preparations, 1);
    assert.deepEqual(during, { loading: true, error: null, source: "translation", requests: 0, progress: [], messages: before });
    assert.equal(mode === "full" ? result : result.translated, "Translated article.");
    assert.equal(h.calls.translate.length + h.calls.sentences.length, 1);
    assert.equal(h.current.loading, false);
    assert.equal(h.current.lastOperation, "translation");
    assert.deepEqual(h.messages(), before);
  });

  test(`should recover from ${mode} preparation failure without translating or changing direct history`, async () => {
    const h = preparationHarness();
    const before = await seedConversation(h);
    let preparations = 0;
    const failed = await startPreparedTranslation(h, mode, async () => { preparations++; throw new Error("Synthetic preparation failure"); });
    h.render();
    const afterFailure = { result: plain(failed), loading: h.current.loading, error: h.current.error, source: h.current.lastOperation, requests: h.calls.translate.length + h.calls.sentences.length, messages: h.messages() };
    const retry = await startPreparedTranslation(h, mode, async () => { preparations++; }); h.render();
    assert.deepEqual(afterFailure, { result: null, loading: false, error: "Synthetic preparation failure", source: "translation", requests: 0, messages: before });
    assert.equal(preparations, 2);
    assert.equal(mode === "full" ? retry : retry.translated, "Translated article.");
    assert.equal(h.calls.translate.length + h.calls.sentences.length, 1);
    assert.equal(h.current.loading, false);
    assert.equal(h.current.error, null);
    assert.deepEqual(h.messages(), before);
  });
}

for (const rejectPreparation of [false, true]) {
  test(`should keep cancelled sentence preparation busy until it ${rejectPreparation ? "rejects" : "resolves"} without requesting a batch`, async () => {
    const h = preparationHarness();
    const before = await seedConversation(h);
    const gate = deferred();
    void gate.promise.catch(() => {});
    let preparations = 0;
    const pending = startPreparedTranslation(h, "sentences", () => { preparations++; return gate.promise; }); h.render();
    h.current.cancelTranslation(); h.render();
    const during = { loading: h.current.loading, error: h.current.error, requests: h.calls.sentences.length, messages: h.messages() };
    if (rejectPreparation) gate.reject(new Error("Synthetic preparation rejection after Stop"));
    else gate.resolve();
    const result = await pending; h.render();
    assert.equal(preparations, 1);
    assert.deepEqual(during, { loading: true, error: null, requests: 0, messages: before });
    assert.deepEqual(plain(result), { translated: "", pairs: [] });
    assert.equal(h.calls.sentences.length, 0);
    assert.equal(h.current.loading, false);
    assert.equal(h.current.error, null);
    assert.equal(h.current.lastOperation, "translation");
    assert.deepEqual(h.messages(), before);
  });
}
