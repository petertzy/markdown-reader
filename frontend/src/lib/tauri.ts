export function isTauriRuntime() {
  return (
    typeof window !== "undefined" &&
    ("__TAURI_INTERNALS__" in window ||
      "__TAURI__" in window ||
      window.location.hostname === "tauri.localhost" ||
      window.navigator.userAgent.includes("Tauri"))
  );
}

export function shouldShowPackagedBackendStatus() {
  return process.env.NODE_ENV !== "development" && isTauriRuntime();
}
