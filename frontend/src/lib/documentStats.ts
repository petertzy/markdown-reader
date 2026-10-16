import { Markdown } from "@/lib/api";

export async function fetchDocumentStats(content: string) {
  if (!content.trim()) {
    return { words: 0, chars_with_spaces: 0, chars_without_spaces: 0, heading_count: 0, reading_time: "< 1 min read" };
  }
  return Markdown.wordCount(content);
}