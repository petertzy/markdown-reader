export const PANELS = {
  AI: "ai",
  CITATION: "citation",
} as const;

export type PanelId = (typeof PANELS)[keyof typeof PANELS] | null;
