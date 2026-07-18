import { useEffect, useState } from "react";

export type AppSettings = {
  name: string;
  email: string;
  timezone: string;
  weekStart: string;
  focusMinutes: string;
  shortBreak: string;
  longBreak: string;
  cycleCount: string;
  workload: string;
  theme: "light" | "dark" | "auto";
  tone: string;
  strictness: string;
  adjustment: string;
  proactive: boolean;
  focusMatters: boolean;
  protectDeepWork: boolean;
  learnFromFeedback: boolean;
  integrations: string[];
};

export const SETTINGS_KEY = "ai-life-settings";
export const SETTINGS_EVENT = "ai-life-settings-change";

export const defaultSettings: AppSettings = {
  name: "AI Life User",
  email: "user@example.com",
  timezone: "Asia/Singapore",
  weekStart: "Monday",
  focusMinutes: "25",
  shortBreak: "5",
  longBreak: "15",
  cycleCount: "4",
  workload: "medium",
  theme: "light",
  tone: "supportive",
  strictness: "balanced",
  adjustment: "moderate",
  proactive: true,
  focusMatters: true,
  protectDeepWork: true,
  learnFromFeedback: true,
  integrations: [],
};

export function loadAppSettings(): AppSettings {
  if (typeof window === "undefined") return defaultSettings;
  try {
    const stored = window.localStorage.getItem(SETTINGS_KEY);
    return stored ? { ...defaultSettings, ...JSON.parse(stored) as Partial<AppSettings> } : defaultSettings;
  } catch {
    return defaultSettings;
  }
}

export function saveAppSettings(settings: AppSettings) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
  window.dispatchEvent(new CustomEvent<AppSettings>(SETTINGS_EVENT, { detail: settings }));
}

export function useAppSettings() {
  const [settings, setSettings] = useState<AppSettings>(defaultSettings);

  useEffect(() => {
    const sync = () => setSettings(loadAppSettings());
    sync();
    window.addEventListener("storage", sync);
    window.addEventListener(SETTINGS_EVENT, sync);
    return () => {
      window.removeEventListener("storage", sync);
      window.removeEventListener(SETTINGS_EVENT, sync);
    };
  }, []);

  return settings;
}

export function workloadMinutes(workload: string) {
  if (workload === "light") return 180;
  if (workload === "high") return 480;
  return 360;
}

export function orderByWeekStart<T>(items: T[], dateOf: (item: T) => string, weekStart: string) {
  const startDay = weekStart === "Sunday" ? 0 : 1;
  return [...items].sort((left, right) => {
    const leftDay = new Date(`${dateOf(left)}T00:00:00`).getDay();
    const rightDay = new Date(`${dateOf(right)}T00:00:00`).getDay();
    return ((leftDay - startDay + 7) % 7) - ((rightDay - startDay + 7) % 7);
  });
}
