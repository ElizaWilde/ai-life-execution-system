const USER_ID_KEY = "ai-life-user-id";
const DEFAULT_USER_ID = "1";

export function getStoredUserId(): string {
  if (typeof window === "undefined") {
    return DEFAULT_USER_ID;
  }
  // Temporary MVP identity until token authentication assigns the user.
  window.localStorage.setItem(USER_ID_KEY, DEFAULT_USER_ID);
  return DEFAULT_USER_ID;
}
