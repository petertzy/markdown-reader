export const PANELS = {
  PREVIEW: "preview",
  AI: "ai",
  CITATION: "citation",
  PUBLICATION: "publication",
} as const;

export type PanelId = (typeof PANELS)[keyof typeof PANELS] | null;

export function getPanelContent<T>(
  activePanel: PanelId,
  content: Record<Exclude<PanelId, null>, T>,
): T | null {
  return activePanel === null ? null : content[activePanel];
}

export function getPanelSplitAfterToggle(
  activePanel: PanelId,
  selectedPanel: Exclude<PanelId, null>,
): number {
  if (activePanel === selectedPanel) return 100;
  return selectedPanel === PANELS.PREVIEW ? 50 : 60;
}
