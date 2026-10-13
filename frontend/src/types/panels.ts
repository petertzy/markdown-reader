export const PANELS = {
  PREVIEW: "preview",
  AI: "ai",
  CITATION: "citation",
} as const;

export type PanelId = (typeof PANELS)[keyof typeof PANELS] | null;
