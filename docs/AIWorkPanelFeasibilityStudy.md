# Feasibility Study: AI Work Panel and Future Project Direction

> **Issue Reference:** Closes [#274](https://github.com/petertzy/markdown-reader/issues/274)  
> **Status:** Proposal & Feasibility Report  
> **Target Audience:** Maintainers, Contributors, and Extension Developers

---

## 1. Executive Summary

As AI-assisted tooling transitions from passive conversational chat into **active, task-oriented execution**, Markdown Reader has the opportunity to introduce a dedicated **AI Work Panel**. Unlike the existing AI chat assistant, the Work Panel focuses on **direct document modification**, allowing users to specify editing, formatting, restructuring, and translation goals in natural language that are directly applied to the document with complete safety and undoability.

This study explores the architectural feasibility, user experience requirements, backend protocols, and phased implementation strategy for the feature.

---

## 2. Core Differences: Chat Panel vs. Work Panel

| Dimension | AI Chat Assistant (Existing) | AI Work Panel (Proposed) |
| :--- | :--- | :--- |
| **Primary Goal** | Answer queries, explain concepts, summarize | Perform modifications, refactor, and generate content |
| **Output Type** | Conversational prose and markdown snippets | Direct document edits / diffs |
| **Context Scope** | Prompt + selected snippet | Full active document + selection + metadata |
| **User Interaction** | Read and manually copy/paste snippets | Review changes and accept/revert with one click |
| **Editor Integration** | Passive | Active (`executeEdits` with undo-stack preservation) |

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
   - **Recommended Approach:** Use `monaco.executeEdits("ai-work", [{ range: fullRange, text: newContent }])` and push an undo stop via `model.pushStackElement()`. This ensures that pressing `Ctrl+Z` / `Cmd+Z` restores the exact pre-AI state.

2. **System Prompt Formulation:**
   - The LLM prompt must strictly prohibit conversational commentary (e.g., "Here is your updated markdown:").
   - Output must be clean, valid Markdown preserving existing frontmatter and structure unless explicitly instructed otherwise.

3. **Diff & Review Experience:**
   - Provide an optional side-by-side or inline diff preview before applying destructive changes.
   - Users can choose between **"Apply Directly"** (with instant undo) and **"Review Diff"**.

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

- **Technical Feasibility:** **10/10**. The application already possesses Monaco integration, a Python sidecar with multi-provider AI support, and an extensible panel system (`PANELS.AI`).
- **Implementation Effort:** **Low to Moderate**. Requires a new `/work` endpoint in the Python backend and an active edit handler in the frontend.
- **Recommended Action:** Adopt Phase 1 with `executeEdits` undo preservation and reviewable changes, keeping #274 open as the umbrella roadmap issue.
