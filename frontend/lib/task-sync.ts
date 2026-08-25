const TASK_SYNC_KEY = "ai-life-task-sync";

export function announceTaskUpdate() {
  if (typeof window === "undefined") return;
  const detail = { updatedAt: Date.now() };
  window.localStorage.setItem(TASK_SYNC_KEY, JSON.stringify(detail));
}

export function subscribeToTaskUpdates(refresh: () => void) {
  if (typeof window === "undefined") return () => undefined;
  const onStorage = (event: StorageEvent) => {
    if (event.key === TASK_SYNC_KEY && event.newValue) refresh();
  };
  const onFocus = () => refresh();
  const onVisibilityChange = () => {
    if (document.visibilityState === "visible") refresh();
  };
  window.addEventListener("storage", onStorage);
  window.addEventListener("focus", onFocus);
  document.addEventListener("visibilitychange", onVisibilityChange);
  return () => {
    window.removeEventListener("storage", onStorage);
    window.removeEventListener("focus", onFocus);
    document.removeEventListener("visibilitychange", onVisibilityChange);
  };
}
