const CHECK_IN_SYNC_KEY = "ai-life-check-in-sync";

export function announceCheckInUpdate(date: string) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(
    CHECK_IN_SYNC_KEY,
    JSON.stringify({ date, updatedAt: Date.now() }),
  );
}

export function subscribeToCheckInUpdates(date: string, refresh: () => void) {
  if (typeof window === "undefined") return () => undefined;

  const onStorage = (event: StorageEvent) => {
    if (event.key !== CHECK_IN_SYNC_KEY || !event.newValue) return;
    try {
      const update = JSON.parse(event.newValue) as { date?: string };
      if (update.date === date) refresh();
    } catch {
      // Ignore malformed synchronization messages.
    }
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
