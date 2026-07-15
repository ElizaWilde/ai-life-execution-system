"use client";

import { useEffect } from "react";
import { SETTINGS_EVENT, loadAppSettings } from "../../lib/settings";

export default function SettingsSync() {
  useEffect(() => {
    const apply = () => {
      const settings = loadAppSettings();
      document.documentElement.dataset.theme = settings.theme;
      document.documentElement.style.colorScheme = settings.theme === "auto" ? "light dark" : settings.theme;
    };
    apply();
    window.addEventListener("storage", apply);
    window.addEventListener(SETTINGS_EVENT, apply);
    return () => {
      window.removeEventListener("storage", apply);
      window.removeEventListener(SETTINGS_EVENT, apply);
    };
  }, []);
  return null;
}
