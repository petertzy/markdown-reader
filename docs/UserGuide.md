# User Guide

This guide describes user-facing workflows present in the current application. The main workspace uses Monaco for Markdown source editing; Focus Mode uses a separate rich Markdown editor.

## Contents

- [Toolbar](#toolbar)
- [Open and edit documents](#open-and-edit-documents)
- [Focus Mode](#focus-mode)
- [Manage files and projects](#manage-files-and-projects)
- [Preview, appearance, and document statistics](#preview-appearance-and-document-statistics)
- [AI-assisted writing and translation](#ai-assisted-writing-and-translation)
- [Configure AI providers](#configure-ai-providers)
- [Review AI changes](#review-ai-changes)
- [Import and convert files](#import-and-convert-files)
- [Tables and slash commands](#tables-and-slash-commands)
- [BibTeX citation lookup](#bibtex-citation-lookup)
- [Export and publication](#export-and-publication)
- [Troubleshooting](#troubleshooting)

## Toolbar

Most toolbar buttons show only an icon. Hover over a button to see its name and, when it has one, its keyboard shortcut; screen readers announce the same name. Export formats and font-size controls keep their text, because the text is the information.

| Icon | Name | What it does |
| --- | --- | --- |
| 📂 | Open file | Opens a supported document in a new tab. |
| 🗂️ | Open project folder | Opens a local folder in the Explorer. |
| 💾 | Save | Saves the active tab. |
| HTML / PDF / DOCX | Export | Exports the active document in that format. |
| 🌐 | Open rendered preview in browser | Opens the rendered document in your web browser. |
| A- / A+ and the number field | Font size | Changes the editor font size (8 to 72). |
| 🧠 | Focus Mode | Switches between the main editor and Focus Mode. |
| 👁 | Preview | Shows or hides the preview panel. |
| 🤖 | AI Assistant | Shows or hides the AI panel. |
| 📚 | Citations | Shows or hides the BibTeX citation panel. |
| 📝 | Publication | Shows or hides the publication panel. |
| 🌙 / ☀️ | Dark or light mode | Switches the color theme. |

Toggle buttons are highlighted while their mode or panel is on. When the window is narrow, the toolbar wraps onto a second row instead of hiding buttons.

## Open and edit documents

Markdown Reader provides a tabbed Markdown editor and rendered preview. Use **File → Open File** or the toolbar's **Open file** (📂) button to select a supported document. Markdown, Markdown extensions, and plain-text files open directly. Supported non-Markdown formats are converted to Markdown when their converter is available.

The main editor uses Monaco in Markdown mode. It supports line numbers, word wrapping, code folding, and configurable font size. The toolbar's font-size field accepts whole-number values from 8 to 72. Tabs can represent files on disk or untitled documents. Unsaved changes are indicated in the status bar.

## Focus Mode

Choose **Focus Mode** (🧠) in the toolbar to switch from the split Monaco-and-preview workspace to a distraction-reduced rich Markdown editor. Focus Mode uses Milkdown/Crepe with CommonMark, GitHub Flavored Markdown, math, history, and an editor slash-command menu. The Explorer and right-hand side panel are hidden while Focus Mode is active; the app toolbar and document tabs remain available.

The Focus Mode editor handles Markdown paste separately from rich HTML clipboard content. When pasted plain text contains recognizable Markdown syntax, it can parse that text as Markdown rather than inserting visible source markers. Richly formatted HTML clipboard content remains on the normal rich-paste path.

Use the toolbar's **Focus Mode** control again to return to the main editor workspace. The main editor's Monaco-specific search, replace, formatting, and table shortcuts are documented in the [keyboard shortcut reference](./KeyboardShortcuts.md); not every Monaco action is available from the Focus Mode editor.

## Manage files and projects

Use the File menu or toolbar to create, open, save, and close document tabs. The **Open project folder** (🗂️) toolbar button opens a local folder. The Explorer displays its directory tree; folders load their entries when expanded, and selecting a file opens it in a tab.

Opening a project also recursively opens supported files under that folder into editor tabs. For a large project, this can create many tabs. The project translation and Project Work tools use the selected project folder as their scope. Close the project from the Explorer when you no longer need that folder context.

Project operations are intended for desktop use because they require access to local folders. If a native folder picker is unavailable in a browser-based development session, the app may prompt for an absolute folder path.

See the [Project Workflows guide](./ProjectWorkflows.md) for project translation, multi-file AI changes, and publication preparation.

## Preview, appearance, and document statistics

The Preview panel renders the current Markdown document so you can check headings, links, tables, code blocks, and other Markdown content while editing. Use the view controls to change the editor/preview split, show the preview, or open the rendered document in a browser. Dark mode is available from **View → Toggle Dark Mode**.

The status bar displays the active file name, an unsaved-change indicator, word count, character count including spaces, heading count, and estimated reading time. The reading-time value is an estimate based on the application's word-count calculation.

Keyboard shortcuts use **Command** as the primary modifier on macOS and **Ctrl** on Windows/Linux. See the [keyboard shortcuts reference](./KeyboardShortcuts.md) for the defaults and notes about the main editor versus Focus Mode.

## AI-assisted writing and translation

Open the **AI Assistant** (🤖) toolbar panel. It contains **Chat**, **Work**, **Translate**, and **Settings** tabs.

In Chat, ask questions about the active document or selected text. When the AI returns a proposed document action, inspect it and use the displayed Apply control to apply it. Some built-in slash commands can also be entered in the chat input.

The Translate tab supports:

- Translating the full active document or the current text selection.
- Full Text mode for one translation result.
- Sentence Pairs mode, which presents source and translated text in pairs and reports batch progress.
- Stopping an in-progress sentence-pair translation. A stopped task may leave only the batches completed so far in the preview.
- Applying the translation to the document/selection or inserting it below the relevant content using the available controls.

Choose a source language or **Auto Detect**, then select a target language. Project-wide translation is also available near the top of this same Translate tab when a project folder is open; its separate file-level workflow is described in the [Project Workflows guide](./ProjectWorkflows.md).

For local notes retrieval in Chat, see [AI panel and Notes Context](./ProjectAIWorkflows.md). For active-document Work and project Work, see [Review AI changes](#review-ai-changes) and the [AI panel guide](./ProjectAIWorkflows.md).

## Configure AI providers

Open the AI panel's **Settings** tab to configure the provider, model, endpoint, and credentials. Available choices include OpenAI, Anthropic, OpenRouter, and OpenAI-compatible endpoints. The **Local** provider supports compatible servers such as LM Studio and Ollama, as well as a custom endpoint.

For an OpenAI-compatible endpoint, select one of the configured base URL choices, such as NVIDIA or Groq. For the Local provider, choose LM Studio, Ollama, or Custom. A custom endpoint needs its base URL before you can fetch its model list. Use **Fetch Models** to query the selected endpoint when the control is available, then choose and save the model.

Provider and model preferences are stored in the per-user settings file. API keys can be stored in the operating-system credential store through keyring when available; environment variables can also provide credentials. The Settings tab reports whether a key is saved, supplied by the environment, or unavailable. Local endpoints usually do not need an API key unless the server is configured to require one.

Provider model availability, API behavior, rate limits, and costs are controlled by the provider. Multi-provider failover depends on configured fallback providers and on the type of error returned; it is not a guarantee that every request will succeed.

## Review AI changes

The application has more than one AI editing path:

- **Chat suggestions:** When Chat returns an actionable suggestion, the panel displays an Apply control. Inspect the suggestion before applying it.
- **Active-document Work:** In the Work tab, choose **Active document**, enter an instruction, and choose **Apply Changes**. The returned replacement is applied to the active document if that document has not changed while the request was running. In the main Monaco editor, the result is applied as one editor change that can be undone through the editor's undo history; it is not a separate multi-file diff review.
- **Project Work:** Choose **Open project** in the Work scope selector. The AI inspects requested project files and prepares proposed changes with file-by-file diffs. Review the diffs before selecting **Accept changes into editor**. Applying stages the contents in editor tabs; it does not write the files directly to disk. Save the reviewed tabs when ready.

Project Work has its own validation and staging behavior; see [Project Workflows](./ProjectWorkflows.md).

## Import and convert files

Markdown Reader opens Markdown and plain text directly. The backend handles HTML, PDF, and DOCX through native converters. Additional formats are converted through the optional Microsoft MarkItDown integration. Supported extensions include:

| Category | Formats |
| --- | --- |
| Text and web | Markdown, TXT, HTML |
| Documents | PDF, DOCX |
| Office and data | PPT, PPTX, XLS, XLSX, CSV |
| Structured and e-book | EPUB, XML |
| Archives | ZIP |
| Image and OCR | JPG, JPEG, PNG, GIF, BMP, TIFF |
| Audio | WAV, MP3 |
| Other | Outlook MSG, Jupyter IPYNB |

MarkItDown availability depends on the installed optional dependencies. Normal PDF opening uses PyMuPDF. Docling is available through a separate backend conversion endpoint, but the current frontend does not expose it as a selectable PDF-import mode. Conversion can lose layout or information, particularly with scanned PDFs, complex tables, images, and Office documents. Inspect the resulting Markdown before using it as a source of truth.

The project currently requires Python 3.11 to 3.13; Python 3.14 is excluded because some optional MarkItDown dependencies do not yet provide compatible wheels.

## Tables and slash commands

Use **Table → Insert Table** or the `/insert-table` slash command to create a Markdown table. The main editor's table command inserts a local Markdown table and does not require an AI request.

In the main editor, type `/` at the start of a line or after whitespace to open the slash-command menu:

| Command | Result |
| --- | --- |
| `/summarize` | Summarizes the document with AI |
| `/translate` | Opens the Translate tab in the AI panel |
| `/format` | Formats text with AI |
| `/toc` | Generates a table of contents with AI |
| `/fix-code` | Cleans up Markdown code fences with AI |
| `/insert-table` | Inserts a table locally |
| `/insert-toc` | Builds a table of contents locally from document headings |

Use the arrow keys to select a command, Enter to execute it, and Escape to close the menu. Focus Mode has its own editor slash menu for the available commands.

## BibTeX citation lookup

The Cite panel can load a BibTeX `.bib` library. Search entries by citation key, author, title, year, publication venue, or entry type, then choose an entry to insert a citation-key marker such as `[@doe2024]` at the editor cursor.

In the desktop app, use **Select** to choose a BibTeX file with the native file picker. In browser-based development, the selected file is uploaded to the local backend and becomes the active citation library.

The current feature is a BibTeX entry browser and citation-key insertion helper. Do not assume that the app generates a formatted bibliography or converts citation markers into a publication-style reference list during export; review and complete the citation workflow required by your target publication separately.

## Export and publication

The toolbar's export controls support HTML, PDF, and DOCX for the current document. In the desktop app, the save dialog lets you choose the output path. Browser-based development supports direct HTML download; PDF and DOCX export require the desktop save-dialog flow.

PDF export uses WeasyPrint when its native dependencies are available and can fall back to PyMuPDF with simpler layout. See [Technical documentation](./TECHNICAL.md#pdf-export-dependencies), [macOS setup](./PrepareForMacUser.md), and [Windows setup](./PrepareForWindowsUser.md).

The **Publication** panel combines selected open document tabs into a publication draft. Select the tabs, arrange their order, and prepare the draft. The backend applies deterministic formatting, resolves relative image paths against each source document's folder, and generates a table of contents from the combined headings. This is not an AI editorial workflow. Inspect the combined result before export. Publication HTML can be downloaded in browser development; publication PDF export requires the desktop app.

For multi-file publication details, see [Project Workflows](./ProjectWorkflows.md).

## Troubleshooting

### The app does not start

Check the Python and Node.js versions, install the prerequisites in the main [README](https://github.com/petertzy/markdown-reader/blob/main/README.MD), and make sure `frontend/.env.local` exists. Run the platform-appropriate development helper from the repository root.

### The backend port is already in use

The development helper starts with port 8000 and tries nearby ports if it cannot bind the requested port. Check the helper's output for the actual backend port. To request a port, set `MARKDOWN_READER_BACKEND_PORT` before launching it.

### AI requests fail

Confirm the selected provider, model, endpoint, and credentials. Local model servers must be running and reachable at the configured URL. Check provider-specific limits and errors; fallback behavior depends on the configured providers and error type.

### PDF export has missing libraries or layout differences

Install the native dependencies described in the platform-specific setup guide. If WeasyPrint cannot load, the app may use the PyMuPDF fallback, which can produce simpler layouts.

### Import results are incomplete

Some conversions depend on optional third-party packages and on the structure of the source file. Confirm that the relevant dependencies are installed and inspect the converted Markdown, especially for complex PDFs, scanned images, tables, and Office documents.

## Related documentation

- [AI panel and Notes Context](./ProjectAIWorkflows.md)
- [Project workflows](./ProjectWorkflows.md)
- [Keyboard shortcuts](./KeyboardShortcuts.md)
- [Technical documentation](./TECHNICAL.md)
- [macOS setup](./PrepareForMacUser.md)
- [Windows setup](./PrepareForWindowsUser.md)
- [Code signing and distribution](./CodeSigningAndDistribution.md)
- [Contributing guide](https://github.com/petertzy/markdown-reader/blob/main/CONTRIBUTING.md)
