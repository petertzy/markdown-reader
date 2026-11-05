# Documentation Index

Use this page to find the right guide. User-facing instructions describe workflows present in the current application. Feasibility studies, strategy notes, and cost comparisons may describe proposals or historical snapshots rather than the current implementation.

## Start here

- [Main README](https://github.com/petertzy/markdown-reader/blob/main/README.MD): project overview, desktop downloads, source setup, and links to detailed guides.
- [User Guide](./UserGuide.md): editor modes, file handling, AI assistance, importing, citations, and export.
- [AI Panel and Notes Context](./ProjectAIWorkflows.md): Chat, active-document Work, project Work, local note indexing, and provider/data handling.
- [Project Workflows](./ProjectWorkflows.md): project translation, multi-file AI changes, and publication drafts.
- [Keyboard Shortcuts](./KeyboardShortcuts.md): default application and editor shortcuts.
- [Contributing Guide](https://github.com/petertzy/markdown-reader/blob/main/CONTRIBUTING.md): prerequisites, development setup, validation, and contribution workflow.

## User and platform guides

- [Prepare for macOS](./PrepareForMacUser.md): Homebrew libraries used by WeasyPrint for PDF export.
- [Prepare for Windows](./PrepareForWindowsUser.md): MSYS2 UCRT64 libraries and DLL discovery for WeasyPrint.
- [Math Rendering Test File](./MathRenderingTestFile.md): sample content for checking mathematical notation rendering.

## Architecture and implementation

- [Technical Documentation](./TECHNICAL.md): architecture, local backend security, desktop content security policy, PDF export dependencies, and local packaging.
- [Code Signing and Distribution](./CodeSigningAndDistribution.md): current release workflow status and platform-signing research.

## Project governance

- [Project Roles](./ProjectRoles.md): project responsibilities and role assignments.

## Hosting and planning notes

- [Hosting Strategy](./HostingStrategy.md): historical Cloudflare Pages proposal, with a note on the current GitHub Pages distribution deployment.
- [AI Work Panel Feasibility Study](./AIWorkPanelFeasibilityStudy.md): design exploration, not a guarantee that each proposal is implemented.
- [Project Extensions Feasibility Study](./ProjectExtensionsFeasibilityStudy.md): extension concepts and planning notes.

## Maintenance notes

- Keep user instructions aligned with visible controls and implemented backend behavior.
- Update the detailed guide closest to a changed workflow, then update README only when the change belongs in the concise overview.
- Link to one source of truth rather than duplicating long procedures.
- Clearly label planning, feasibility, or historical research so it is not mistaken for shipped behavior.
