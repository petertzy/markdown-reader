/**
 * File extensions accepted for open/import, matching backend/routers/files.py.
 */

export const PLAIN_TEXT_EXTENSIONS = new Set(["md", "markdown", "txt"]);

export const NATIVE_CONVERTIBLE_EXTENSIONS = ["html", "htm", "pdf", "docx"];

export const MARKITDOWN_EXTENSIONS = [
  "pptx",
  "ppt",
  "xlsx",
  "xls",
  "csv",
  "epub",
  "xml",
  "zip",
  "wav",
  "mp3",
  "jpg",
  "jpeg",
  "png",
  "gif",
  "bmp",
  "tiff",
  "tif",
  "msg",
  "ipynb",
];

export const OPEN_FILE_EXTENSIONS = [
  ...PLAIN_TEXT_EXTENSIONS,
  ...NATIVE_CONVERTIBLE_EXTENSIONS,
  ...MARKITDOWN_EXTENSIONS,
];

export const SUPPORTED_FILE_EXTENSIONS = new Set(OPEN_FILE_EXTENSIONS);

export const OPEN_FILE_ACCEPT = OPEN_FILE_EXTENSIONS.map((ext) => `.${ext}`).join(",");

export function fileExtension(name: string) {
  return name.split(".").pop()?.toLowerCase() ?? "";
}

export function isPlainTextFile(name: string) {
  return PLAIN_TEXT_EXTENSIONS.has(fileExtension(name));
}

export function isSupportedFile(name: string) {
  return SUPPORTED_FILE_EXTENSIONS.has(fileExtension(name));
}

export function needsConversion(name: string) {
  const ext = fileExtension(name);
  return SUPPORTED_FILE_EXTENSIONS.has(ext) && !PLAIN_TEXT_EXTENSIONS.has(ext);
}
