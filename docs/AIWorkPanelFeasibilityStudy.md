# Feasibility Study: AI Work Panel and Future Project Direction

> **Issue Reference:** [#274](https://github.com/petertzy/markdown-reader/issues/274)  
> **Status:** Proposal & Feasibility Report  
> **Target Audience:** Maintainers, Contributors, and Extension Developers

---

## 1. Executive Summary

As AI-assisted tooling transitions from conversational chat into **active, task-oriented execution**, Markdown Reader could introduce a dedicated **AI Work Panel**. The existing AI chat assistant already supports reviewable edit proposals; the proposed panel would focus on task-oriented document modification, allowing users to describe editing, formatting, restructuring, or translation goals and review the resulting changes before applying them. Safe application and undo behavior are design requirements that need validation during implementation.

This study explores the architectural feasibility, user experience requirements, backend protocols, and phased implementation strategy for the feature.

---

## 2. Core Differences: Chat Panel vs. Work Panel

| Dimension | AI Chat Assistant (Existing) | AI Work Panel (Proposed) |
| :--- | :--- | :--- |
| **Primary Goal** | Answer queries, explain concepts, summarize | Perform modifications, refactor, and generate content |
| **Output Type** | Conversational response plus optional structured edit proposal | Task result with reviewable document edits / diffs |
| **Context Scope** | Prompt + active document + selection | Full active document + selection + metadata |
| **User Interaction** | Review and optionally apply a proposal in the existing panel | Review changes and accept/revert with one click |
| **Editor Integration** | Applies accepted actions through the existing editor adapter | Active (`editor.executeEdits` with undo-stack preservation) |

---

## 3. Phase 1: Single-Document Work Panel Architecture

### 3.1 Architecture Overview

```
┌────────────────────────────────────────────────────────┐
│                   Frontend (Next.js)                   │
│                                                        │
│  ┌──────────────────┐            ┌──────────────────┐  │
│  │  Monaco Editor   │◀───────────│  AI Work Panel   │  │
│  │ (Active Document)│            │  (Input & Tasks) │  │
│  └─────────┬────────┘            └─────────┬────────┘  │
│            │ Document Context              │ Task Req  │
│            ▼                               ▼           │
│  ┌──────────────────────────────────────────────────┐  │
│  │              useAIActions / useWork              │  │
│  └──────────────────────────┬───────────────────────┘  │
└─────────────────────────────┼──────────────────────────┘
                              │ HTTP / SSE Stream
                              ▼
┌────────────────────────────────────────────────────────┐
│               Python Sidecar (FastAPI)                 │
│                                                        │
│  ┌──────────────────────────────────────────────────┐  │
│  │   /api/ai/work (Router)                          │  │
│  │   - System prompt enforcement (Raw Markdown)     │  │
│  │   - Context chunking & token budget management   │  │
│  │   - Provider abstraction (OpenAI/Anthropic/Local)│  │
│  └──────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────┘
```

### 3.2 Key Technical Considerations

1. **Preserving Monaco Undo/Redo History:**
   - Replacing the entire document via `editor.setValue()` destroys Monaco's undo stack, causing frustration if the user wants to revert.
   - **Recommended Approach:** On the mounted editor instance, use `editor.executeEdits("ai-work", [{ range: fullRange, text: newContent }])` and use `model.pushStackElement()` to delimit the operation in the undo history. Verify undo and redo behavior against the supported Monaco version and editor lifecycle before relying on it; the API calls alone do not guarantee exact restoration in every integration.

2. **System Prompt Formulation:**
   - The LLM prompt must strictly prohibit conversational commentary (e.g., "Here is your updated markdown:").
   - Output should be clean Markdown that preserves existing frontmatter and structure unless explicitly instructed otherwise. Validate or review generated output before applying it.

3. **Stale-Document Guard & Concurrency Safety:**
   - Undo history alone is insufficient if the user continues editing while an AI generation request is in flight. Overwriting the active document with `newContent` derived from an older snapshot would destroy intervening keystrokes.
   - **Protocol Enforcement:**
     - The dispatch payload attaches a document revision counter or content hash (`baseDocHash`).
     - Upon receiving the result and again immediately before applying it, the client verifies whether the editor's current hash matches `baseDocHash`.
     - **Mismatch Handling:** If the document has diverged, **"Apply Directly"** is strictly disabled/rejected. The UI informs the user of concurrent changes and directs them to **"Review Diff"** (with 3-way merge/conflict highlighting) or prompts to re-run against the latest snapshot.

4. **Diff & Review Experience:**
   - Provide an optional side-by-side or inline diff preview before applying destructive changes.
   - Users can choose between **"Apply Directly"** (guarded by snapshot validity and instant undo) and **"Review Diff"**.

---

## 4. Phase 2: Project-Wide AI Workflows

Once single-document editing is stable, the same pattern can be extended to multi-file project workflows:

1. **Unattended Batch Translation:**
   - Translates all Markdown files in a folder while preserving YAML frontmatter, code blocks, and internal link topologies.
   - Operates asynchronously with progress tracking reported in the status bar.

2. **Markdown Project to Published Book:**
   - Automated ordering based on headings and naming conventions.
   - Generation of unified Table of Contents, continuous page numbers, and cross-reference citations.
   - Export to formatted PDF and DOCX using existing export pipelines.

---

## 5. Feasibility Verdict

- **Technical Feasibility:** The proposal appears technically feasible based on the existing Monaco integration, Python sidecar with multi-provider AI support, and extensible panel system (`PANELS.AI`). Undo grouping, stale-result handling, and review behavior still need implementation and validation.
- **Implementation Effort:** Requires a task-oriented backend endpoint or equivalent flow and frontend integration for generating, reviewing, and applying edits. Effort depends on the chosen diff and conflict-resolution experience.
- **Recommended Action:** Prototype Phase 1 for the current editor tab, including guarded application, reviewable changes, and verified undo/redo behavior. Keep #274 open as the umbrella roadmap issue while feasibility is validated.
