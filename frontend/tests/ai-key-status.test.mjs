import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import vm from "node:vm";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";

const filename = fileURLToPath(new URL("../src/components/AIPanel.tsx", import.meta.url));
const require = createRequire(filename);
const source = readFileSync(filename, "utf8");
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX },
}).outputText;

function renderSettings(status) {
  const settings = {
    ai_provider: "openai_compatible",
    provider_order: ["openai_compatible"],
    providers: {
      openai_compatible: {
        display_name: "OpenAI Compatible",
        model: "test-model",
        default_models: ["test-model"],
        key_configured: status === "saved" || status === "environment",
      },
    },
    api_key_statuses: { openai_compatible_nvidia: status },
    openai_compatible_base_url_choice: "nvidia",
    openai_compatible_base_url_options: [
      { key: "nvidia", label: "NVIDIA", url: "http://127.0.0.1/v1" },
    ],
    local_ai_base_url_options: [],
    secure_key_storage_available: status !== "environment",
  };
  const exports = {};
  const componentRequire = (name) => {
    if (name === "@/lib/api") {
      return { AI: {}, Knowledge: {}, getDefaultAISettings: () => settings };
    }
    if (name === "@/hooks/useAIChat") {
      return { useAIChat: () => ({ messages: [], loading: false, error: null }) };
    }
    if (name === "@/components/ProjectWorkReview") {
      return { default: () => null };
    }
    if (name === "@/lib/inline-markdown.mjs") {
      return require("../lib/inline-markdown.mjs");
    }
    return require(name);
  };
  vm.runInNewContext(compiled, { exports, require: componentRequire }, { filename });
  return renderToStaticMarkup(React.createElement(exports.default, {
    documentText: "", initialTab: "settings",
  }));
}

test("Delete Key is disabled and absence is explicit when no API key is saved", () => {
  const html = renderSettings("not_saved");
  const button = html.match(/<button\b([^>]*)>Delete Key<\/button>/);
  assert.ok(button, "the rendered settings must contain the key action");
  assert.match(button[1], /\bdisabled=""/, "an absent saved key cannot be deleted");
  assert.match(html, /No API key is saved\./);
});

test("Delete Key is enabled and saved storage is explicit for a saved API key", () => {
  const html = renderSettings("saved");
  const button = html.match(/<button\b([^>]*)>Delete Key<\/button>/);
  assert.ok(button);
  assert.doesNotMatch(button[1], /\bdisabled=""/);
  assert.match(html, /An API key is saved in the system credential store\./);
});

test("an environment fallback offers clearing without claiming a saved key", () => {
  const html = renderSettings("environment");
  const button = html.match(/<button\b([^>]*)>Clear Environment Key<\/button>/);
  assert.ok(button);
  assert.doesNotMatch(button[1], /\bdisabled=""/);
  assert.match(html, /An API key is configured in the environment\. Secure storage is unavailable\./);
  assert.doesNotMatch(html, /An API key is saved in the system credential store\./);
});

for (const status of ["unavailable", undefined]) {
  test(`unknown saved-key status disables deletion (${status ?? "missing field"})`, () => {
    const html = renderSettings(status);
    const button = html.match(/<button\b([^>]*)>Delete Key<\/button>/);
    assert.ok(button);
    assert.match(button[1], /\bdisabled=""/);
    assert.match(html, /Saved API key status is unavailable\. Refresh to try again\./);
    assert.doesNotMatch(html, /No API key is saved\./);
  });
}

// Use the component's actual handlers with a fresh render snapshot per action,
// as in provider-model-selection.test.mjs. Shared refs survive each snapshot.
const settingsStart = source.indexOf("  const syncSettingsForm =");
const settingsEnd = source.indexOf("  const handleProviderChange =", settingsStart);
const fetchStart = source.indexOf("  const handleFetchModels =");
const fetchEnd = source.indexOf("  const saveSettings =", fetchStart);
assert.ok(settingsStart >= 0 && settingsEnd > settingsStart);
assert.ok(fetchStart >= 0 && fetchEnd > fetchStart);
const handlers = ts.transpileModule(
  `${source.slice(settingsStart, settingsEnd)}\n${source.slice(fetchStart, fetchEnd)}\n({ loadSettings, handleFetchModels });`,
  { compilerOptions: { target: ts.ScriptTarget.ES2022 } },
).outputText;

