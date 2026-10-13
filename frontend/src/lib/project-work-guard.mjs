export function projectTabsAreFresh(snapshot, current) {
  return snapshot.length === current.length && snapshot.every((tab, index) => {
    const currentTab = current[index];
    return tab.id === currentTab.id && tab.filePath === currentTab.filePath && tab.content === currentTab.content;
  });
}
