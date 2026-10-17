import { revealInFileManager as revealPathInFileManager } from "./revealInFileManager.mjs";

/**
 * Reveals a file in the system's file manager (Finder on macOS, Explorer on Windows).
 * Accepts native Windows (backslash) and POSIX (forward slash) paths.
 */
export async function revealInFileManager(
  filePath: string,
): Promise<void> {
  const { revealItemInDir } = await import("@tauri-apps/plugin-opener");
  await revealPathInFileManager(filePath, revealItemInDir);
}
