import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import vm from "node:vm";

// Exercise the actual component handlers with React-style render snapshots and
// state setters. No provider requests, API keys, or browser services are used.
const source = readFileSync(new URL("../src/components/AIPanel.tsx", import.meta.url), "utf8");
const start = source.indexOf("  const refreshModelOptions = async (");
const end = source.indexOf("  const handleBaseUrlChange =", start);
assert.ok(start >= 0 && end > start, "component model handlers must be present");
const handlers = source.slice(start, end)
  .replace("nextProvider: string", "nextProvider");

function harness(initialModel, responseModels) {
  let selected = initialModel;
  let options = [];
  const requests = [];
  const settings = { providers: {
    openrouter: { model: "nvidia/saved-free", default_models: ["router/default"] },
    openai: { model: "openai/saved", default_models: ["openai/default"] },
  } };
  const context = {
    provider: "openai", model: initialModel, baseUrlChoice: "nvidia",
    localBaseUrlChoice: "lm_studio", localBaseUrl: "", apiKey: "", settings,
    modelRequestSeq: { current: 0 }, providerRef: { current: "openai" },
    localBaseUrlChoiceRef: { current: "lm_studio" }, localBaseUrlRef: { current: "" },
    setModel: (value) => { selected = typeof value === "function" ? value(selected) : value; },
    setModelOptions(value) { options = Array.from(value); }, setProvider() {}, setApiKey() {}, setSettingsMessage() {},
    setModelsFetching() {}, setLocalBaseUrlChoice() {}, setLocalBaseUrl() {},
    selectedLocalBaseUrl: () => "http://localhost/v1", normalizeBaseUrl: (x) => x,
    currentLocalBaseUrl: () => "http://localhost/v1",
    AI: { getModels: () => new Promise((resolve) => { requests.push(resolve); }), setProvider: async () => {} },
  };
  const actions = vm.runInNewContext(`${handlers}; ({ handleProviderChange, refreshModelOptions });`, context);
  return { ...actions, selected: () => selected, options: () => options,
    select: (value) => context.setModel(value),
    resolve: async (index = 0, models = responseModels) => { requests[index]({ models }); await Promise.resolve(); await Promise.resolve(); },
  };
}

test("switching back to OpenRouter preserves its saved model after catalog refresh", async () => {
  const h = harness("openai/saved", ["router/default", "nvidia/saved-free"]);
  h.handleProviderChange("openrouter");
  assert.equal(h.selected(), "nvidia/saved-free");
  await h.resolve();
  assert.equal(h.selected(), "nvidia/saved-free");
});

test("model selection made while a catalog request is pending is preserved", async () => {
  const h = harness("old-model", ["first-model", "chosen-model"]);
  const request = h.refreshModelOptions();
  h.select("chosen-model");
  await h.resolve();
  await request;
  assert.equal(h.selected(), "chosen-model");
});

test("unavailable models still fall back to the first returned model", async () => {
  const h = harness("missing", ["available"]);
  const request = h.refreshModelOptions();
  await h.resolve(); await request;
  assert.equal(h.selected(), "available");
});

test("an empty model catalog still clears selection", async () => {
  const h = harness("missing", []);
  const request = h.refreshModelOptions();
  await h.resolve(); await request;
  assert.equal(h.selected(), "");
});

test("a later provider switch ignores the previous provider's in-flight refresh", async () => {
  const h = harness("openai/saved", ["first-model", "nvidia/saved-free", "openai/saved"]);
  h.handleProviderChange("openrouter");
  h.handleProviderChange("openai");
  await h.resolve(1, ["openai/saved"]);
  await h.resolve(0, ["router/default", "nvidia/saved-free"]);
  assert.equal(h.selected(), "openai/saved");
  assert.deepEqual(h.options(), ["openai/saved"]);
});
