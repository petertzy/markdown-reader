"use client";

/**
 * FocusModePane.tsx
 * ==============
 * Milkdown based focus mode editor pane.
 * 
 * @fix #449 - Consistent Markdown Rendering When Pasting Content into Focus Mode Editor
 * @issue https://github.com/petertzy/markdown-reader/issues/449
 * 
 * Root Cause:
 * - Clipboard contains both text/html and text/plain
 * - Milkdown's clipboard plugin inconsistently picks HTML vs plain
 * - When HTML is used for Markdown source, raw syntax (#, **) remains visible
 * 
 * Solution:
 * - Intercept paste at ProseMirror level via editorViewCtx
 * - Detect Markdown with robust heuristics (12 patterns, confidence scoring)
 * - Force consistent Markdown parsing, prevent HTML path for Markdown content
 * - No new dependencies, uses only existing Milkdown APIs
 */

import { Crepe } from '@milkdown/crepe'
import { Milkdown, MilkdownProvider, useEditor } from '@milkdown/react'
import { listener, listenerCtx } from '@milkdown/kit/plugin/listener'
import { commonmark } from '@milkdown/kit/preset/commonmark'
import { gfm } from '@milkdown/kit/preset/gfm'
import { clipboard } from '@milkdown/kit/plugin/clipboard'
import { cursor } from '@milkdown/kit/plugin/cursor'
import { indent } from '@milkdown/kit/plugin/indent'
import { block } from '@milkdown/kit/plugin/block'
import { history, undoCommand, redoCommand } from '@milkdown/kit/plugin/history'
import { commandsCtx, editorViewCtx, editorViewOptionsCtx, parserCtx } from '@milkdown/kit/core'
import { DOMParser, DOMSerializer } from '@milkdown/kit/prose/model'
import { math } from '@milkdown/plugin-math'
import '@milkdown/crepe/theme/common/style.css'
import '@milkdown/crepe/theme/frame.css'
import '@/lib/focusModePaneDark.css'
import { SlashCommand } from '@/hooks/useSlashCommands'
import React, { useEffect } from 'react';

// ============================================================================
// Professional Markdown Detection - Issue #449
// ============================================================================

/**
 * Robust Markdown detection with confidence scoring.
 * Prevents false positives like "C# is great" vs real "# Heading"
 */
