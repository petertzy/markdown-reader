# Keyboard Shortcuts

This page lists the default shortcuts defined by the application. The primary modifier is **Command** on macOS and **Ctrl** on Windows and Linux. The application does not currently expose a shortcut-customization interface.

## Files and tabs

| Action | macOS | Windows/Linux |
| --- | --- | --- |
| New file | Command+N | Ctrl+N |
| Open file | Command+O | Ctrl+O |
| Save file | Command+S | Ctrl+S |
| Close current tab | Command+W | Ctrl+W |
| Close all tabs | Command+Shift+W | Ctrl+Shift+W |

## Editing and formatting

| Action | macOS | Windows/Linux |
| --- | --- | --- |
| Undo | Command+Z | Ctrl+Z |
| Redo | Command+Shift+Z | Ctrl+Y or Ctrl+Shift+Z |
| Search | Command+F | Ctrl+F |
| Replace | Command+Option+F | Ctrl+H |
| Bold | Command+B | Ctrl+B |
| Italic | Command+I | Ctrl+I |
| Underline | Command+U | Ctrl+U |
| Heading 1 | Command+1 | Ctrl+1 |
| Heading 2 | Command+2 | Ctrl+2 |
| Heading 3 | Command+3 | Ctrl+3 |
| Normal text | Command+0 | Ctrl+0 |
| Insert table | Command+Option+T | Ctrl+Alt+T |

## Export and view

| Action | macOS | Windows/Linux |
| --- | --- | --- |
| Export to HTML | Command+Option+H | Ctrl+Alt+H |
| Export to Word (DOCX) | Command+Option+D | Ctrl+Alt+D |
| Export to PDF | Command+Option+P | Ctrl+Alt+P |
| Toggle dark mode | F6 | F6 |
| Toggle AI panel | Command+Shift+A | Ctrl+Shift+A |
| Open preview in browser | Command+Option+B | Ctrl+Alt+B |
| Full-width editor | Command+Option+Left Arrow | Ctrl+Alt+Left Arrow |
| Balanced split view | Command+Option+Down Arrow | Ctrl+Alt+Down Arrow |
| Full-width preview | Command+Option+Right Arrow | Ctrl+Alt+Right Arrow |

The search, replace, formatting, and table shortcuts are tied to the main Monaco editor. Focus Mode uses a different rich editor and has its own slash-command menu; use the toolbar and Focus Mode's editor controls for actions that are not handled by Monaco. File-level and view-level shortcuts are application commands.

Shortcut execution respects editor focus. For example, an editor-scoped shortcut should not intercept native undo or typing while focus is in an ordinary text input such as the AI prompt field.

The main editor slash menu is separate from keyboard shortcuts: type `/` at the start of a line or after whitespace, use the arrow keys to select a command, Enter to execute it, and Escape to dismiss it. Focus Mode has its own slash-command menu.

## Related documentation

- [User guide](./UserGuide.md)
- [AI panel and Notes Context](./ProjectAIWorkflows.md)
- [Project workflows](./ProjectWorkflows.md)
