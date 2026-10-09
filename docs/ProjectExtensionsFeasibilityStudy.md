# Feasibility Study: Project-Oriented Editing and Extensible AI/Tooling

> **Issue Reference:** [#360](https://github.com/petertzy/markdown-reader/issues/360)
> **Status:** Exploration & Architecture Proposal (no code changes)
> **Target Audience:** Maintainers and Contributors
> **Sequencing:** Follows #357 (project-wide AI workflows); deliberately exploratory per the issue's *Important Considerations*.

---

## 1. Executive Summary

Markdown Reader today is a document-centric editor with a working AI layer (chat, translate, Work panel) and two latent project-level capabilities: a **knowledge-base indexer** that already walks folders and chunks Markdown into SQLite FTS5, and a **files router** that reads/writes arbitrary absolute paths for the active document workflow.

This study answers the seven exploration questions posed by #360 and concludes:

- **Verdict: feasible, but gated.** The extension surface should stay *design-only* until #357 (project-wide Work) has demonstrated value, exactly as the issue instructs.
- **The cheapest high-value win is not an extension system at all**: it is promoting the existing knowledge-base machinery into a first-class *Project* concept in core (folder opening, project tree, project search). That work is needed by #357–#359 regardless of whether extensions ever ship.
- **A narrow, capability-based plugin seam can be introduced later** without reopening the architecture, if it follows the rules in §4–§7: extensions declare capabilities, never get raw filesystem or network authority, and surface to users only through the existing Work-panel review pipeline.

---

## 2. Current State (what exists today)

Grounded inventory of the surfaces this design builds on:

| Area | Where | Relevant facts |
| :--- | :--- | :--- |
| Work panel (single-doc) | `frontend/src/hooks/useAIActions.ts`, `backend/routers/ai.py` | `POST /api/ai/work` takes `{instruction, document_content}`, returns `{modified_content}`; synchronous; frontend stale-result guard; result applied as **one undoable Monaco edit**. |
| AI provider abstraction | `backend/ai_logic.py` (~1.8k lines) | Provider order + fallback, OpenAI-compatible/local base-URL options, secure key storage (`is_secure_key_storage_available`), model persistence, retry/quota/context-length handling. |
| Project file discovery | `backend/knowledge_logic.py` | `find_note_files()` recursively walks a folder, skips ignored dirs/hidden files; `index_knowledge_base()` incrementally chunks Markdown into **SQLite with FTS5**. |
| Arbitrary file I/O | `backend/routers/files.py` | `GET /api/files/read`, `POST /api/files/write` operate on **absolute paths with no sandbox** — today's trust model is "local app, user-initiated". |
| Backend auth | `backend/main.py` | Single shared token (`X-Markdown-Reader-Token`) gating all routers; a local-process trust boundary, not a multi-tenant one. |
| Frontend panel shell | `frontend/src/components/AIPanel.tsx` | Tabs: `chat / work / translate / settings` — a ready-made host for extension-provided actions. |

**Key observation:** the three prerequisites for "project-oriented editing" (folder walk, cross-file search, file read/write) already exist behind API endpoints. What is missing is the *Product concept* (a project) and the *governance layer* (who may do what) — not the primitives.

---

## 3. Relationship to #357–#359

```
#357 project-wide Work  ──►  #358 long-running tasks  ──►  #359 publication
        │
        └──► #360 (this study): defines the core-vs-extension boundary
              and the extension architecture those features may later plug into
```

- **#357 is the gate.** Until AI can safely discover, read, and propose writes to multiple project files, an extension model has nothing real to extend. This study therefore specifies *seams*, not implementations.
- **#358/#359 consume the same substrate**: long-running tasks and publication pipelines are natural *built-in* capabilities that would later be expressible through the capability model in §5.
- **This document changes no code** and requests no dependency or config additions.


---

## 4. Question 1 & 6 — What Belongs in Core vs. Extensions

**Decision rule:** *If a feature is required for the core promise — "author, review, and publish Markdown documents safely" — it is built-in. If it connects Markdown to the outside world (providers, services, formats), it is a candidate extension.*

### 4.1 Built-in (non-negotiable core)

| Capability | Why core |
| :--- | :--- |
| Editor, preview, tabs, find/undo, focus mode | The product itself. |
| Project folder opening, project tree, project-wide search | Needed by #357–#359; cannot depend on optional plugins. |
| File read/write **within the opened project** | Must be governed centrally (§7), never delegated raw. |
| Work-panel review/apply/undo pipeline | The universal safety mechanism; extensions must pass *through* it, not around it. |
| Export (HTML/PDF/DOCX), rendering, citations, knowledge indexing | Deterministic, local, testable — the "predictable output" half of the stack. |
| AI provider failover + key storage | Security-sensitive shared infrastructure. |

### 4.2 Extension candidates (later, if justified)

| Candidate | Rationale |
| :--- | :--- |
| Additional AI providers/protocols (e.g. MCP-style servers, local model runtimes) | The provider list is already config-shaped (`ai_logic.py`); a seam exists. |
| Translation/publication *pipelines* beyond the built-in defaults | #358/#359 may ship built-ins first; third parties can add variants. |
| Specialty document processors (diagrams, linting, style checks) | Pure functions over Markdown — the safest extension type. |
| Import/export formats (e.g. new target formats) | Format converters are leaf nodes; low blast radius. |

### 4.3 Explicitly out of scope


---

## 5. Question 2 & 3 — Proposed Architecture and the Work-Panel Capability Model

### 5.1 Layered architecture

```
┌───────────────────────────────────────────────────────────────┐
│ Frontend (Next.js)                                           │
│  AIPanel tabs (chat/work/translate/settings)                 │
│  + "capabilities" registry fed by backend capability list    │
│      → each entry renders as a Work-panel action template    │
└──────────────────────────┬────────────────────────────────────┘
                           │ HTTP (existing token auth)
┌──────────────────────────▼────────────────────────────────────┐
│ FastAPI backend                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ Capability Registry (built-in + enabled extensions)    │  │
│  │  - manifest validation  - permission grant check       │  │
│  └───────────────┬────────────────────────────┬───────────┘  │
│                  │                            │              │
│   ┌──────────────▼───────────┐   ┌────────────▼────────────┐ │
│   │ Core capabilities        │   │ Extension host (future) │ │
│   │  work, translate,        │   │  subprocess/HTTP tools  │ │
│   │  export, index, summarize│   │  no raw FS — mediated   │ │
│   └──────────────────────────┘   └─────────────────────────┘ │
└───────────────────────────────────────────────────────────────┘
```

### 5.2 How an extension surfaces in the Work panel

Extensions do **not** render UI. They declare **capabilities**; the Work panel renders them exactly like today's task templates (`get_ai_automation_task_templates`):

1. Extension manifest declares `capabilities[]` — each with: id, display name, input schema (JSON Schema), required permissions, and invocation target.
2. Backend validates manifests at load; only *enabled* capabilities enter the registry.
3. AIPanel's work tab lists registry entries as runnable templates (same UX as today).
4. Invocation goes backend→extension, **result returns as a structured proposal** that flows through `applyWorkResultIfFresh`-style review: the human still clicks *Apply Changes*.

This gives the issue's requirement — "extensions expose capabilities to the Work panel" — with **zero new frontend trust**: the panel treats extension output exactly like model output today (a proposal, never a direct write).

### 5.3 Invocation contract (proposed)

```jsonc
// POST /api/capabilities/{capability_id}/invoke   (future)
{
  "arguments": { /* input-schema validated */ },
  "context": {
    "project_root": "/path/from/opened-project",  // backend-supplied, never extension-supplied
    "file_scope":   ["rel/path/a.md"],            // resolved & clamped by backend
    "request_id":   "uuid"                        // logs + cancellation (#358 groundwork)
  }
}
// → 202 {request_id} + progress stream (SSE), mirroring the planned #358 task model
```

**Rule:** the extension never chooses paths; it receives backend-resolved, project-clamped paths.


---

## 6. Question 4 — Permissions / Security Model

### 6.1 Threat model (local-first)

The current app trusts its own process (shared token, absolute-path file I/O). Extensions change one thing: **third-party code becomes a principal**. Goals:

1. A malicious or buggy extension cannot read outside the opened project, exfiltrate API keys, or write files without user review.
2. Users can see, per extension, exactly what was granted — and revoke it.
3. Nothing in the default install is affected (issue requirement: minimal impact on non-users).

### 6.2 Capability-based grants (no ambient authority)

| Permission | Grants | Mediated by |
| :--- | :--- | :--- |
| `project:read` | Read files under the opened project root, clamped by backend path resolution | Backend `resolve_in_project()` (new; rejects `..`/symlinks escaping root) |
| `project:write` | **Propose** writes (never direct) | Work-panel review pipeline only |
| `ai:invoke` | Call the shared provider stack with the user's key | `ai_logic` — key material never crosses the extension boundary |
| `net:allowlist` | Call named HTTPS hosts listed in the manifest, allowlist-enforced | Backend egress proxy |
| `export:run` | Trigger deterministic exporters | Existing export router |

**Deny-by-default.** Grants are per-extension, shown at enable time, stored in app settings next to existing AI settings (`_load_app_settings`/`_save_app_settings` pattern), revocable instantly by disabling the extension.

### 6.3 Why this beats the alternatives

- **Subprocess sandbox per extension** (language runtimes, seccomp): strongest, but heavy for a document app; propose as a *Phase 2 hardening*, not a prerequisite — see §8.
- **"Trusted extensions" (all-or-nothing)**: too coarse; a diagram plugin shouldn't inherit file-write authority.
- **Current absolute-path I/O as-is**: fine for user-initiated actions; **unacceptable for extension-initiated ones** — §5.3's path clamping is the required new boundary.

Note: `POST /api/files/write` accepting arbitrary absolute paths is acceptable *today* because every call originates from the user's own keystrokes in this app. The moment a model or extension can drive it, mediation (project clamping + review) becomes mandatory — this is the single most important security conclusion of the study.


---

## 7. Question 5 — Lifecycle: Discover → Install → Enable → Configure → Disable

| Stage | Design | Precedent in-app |
| :--- | :--- | :--- |
| **Discover** | Curated directory (a JSON index in an `extensions/` folder or a registry URL); *browse-only, no auto-install* | Knowledge-base folder picker pattern |
| **Install** | Copy a folder containing an `extension.json` manifest + assets into the app's extension directory; hash recorded | Settings persistence (`_save_app_settings`) |
| **Enable/Disable** | Toggle in Settings; disabled = not loaded, zero surface | AI provider on/off style toggles |
| **Configure** | Per-manifest typed settings (path, URL, token) rendered from schema; secrets go through **existing secure key storage**, never manifest files | `set_secure_ai_api_key` / keyring path |
| **Update** | Hash-pinned; update shows manifest diff (permission changes require re-grant) | — (new, but small) |
| **Uninstall** | Delete folder + grants; no residue | — |

**Deliberately excluded from v1:** in-app marketplace, ratings, auto-updates, remote code fetch. Distribution starts as "drop a folder in" — matching the issue's *simple installation and configuration* principle and the project's conservative risk posture.

---

## 8. Question 7 — Proof-of-Concept Sketch (not implemented here)

**Chosen PoC: "Local Model Bridge" capability** — the smallest integration that exercises every layer without new risk:

1. Manifest declares one capability: `summarize-file` with `project:read` + `ai:invoke`.
2. Backend registers it beside built-in task templates; AIPanel renders it as one more Work template.
3. On invoke: backend clamps the file path to the project root, reads it, calls the **existing** provider stack (`_request_chat_from_provider`), and returns a proposal that the user applies through the unchanged review/undo pipeline.
4. Nothing else changes: no new frontend write paths, no key exposure, deny-by-default.

**Why this PoC:** it proves (a) manifest→registry→panel rendering, (b) permission mediation, (c) proposal-based results — using existing machinery end to end. A hypothetical `hello-world` shell extension is *rejected*: it would set the wrong precedent (ambient execution authority).

**Exit criteria for a real Phase 1** (to be judged *after* #357 ships):

- [ ] #357's project-wide Work is stable in production
- [ ] A project-root concept exists in the frontend (folder opened)
- [ ] Path-clamped `resolve_in_project()` exists and is tested
- [ ] At least one concrete third-party integration need is identified (not speculative)


---

## 9. Risks and Open Questions

| # | Risk / Question | Direction |
| :--- | :--- | :--- |
| 1 | Extension maintenance burden falls entirely on the maintainer | Start with *folder-drop* distribution; no registry = no SLA |
| 2 | Model/output injection: extension content influencing the model | Treat extension output as data; never merge into system prompts |
| 3 | Versioning vs. rapid core evolution | Manifest declares `apiVersion`; core rejects incompatible ones loudly |
| 4 | Is a plugin system justified at all? | Honest answer: **not yet**. §4.1's core list satisfies #357–#359 without it. Re-evaluate when a concrete external integration request arrives |
| 5 | Desktop (Tauri) vs. web deployment differences | Capability checks live in the Python backend — same code path in both |

---

## 10. Feasibility Verdict

**Technically feasible; organizationally gated.** The architecture in §5–§7 can be added *after* #357 without rework because it introduces one new boundary (the capability registry) and reuses the existing review pipeline as its universal safety valve. The recommended order:

1. **Now:** ship this study (this PR).
2. **Next:** #357 project-wide Work → its natural by-products (project root, path clamping) become the foundation.
3. **Then:** reassess §8's exit criteria; if a concrete integration demand exists, implement Phase 1 as specified — registry, manifests, mediated invocation, one PoC capability.

Until step 3 is triggered, **no extension code should be merged**, keeping the core small and the default experience untouched, per the issue's own guidance.

Arbitrary code execution, shell access, UI plugins that inject into the editor DOM, and anything that bypasses the review pipeline. The issue's design principle — *"minimal impact on users who do not need extensions"* — implies the default install carries **zero** of §4.2.
