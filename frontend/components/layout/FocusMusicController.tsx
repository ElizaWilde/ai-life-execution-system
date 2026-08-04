"use client";

import { useEffect, useRef } from "react";
import {
  FOCUS_TIMER_EVENT,
  FOCUS_TIMER_KEY,
  readSharedFocusTimer,
  reconcileSharedFocusTimer,
  remainingSecondsAt,
  writeSharedFocusTimer,
} from "../../lib/focus-timer-sync";
import { api } from "../../lib/api";
import { syncFocusMusic } from "../../lib/focus-music";
import { SETTINGS_EVENT, SETTINGS_KEY, loadAppSettings } from "../../lib/settings";
import { playTimerCompleteSound } from "../../lib/timer-sound";

export default function FocusMusicController() {
  const finishingSessionRef = useRef<number | null>(null);

  useEffect(() => {
    const sync = () => {
      const settings = loadAppSettings();
      const current = readSharedFocusTimer();
      const durations = {
        focus: Math.max(1, Number(settings.focusMinutes) || 25) * 60,
        shortBreak: Math.max(1, Number(settings.shortBreak) || 5) * 60,
        longBreak: Math.max(1, Number(settings.longBreak) || 15) * 60,
        cycleCount: Math.min(12, Math.max(1, Number(settings.cycleCount) || 4)),
      };
      const timer = current ? reconcileSharedFocusTimer(current, Date.now(), durations) : null;
      if (current && timer && (
        current.mode !== timer.mode ||
        current.running !== timer.running ||
        current.endAt !== timer.endAt ||
        current.completedFocusSessions !== timer.completedFocusSessions
      )) {
        if (current.running && current.endAt !== null && current.endAt <= Date.now()) {
          void playTimerCompleteSound(current.endAt);
        }
        writeSharedFocusTimer(timer);
      }
      const shouldPlay = Boolean(
        timer?.running && timer.mode === "focus" && remainingSecondsAt(timer) > 0,
      );
      void syncFocusMusic(shouldPlay, settings).catch(() => undefined);

      const completedCycle = Boolean(
        timer?.studySessionId &&
        timer.accumulatedFocusSeconds > 0 &&
        !timer.running &&
        timer.mode === "focus" &&
        timer.completedFocusSessions === 0,
      );
      if (completedCycle && timer && finishingSessionRef.current !== timer.studySessionId) {
        const sessionId = timer.studySessionId as number;
        const focusedSeconds = timer.accumulatedFocusSeconds;
        finishingSessionRef.current = sessionId;
        void api.finishSession({ session_id: sessionId, duration_seconds: focusedSeconds })
          .then(() => {
            const latest = readSharedFocusTimer();
            if (latest?.studySessionId === sessionId) {
              writeSharedFocusTimer({ ...latest, studySessionId: null, accumulatedFocusSeconds: 0 });
            }
          })
          .catch(() => undefined)
          .finally(() => {
            finishingSessionRef.current = null;
          });
      }
    };
    const syncStorage = (event: StorageEvent) => {
      if (event.key === FOCUS_TIMER_KEY || event.key === SETTINGS_KEY) sync();
    };

    sync();
    const interval = window.setInterval(sync, 1000);
    window.addEventListener("storage", syncStorage);
    window.addEventListener(FOCUS_TIMER_EVENT, sync);
    window.addEventListener(SETTINGS_EVENT, sync);
    return () => {
      window.clearInterval(interval);
      window.removeEventListener("storage", syncStorage);
      window.removeEventListener(FOCUS_TIMER_EVENT, sync);
      window.removeEventListener(SETTINGS_EVENT, sync);
    };
  }, []);

  return null;
}