function settingsResponse(status) {
  return {
    ai_provider: "openai",
    provider_order: ["openai"],
    providers: { openai: { model: "loaded-model", default_models: ["loaded-model"] } },
    api_key_statuses: { openai: status },
    local_ai_base_url_options: [],
  };
}

function settingsHandlers() {
  let resolve, reject;
  const pendingSettings = new Promise((success, failure) => { resolve = success; reject = failure; });
  const state = {
    settings: settingsResponse("saved"), settingsLoading: false, settingsSaving: false,
    modelsFetching: false, settingsMessage: null, provider: "openai",
    baseUrlChoice: "nvidia", localBaseUrlChoice: "lm_studio", localBaseUrl: "",
    model: "old-model", modelOptions: [], apiKey: "",
  };
  const refs = {
    settingsRequestSeq: { current: 0 }, modelRequestSeq: { current: 0 },
    providerRef: { current: "openai" }, localBaseUrlChoiceRef: { current: "lm_studio" },
    localBaseUrlRef: { current: "" },
  };
  const calls = { settings: 0, models: [] };
  const update = (name) => (value) => {
    state[name] = typeof value === "function" ? value(state[name]) : value;
  };
  const setters = {
    setSettings: update("settings"), setSettingsLoading: update("settingsLoading"),
    setSettingsMessage: update("settingsMessage"), setProvider: update("provider"),
    setBaseUrlChoice: update("baseUrlChoice"), setLocalBaseUrlChoice: update("localBaseUrlChoice"),
    setLocalBaseUrl: update("localBaseUrl"), setModel: update("model"),
    setApiKey: update("apiKey"), setModelsFetching: update("modelsFetching"),
    setModelOptions: (value) => { state.modelOptions = Array.from(value); },
  };
  const AI = {
    getSettings() { calls.settings += 1; return pendingSettings; },
    async getModels(...args) { calls.models.push(args); return { models: ["catalog-model"] }; },
  };
  return {
    state, calls, resolve, reject,
    render: () => vm.runInNewContext(handlers, {
      ...state, ...refs, ...setters, AI, Error,
      selectedLocalBaseUrl: () => "", currentLocalBaseUrl: () => "",
      normalizeBaseUrl: (value) => value,
    }),
  };
}

for (const outcome of ["not_saved", "failure"]) {
  test(`Fetch Models cannot discard a pending settings ${outcome} result`, async () => {
    const h = settingsHandlers();
    const loading = h.render().loadSettings();
    assert.equal(h.state.settingsLoading, true);
    await h.render().handleFetchModels();
    const pendingLoading = h.state.settingsLoading;
    if (outcome === "failure") h.reject(new Error("Synthetic settings read failure"));
    else h.resolve(settingsResponse("not_saved"));
    await loading;
    assert.deepEqual({
      settingsRequests: h.calls.settings, modelRequests: h.calls.models.length,
      pendingLoading, finalLoading: h.state.settingsLoading,
      finalKeyStatus: h.state.settings.api_key_statuses.openai,
      message: h.state.settingsMessage,
    }, {
      settingsRequests: 1, modelRequests: 0, pendingLoading: true, finalLoading: false,
      finalKeyStatus: outcome === "failure" ? undefined : "not_saved",
      message: outcome === "failure" ? "Synthetic settings read failure" : null,
    });
  });
}

test("Fetch Models makes no request while settings are saving", async () => {
  const h = settingsHandlers();
  h.state.settingsSaving = true;
  await h.render().handleFetchModels();
  assert.equal(h.calls.models.length, 0);
  assert.equal(h.state.settingsSaving, true);
  assert.equal(h.state.settings.api_key_statuses.openai, "saved");
});

test("Fetch Models still loads the model catalog when settings are idle", async () => {
  const h = settingsHandlers();
  await h.render().handleFetchModels();
  assert.deepEqual(h.calls.models, [["openai", ""]]);
  assert.deepEqual(h.state.modelOptions, ["catalog-model"]);
  assert.equal(h.state.model, "catalog-model");
  assert.equal(h.state.modelsFetching, false);
  assert.equal(h.state.settings.api_key_statuses.openai, "saved");
});
