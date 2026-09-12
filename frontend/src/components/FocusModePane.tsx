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
import { history } from '@milkdown/kit/plugin/history'
import { editorViewCtx } from '@milkdown/kit/core'
import { math } from '@milkdown/plugin-math'
import '@milkdown/crepe/theme/common/style.css'
import '@milkdown/crepe/theme/frame.css'
import '@/lib/focusModePaneDark.css'
import { SlashCommand } from '@/hooks/useSlashCommands'
import React from 'react';

type Props = {
  value: string,
  onChange: (value: string | undefined) => void,
  darkMode: boolean,
  fontSize: number,
  slashCommands: SlashCommand[],
  onSelect: (cmd: SlashCommand) => void
};

function CrepeEditor({ value, onChange, darkMode, fontSize, slashCommands, onSelect }: Props) {
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
    return crepe
  })

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
