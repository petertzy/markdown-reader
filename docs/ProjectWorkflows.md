# Project Workflows

This guide documents the project-wide workflows implemented in Markdown Reader. These tools operate on a selected local project folder and should be used with a backup of important source files.

## Open a project folder

Choose **Project** in the toolbar or **File → Open Folder**. The application recursively discovers supported files below the selected folder and opens those files in editor tabs. The Explorer also displays the folder hierarchy; its subdirectories load when expanded, and selecting a file in the tree opens that file in a tab.

Because opening a project can open many files, use a folder containing the documents you intend to work with. Project translation and Project Work use the selected folder as their root. Project Work can use the current contents of open editor tabs as input, so keep the intended project selected and save important changes before starting.

## Translate a project

Project translation translates Markdown files under the selected project root as one cancellable task. In the AI panel, open the **Translate** tab and use the **Translate project** controls.

1. Open the source project folder.
2. In the Translate tab, choose the source language or leave it on **Auto Detect**, then select a target language.
3. Start **Translate project**.
4. Follow the completed/total file count, task status, and per-file results.
5. If the task finishes with failed files, choose **Retry failed files** to start a retry for only those files.
6. Open the output directory shown by the task and inspect the translated Markdown.

Only Markdown files (`.md` and `.markdown`) are translated. Hidden folders, vendor/build folders, and symlinked directories/files are excluded from source discovery. A file larger than 1 MB is reported as failed rather than translated. A failure on one file does not prevent the remaining files from being processed.

The source files are not modified. Results are written to a separate output tree inside the project, organized by target-language slug (for example, `translations/french/`). Relative local assets referenced by Markdown links are copied into the corresponding output tree so that translated documents can continue to resolve those assets. The output directory is excluded from future source discovery. The task can be cancelled while it is running; cancellation is cooperative between files.

Markdown-sensitive spans are protected during translation. This includes code fences, inline code, math, HTML, URLs, link destinations and reference labels, and front matter keys. Protected content is restored after the provider responds; if required tokens are lost or invented, that file fails validation. This protection reduces structural damage but does not guarantee a perfect translation. Review the translated prose, links, copied assets, formatting, and terminology before publishing the result.

## Use Project Work for multi-file changes

Project Work lets the AI prepare a proposed set of edits across files in the open project. Use it for coordinated tasks such as consistent terminology changes or related documentation updates, not for silent bulk file writes.

1. Open the relevant project folder.
2. Open the AI panel's **Work** tab and set **Work scope** to **Open project**.
3. Enter a specific instruction describing the requested changes and boundaries.
4. Let the workflow discover project paths, inspect requested files, and prepare a task summary.
5. Review the inspected-file list, every proposed file change, and each diff.
6. Choose **Accept changes into editor** only when the proposal is acceptable, or discard it to abandon the proposal.
7. Review and save each changed file from its editor tab.

Project Work reads eligible UTF-8 `.md`, `.markdown`, and `.txt` files. It skips hidden paths, symlinks, and configured dependency/build directories. It discovers paths first; the model then requests the contents it needs in bounded steps. The workflow validates that inspected files and open buffers have not changed before applying the proposal. It does not write changes directly to project files. Applying stages the proposed content in editor tabs, where you can inspect and save it normally.

Project Work is bounded to a maximum of 2,000 discovered files, 120 KB of request context, 12 provider steps, and a one-hour in-memory task lifetime. These limits help keep work scoped; they are not a promise that every project can be processed in one task. Task state is held by the local backend process and should not be treated as durable storage across an app/backend restart.

## Prepare a publication from open tabs

The **Publication** panel combines selected open document tabs into one publication draft.

1. Open the documents to include.
2. Open the **Publication** panel from the toolbar.
3. Select the tabs and use the up/down controls to arrange their order.
4. Choose **Prepare publication** and inspect the combined draft.
5. Export the prepared result to HTML or PDF.

Preparation is deterministic, not AI-authored. It applies the application's Markdown formatting rules, joins the selected content with separators, resolves relative image paths using each source file's directory, and generates a table of contents from the combined headings. It operates on the content in open tabs, so ensure those tabs contain the latest changes you want included.

Publication HTML can be downloaded from browser-based development. Publication PDF export uses the desktop save-dialog flow and requires the Tauri app. Review the combined document and its image references before distribution.

## Safety and troubleshooting

- Keep a backup of important source documents before project-wide work.
- Do not assume translated output is publication-ready without reviewing it.
- Check per-file results when translation fails, then retry failed files if appropriate.
- Remember that opening a project can open all supported files below that folder in tabs.
- If Project Work reports that open documents changed while it was running, start the task again and inspect the fresh diffs.
- If no project is open, open a folder before starting a project-level task.
- AI operations may send document or project excerpts to the configured provider. Follow your privacy and data-handling requirements.

## Related documentation

- [User guide](./UserGuide.md)
- [AI panel and Notes Context](./ProjectAIWorkflows.md)
- [Technical documentation](./TECHNICAL.md)
- [Contributing guide](../CONTRIBUTING.md)
