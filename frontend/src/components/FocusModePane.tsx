"use client";

/**
 * FocusModePane.tsx
 * ==============
 * Milkdown based focus mode editor pane.
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
import { commandsCtx, editorViewCtx } from '@milkdown/kit/core'
import { math } from '@milkdown/plugin-math'
import '@milkdown/crepe/theme/common/style.css'
import '@milkdown/crepe/theme/frame.css'
import '@/lib/focusModePaneDark.css'
import { SlashCommand } from '@/hooks/useSlashCommands'
import React, { useEffect } from 'react';

/**
 * Imperative undo/redo handle for the Focus Mode (Milkdown) editor.
 *
 * The homepage routes the `edit.undo` / `edit.redo` actions here while
 * Focus Mode is active, because `monacoRef` is null in that mode and the
 * Monaco-backed `runMonacoAction` would silently no-op (issue #341).
 */
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
  /** Shared handle the homepage uses to reach this editor's undo/redo. */
  editorRef?: React.MutableRefObject<FocusEditorHandle | null>,
};

function CrepeEditor({ value, onChange, darkMode, fontSize, slashCommands, onSelect, editorRef }: Props) {
  // Identity of the handle we published, so a stale instance's unmount cleanup
  // (e.g. tab-switch remount via the `key` prop) never nulls a newer instance's handle.
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
        })

    // Publish undo/redo to the shared handle (issue #341): the app-level
    // `edit.undo` / `edit.redo` actions must reach the Milkdown history while
    // Focus Mode is active instead of the (nulled) Monaco instance. Focus the
    // view first for parity with runMonacoAction's `mono.focus()`.
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

  // Clear the shared handle when the pane unmounts (e.g. leaving Focus Mode)
  // so callers fall back to Monaco instead of driving a destroyed editor.
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