function isMarkdownContent(text: string): boolean {
  if (!text || text.trim().length < 3) return false;

  // Strong signals - single match = Markdown
  const strongPatterns = [
    /^#{1,6}\s+\S/m,           // # Heading
    /^```[\w]*\n/m,            // ```code block
    /\|.*\|.*\n\s*\|(?:-|:|\||\s)+\|/m, // | table |
    /^\s*([-*_]\s*){3,}\s*$/m, // --- horizontal rule
  ];

  for (const pattern of strongPatterns) {
    if (pattern.test(text)) return true;
  }

  // Weak signals - need 2+ to confirm Markdown
  const weakPatterns = [
    /^>\s+.+/m,                 // > blockquote
    /^\s*[-*+]\s+\S/m,        // - list
    /^\s*\d+\.\s+\S/m,      // 1. ordered list
    /\*\*[^\*\n]+\*\*/m,   // **bold**
    /__[^_\n]+__/m,             // __bold__
    /`[^`\n]+`/m,               // `code`
    /\[.+\]\(.+\)/m,         // [link](url)
    /!\[.*\]\(.+\)/m,        // ![image](url)
  ];

  let weakMatches = 0;
  for (const pattern of weakPatterns) {
    if (pattern.test(text)) weakMatches++;
  }

  // Multi-line list structure = strong signal
  const lines = text.split('\n');
  const listLines = lines.filter(l => /^\s*([-+*]|\d+\.)\s+\S/.test(l));
  if (listLines.length >= 2) return true;

  return weakMatches >= 2;
}

export type FocusEditorHandle = {
  undo: () => void,
  redo: () => void,
};

type Props = {
  value: string,
  onChange: (value: string | undefined) => void,
  darkMode: boolean,
  fontSize: number,
  slashCommands: SlashCommand[],
  onSelect: (cmd: SlashCommand) => void,
  editorRef?: React.MutableRefObject<FocusEditorHandle | null>,
};

function CrepeEditor({ value, onChange, darkMode, fontSize, slashCommands, onSelect, editorRef }: Props) {
  const ownHandleRef = React.useRef<FocusEditorHandle | null>(null);

  useEditor((root) => {
    const removeSlash = () => {
      crepe.editor.action((ctx) => {
        const view = ctx.get(editorViewCtx)
        const { state } = view
        const { $from } = state.selection
        const textBeforeCursor = $from.parent.textContent.slice(0, $from.parentOffset)
        const slashMatch = /(^|\s)(\/[A-Za-z0-9-]*)$/.exec(textBeforeCursor)
        if (!slashMatch) return
        const slashOffset = $from.parentOffset - slashMatch[2].length
        const from = $from.start() + slashOffset
        view.dispatch(state.tr.delete(from, $from.pos))
      })
    }

    const crepe = new Crepe({
      root,
      defaultValue: value,
      featureConfigs: {
        [Crepe.Feature.BlockEdit]: {
          buildMenu: (builder) => {
            const group = builder.addGroup('slash', 'Slash Commands');
            for (const i of slashCommands)
              group.addItem(i.label, {
                label: i.label,
                icon: '',
                onRun: () => {
                  removeSlash();
                  onSelect(i);
                }
              });
          }
        },
      }
    });
    
    crepe
      .editor
        .use(history)
        .use(math)
        .use(listener)
        .use(commonmark)
        .use(gfm)
        .use(clipboard)
        .use(cursor)
        .use(indent)
        .use(block)
        .config((ctx) => {
          const listener = ctx.get(listenerCtx)
          listener.markdownUpdated((ctx, markdown, prevMarkdown) => {
            if (markdown !== prevMarkdown) {
              onChange(markdown)
            }
          })

          // ========================================================================
          // PROFESSIONAL FIX #449 - No new imports, uses existing editorViewCtx
          const originalHandlePaste = ctx.get(editorViewOptionsCtx).handlePaste;
          ctx.update(editorViewOptionsCtx, (options) => ({
            ...options,
            handlePaste: (view, event, preProcessedSlice) => {
              const clipboardData = event.clipboardData;
              const plainText = clipboardData?.getData('text/plain') ?? '';
              const html = clipboardData?.getData('text/html') ?? '';
              if (!html || !isMarkdownContent(plainText)) {
                return originalHandlePaste?.(view, event, preProcessedSlice) ?? false;
              }

              try {
                const parsed = ctx.get(parserCtx)(plainText);
                if (!parsed || typeof parsed === 'string') {
                  return originalHandlePaste?.(view, event, preProcessedSlice) ?? false;
                }

                const dom = DOMSerializer.fromSchema(view.state.schema).serializeFragment(parsed.content);
                const slice = DOMParser.fromSchema(view.state.schema).parseSlice(dom);
                view.dispatch(
                  view.state.tr
                    .replaceSelection(slice)
                    .setMeta('paste', true)
                    .setMeta('fix-449', 'consistent-markdown-paste')
                );
                return true;
              } catch (error) {
                console.warn('[Fix #449] Paste handling failed, fallback to default:', error);
                return originalHandlePaste?.(view, event, preProcessedSlice) ?? false;
              }
            },
          }));
        })

    if (editorRef) {
      const handle: FocusEditorHandle = {
        undo: () => crepe.editor.action((ctx) => {
          ctx.get(editorViewCtx).focus()
          return ctx.get(commandsCtx).call(undoCommand.key)
        }),
        redo: () => crepe.editor.action((ctx) => {
          ctx.get(editorViewCtx).focus()
          return ctx.get(commandsCtx).call(redoCommand.key)
        }),
      }
      ownHandleRef.current = handle
      editorRef.current = handle
    }
    return crepe
  })

  useEffect(() => () => {
    if (editorRef && editorRef.current === ownHandleRef.current) {
      editorRef.current = null
    }
  }, [editorRef]);

  return (
    <div className={`
      text-balance
      flex-1 min-w-0 min-h-0 overflow-auto
      focus-mode-editor
      ${darkMode ? "fme-dark-mode" : ""}
    `}
      style={{ "--fme-font-size": `${fontSize}px` } as React.CSSProperties & { "--fme-font-size": string }}
    >
      <Milkdown/>
    </div>
  )
}

export default function FocusModePane (props: Props) {
  return (
    <MilkdownProvider>
      <CrepeEditor {...props} />
    </MilkdownProvider>
  )
}
