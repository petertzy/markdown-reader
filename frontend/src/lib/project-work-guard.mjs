export function projectTabsAreFresh(snapshot, current) {
  return snapshot.length === current.length && snapshot.every((tab, index) => {
    const currentTab = current[index];
    return tab.id === currentTab.id && tab.filePath === currentTab.filePath && tab.content === currentTab.content;
  });
}

export function taskMatchesProject(taskRoot, projectRoot) {
  return taskRoot === projectRoot;
}

// Project Work requests can outlive the UI state that started them. A token
// makes completions from an older request harmless after a project switch,
// discard, or newer request.
export function createProjectWorkRunGuard() {
  let generation = 0;

  return {
    begin() {
      generation += 1;
      return generation;
    },
    invalidate() {
      generation += 1;
    },
    current() {
      return generation;
    },
    isCurrent(token) {
      return token === generation;
    },
  };
}
