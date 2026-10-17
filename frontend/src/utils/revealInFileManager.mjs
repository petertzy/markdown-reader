export async function revealInFileManager(filePath, revealItem) {
  if (!filePath) {
    throw new Error("No file path provided to reveal.");
  }
  await revealItem(filePath);
}
