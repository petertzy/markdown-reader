# AI Panel and Notes Context

The AI panel groups the application's document chat, AI editing, translation, provider settings, and local notes retrieval. Open it with **AI Assistant** (🤖) in the toolbar. Its tabs are **Chat**, **Work**, **Translate**, and **Settings**.

## Chat with document context

The Chat tab sends your message along with the active document and selected text as context. Ask questions, request an explanation, or ask for a suggested edit. When the response includes an actionable document change, inspect it and choose the Apply control shown with the response.

The chat panel also shows source labels when a response uses the configured Notes Context index. A suggested action is not applied merely because the assistant returned it; use the Apply control to make the edit.

## Use a local Notes Context index

Notes Context lets Chat retrieve relevant excerpts from a folder of personal or project notes.

1. In the Chat tab, choose **Select** or **Change** beside Notes Context.
2. Browse to a local folder, or enter an absolute folder path and choose **Index**.
3. Wait for indexing to complete. The panel displays the selected folder and the number of indexed notes.
4. Use the **ON/OFF** control to include or exclude retrieved notes from Chat requests.
5. Re-index after changing the note folder's contents. Use **Clear** in the notes manager to remove indexed content and clear the saved folder selection.

The indexer reads Markdown, Markdown-extension, and plain-text files (`.md`, `.markdown`, and `.txt`). It skips hidden folders and configured application/tool directories such as `.git`, `.obsidian`, `node_modules`, `.venv`, `dist`, and `.build`. Notes are split into chunks using headings and paragraph structure, then stored in a local SQLite database. Search uses SQLite FTS5 relevance scoring when available and a keyword-scoring fallback otherwise. The index is local; it is not a cloud vector database.

When Notes Context is enabled, relevant excerpts retrieved from that local index are added to the AI chat prompt. Those excerpts may therefore be sent to the AI provider configured in Settings as part of the request. Local indexing does not mean that retrieved note content stays on the device after it is included in an external provider request. Check your data-handling requirements before enabling this for confidential notes.

The notes index and its selected folder are stored in the application's per-user configuration area. The database is named `knowledge_base.db`; use the panel's **Clear** control to clear indexed content through the application.

## Work on the active document

In the Work tab, set **Work scope** to **Active document** and enter an instruction. Choose **Apply Changes** to run the AI editing request against the active document. The returned document content is applied to the editor if the document has not changed during the request. In the main Monaco editor, the result is applied as one editor change that can be undone through the editor's undo history. This is a direct document replacement, not a multi-file diff-review workflow.

## Work across an open project

Choose **Open project** in the Work scope selector to use Project Work. The AI first sees the project file list and then requests the files it needs to inspect before preparing proposed changes. The UI displays inspected files and file-by-file diffs. You review the proposal and explicitly accept it into editor tabs; it does not write to disk directly.

See the [Project Workflows guide](./ProjectWorkflows.md) for project discovery, limits, validation, staging, and saving behavior.

## Translation

The Translate tab supports full-document or selection translation, Full Text or Sentence Pairs mode, progress for sentence batches, and a Stop action for an in-progress sentence translation. A stopped sentence-pair operation may leave only the batches that completed before cancellation available for review.

Project-wide translation is also exposed in the Translate tab when a project folder is open. It translates Markdown files into a separate output tree and supports cancellation and retries for failed files. See the [Project Workflows guide](./ProjectWorkflows.md) for output paths, asset copying, and file-level behavior.

## Provider settings and data handling

The Settings tab configures the AI provider, model, base URL, and API key. Supported provider choices include OpenAI, Anthropic, OpenRouter, OpenAI-compatible endpoints, and local compatible services such as LM Studio and Ollama. NVIDIA and Groq are offered as OpenAI-compatible endpoint choices; Custom is available for local-compatible services.

Provider/model preferences and the selected endpoint are stored in per-user settings. API keys can be stored using the operating-system credential store through keyring when available; environment variables are also supported. A provider may receive the active document, selected text, project excerpts, or retrieved note snippets depending on the feature and request. Only send content to external services when your data-handling rules permit it.

## Related documentation

- [User guide](./UserGuide.md)
- [Project workflows](./ProjectWorkflows.md)
- [Technical documentation](./TECHNICAL.md)
