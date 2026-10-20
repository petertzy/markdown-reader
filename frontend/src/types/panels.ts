export const PANELS = {
  PREVIEW: "preview",
  AI: "ai",
  CITATION: "citation",
  PUBLICATION: "publication",
  EXPLORER: "explorer",
} as const;

export type PanelId = (typeof PANELS)[keyof typeof PANELS] | null;
