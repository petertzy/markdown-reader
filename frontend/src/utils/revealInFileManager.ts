import { revealItemInDir } from "@tauri-apps/plugin-opener";

/**
 * Reveals a file in the system's file manager (Finder on macOS, Explorer on Windows).
 * Accepts native Windows (backslash) and POSIX (forward slash) paths.
 */
export async function revealInFileManager(filePath: string): Promise<void> {
  if (!filePath) {
    throw new Error("No file path provided to reveal.");
  }
  await revealItemInDir(filePath);
}