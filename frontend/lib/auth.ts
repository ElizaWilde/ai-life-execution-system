const USER_ID_KEY = "ai-life-user-id";

export function getStoredUserId(): string {
  if (typeof window === "undefined") {
    return "1";
  }
  return window.localStorage.getItem(USER_ID_KEY) || "1";
}

export function setStoredUserId(userId: string): void {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(USER_ID_KEY, userId);
}
