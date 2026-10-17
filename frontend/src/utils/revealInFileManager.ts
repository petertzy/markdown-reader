type RevealItem = (path: string) => Promise<void>;

/**
 * Reveals a file in the system's file manager (Finder on macOS, Explorer on Windows).
 * Accepts native Windows (backslash) and POSIX (forward slash) paths.
 */
export async function revealInFileManager(
  filePath: string,
  reveal?: RevealItem,
): Promise<void> {
  if (!filePath) {
    throw new Error("No file path provided to reveal.");
  }
  const revealItem = reveal ?? (await import("@tauri-apps/plugin-opener")).revealItemInDir;
  await revealItem(filePath);
}
