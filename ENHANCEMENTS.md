# Markdown Editor Enhancements

This document describes the new features added to the Markdown Reader application.

## Overview

Six major feature enhancements have been implemented to improve the editing experience:

1. Syntax Highlighting for Code Blocks
2. Real-time Split Preview
3. Keyboard Shortcuts for Formatting
4. Customizable Editor Themes
5. Section Reordering
6. Enhanced Undo/Redo

---

## 1. Syntax Highlighting for Code Blocks

### Description
Code blocks in the HTML preview now feature syntax highlighting powered by Pygments.

### Features
- Automatic language detection for code blocks
- Support for 500+ programming languages
- Theme-aware highlighting (monokai for dark themes, default for light themes)
- Works with fenced code blocks (```language)

### Usage
Simply write code blocks in your markdown:

```python
def hello():
    print("Hello, World!")
```

The preview will automatically apply syntax highlighting based on the specified language.

---

## 2. Real-time Split Preview

### Description
Toggle between full editor mode and split preview mode for live updates.

### Features
- Toggle via View → Toggle Split Preview menu
- Opens preview in browser for side-by-side viewing
- Automatic preview updates as you type
- Works with all themes

### Usage
1. Go to View → Toggle Split Preview
2. Arrange your browser window next to the editor
3. Edit your markdown and see changes in real-time

---

## 3. Keyboard Shortcuts for Formatting

### Description
Comprehensive keyboard shortcuts for common markdown formatting operations.

### Shortcuts

#### File Operations
- `Ctrl/Cmd + N` - New file
- `Ctrl/Cmd + S` - Save file
- `Ctrl/Cmd + Z` - Undo
- `Ctrl/Cmd + Y` - Redo (Cmd+Shift+Z on Mac)

#### Text Formatting
- `Ctrl/Cmd + B` - **Bold** (`**text**`)
- `Ctrl/Cmd + I` - *Italic* (`*text*`)
- `Ctrl/Cmd + U` - <u>Underline</u> (`<u>text</u>`)
- `Ctrl/Cmd + K` - Inline code (`` `code` ``)
- `Ctrl/Cmd + Shift + K` - Code block (` ```code``` `)
- `Ctrl/Cmd + L` - Insert link (`[text](url)`)

#### Headers
- `Ctrl/Cmd + H` - Toggle heading
- `Ctrl + 1` through `Ctrl + 6` - Set heading level (H1-H6)

#### Section Movement
- `Alt + Up` - Move section up
- `Alt + Down` - Move section down
- `Cmd+Opt+Up` - Move section up (Mac)
- `Cmd+Opt+Down` - Move section down (Mac)

### Usage
1. Select text you want to format
2. Press the corresponding keyboard shortcut
3. If no text is selected, a template is inserted

View all shortcuts via Edit → Keyboard Shortcuts menu.

---

## 4. Customizable Editor Themes

### Description
Choose from 7 pre-defined color themes to customize the editor appearance.

### Available Themes

1. **Default** - Classic light theme
   - Black text on white background
   - Standard selection colors

2. **Dark** - Modern dark theme
   - Light gray text on dark gray background
   - Reduced eye strain for night work

3. **Monokai** - Popular programmer theme
   - Cream text on charcoal background
   - High contrast, easy on eyes

4. **Solarized Light** - Scientifically designed light theme
   - Carefully balanced colors
   - Reduces brightness contrast

5. **Solarized Dark** - Scientifically designed dark theme
   - Same careful color balance as light version
   - Perfect for low-light environments

6. **Dracula** - Stylish dark theme
   - Purple-tinted dark background
   - Vibrant selection colors

7. **Nord** - Arctic-inspired theme
   - Cool blue-gray tones
   - Subtle and professional

### Usage
1. Go to View → Editor Theme
2. Select your preferred theme
3. Theme applies immediately to all open editors
4. Preview updates to match theme style

---

## 5. Section Reordering

### Description
Easily reorganize your markdown document by moving sections up and down.

### Features
- Detects sections based on markdown headers (#, ##, ###, etc.)
- Move entire sections with one command
- Preserves section content and formatting
- Works with nested sections

### Usage

#### Via Menu
1. Place cursor in the section you want to move
2. Go to Edit → Move Section Up/Down
3. Section moves to new position

#### Via Keyboard
1. Place cursor in the section
2. Press `Alt + Up` to move section up
3. Press `Alt + Down` to move section down
4. On Mac, use `Cmd+Opt+Up` and `Cmd+Opt+Down`

### Example
```markdown
# Section A
Content A

# Section B
Content B

# Section C
Content C
```

With cursor in Section B, pressing Alt+Up will result in:
```markdown
# Section B
Content B

# Section A
Content A

# Section C
Content C
```

---

## 6. Enhanced Undo/Redo

### Description
The existing undo/redo system has been integrated with all new features.

### Features
- Full undo/redo support for all formatting operations
- Works with section movement
- Works with theme changes
- Keyboard shortcuts: Ctrl/Cmd+Z (undo), Ctrl/Cmd+Y (redo)
- Preserves multiple levels of history

### Usage
1. Make changes to your document
2. Press Ctrl/Cmd+Z to undo
3. Press Ctrl/Cmd+Y to redo
4. All formatting and section movements are tracked

---

## Technical Details

### Modified Files
- `markdown_reader/ui.py` - Added UI components, themes, and keyboard shortcuts
- `markdown_reader/logic.py` - Added Pygments syntax highlighting integration

### Dependencies
- `pygments` - For code syntax highlighting (already in requirements.txt)
- All other features use existing dependencies

### Compatibility
- macOS: Full support including Command key shortcuts
- Windows: Full support with Ctrl key shortcuts
- Linux: Full support with Ctrl key shortcuts

---

## Tips and Best Practices

1. **Learn the keyboard shortcuts** - They significantly speed up editing
2. **Choose a theme that suits your environment** - Light themes for bright rooms, dark themes for dim lighting
3. **Use section movement** - Quickly reorganize long documents without cut/paste
4. **Enable split preview** - See changes in real-time as you type
5. **Specify language for code blocks** - Better syntax highlighting when language is specified

---

## Future Enhancements

Potential future improvements:
- Inline preview pane within the application
- Custom theme creation
- Undo history panel
- More section manipulation tools
- Collaborative editing features

---

## Support

For issues or feature requests, please visit the GitHub repository:
https://github.com/petertzy/markdown-reader
