export const FOCUS_TIMER_KEY = "ai-life-dashboard-focus-timer-v1";
export const FOCUS_TIMER_EVENT = "ai-life-focus-timer-change";

export type SharedFocusTimerState = {
  mode: "focus" | "shortBreak" | "longBreak";
  remainingSeconds: number;
  phaseDurationSeconds: number;
  running: boolean;
  endAt: number | null;
  completedFocusSessions: number;
  accumulatedFocusSeconds: number;
  studySessionId: number | null;
};

export type SharedTimerDurations = {
  focus: number;
  shortBreak: number;
  longBreak: number;
  cycleCount: number;
};

export function readSharedFocusTimer(): SharedFocusTimerState | null {
  if (typeof window === "undefined") return null;
  try {
    const value = JSON.parse(window.localStorage.getItem(FOCUS_TIMER_KEY) ?? "null") as Partial<SharedFocusTimerState> | null;
    if (!value || !["focus", "shortBreak", "longBreak"].includes(value.mode ?? "")) return null;
    const phaseDurationSeconds = Math.max(1, Number(value.phaseDurationSeconds) || 1);
    return {
      mode: value.mode as SharedFocusTimerState["mode"],
      remainingSeconds: Math.min(phaseDurationSeconds, Math.max(0, Number(value.remainingSeconds) || 0)),
      phaseDurationSeconds,
      running: Boolean(value.running && Number.isFinite(value.endAt)),
      endAt: value.running && Number.isFinite(value.endAt) ? Number(value.endAt) : null,
      completedFocusSessions: Math.max(0, Number(value.completedFocusSessions) || 0),
      accumulatedFocusSeconds: Math.max(0, Number(value.accumulatedFocusSeconds) || 0),
      studySessionId: Number(value.studySessionId) > 0 ? Number(value.studySessionId) : null,
    };
  } catch {
    return null;
  }
}

export function writeSharedFocusTimer(state: SharedFocusTimerState) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(FOCUS_TIMER_KEY, JSON.stringify(state));
  window.dispatchEvent(new CustomEvent<SharedFocusTimerState>(FOCUS_TIMER_EVENT, { detail: state }));
}

export function remainingSecondsAt(state: SharedFocusTimerState, now = Date.now()) {
  if (!state.running || state.endAt === null) return state.remainingSeconds;
  return Math.min(
    state.phaseDurationSeconds,
    Math.max(0, Math.ceil((state.endAt - now) / 1000)),
  );
}

export function durationForTimerMode(mode: SharedFocusTimerState["mode"], durations: SharedTimerDurations) {
  if (mode === "focus") return durations.focus;
  return mode === "longBreak" ? durations.longBreak : durations.shortBreak;
}

export function reconcileSharedFocusTimer(
  timer: SharedFocusTimerState,
  now: number,
  durations: SharedTimerDurations,
): SharedFocusTimerState {
  if (!timer.running || timer.endAt === null) return timer;

  let mode = timer.mode;
  let endAt = timer.endAt;
  let phaseDurationSeconds = timer.phaseDurationSeconds;
  let completedFocusSessions = timer.completedFocusSessions;
  let accumulatedFocusSeconds = timer.accumulatedFocusSeconds;
  let transitions = 0;

  while (endAt <= now && transitions < 100) {
    if (mode === "focus") {
      completedFocusSessions += 1;
      accumulatedFocusSeconds += phaseDurationSeconds;
      mode = completedFocusSessions >= durations.cycleCount ? "longBreak" : "shortBreak";
    } else if (mode === "longBreak") {
      return {
        mode: "focus",
        remainingSeconds: durations.focus,
        phaseDurationSeconds: durations.focus,
        running: false,
        endAt: null,
        completedFocusSessions: 0,
        accumulatedFocusSeconds,
        studySessionId: timer.studySessionId,
      };
    } else {
      mode = "focus";
    }
    phaseDurationSeconds = durationForTimerMode(mode, durations);
    endAt += phaseDurationSeconds * 1000;
    transitions += 1;
  }

  return {
    mode,
    remainingSeconds: Math.max(0, Math.ceil((endAt - now) / 1000)),
    phaseDurationSeconds,
    running: true,
    endAt,
    completedFocusSessions,
    accumulatedFocusSeconds,
    studySessionId: timer.studySessionId,
  };
}

export function startSharedFocusTimer(durationSeconds: number, startedAt: string, studySessionId: number) {
  const safeDuration = Math.max(1, durationSeconds);
  writeSharedFocusTimer({
    mode: "focus",
    remainingSeconds: safeDuration,
    phaseDurationSeconds: safeDuration,
    running: true,
    endAt: new Date(startedAt).getTime() + safeDuration * 1000,
    completedFocusSessions: 0,
    accumulatedFocusSeconds: 0,
    studySessionId,
  });
}

export function stopSharedFocusTimer(durationSeconds: number) {
  const safeDuration = Math.max(1, durationSeconds);
  writeSharedFocusTimer({
    mode: "focus",
    remainingSeconds: safeDuration,
    phaseDurationSeconds: safeDuration,
    running: false,
    endAt: null,
    completedFocusSessions: 0,
    accumulatedFocusSeconds: 0,
    studySessionId: null,
  });
}

export function pauseSharedFocusTimer() {
  const current = readSharedFocusTimer();
  if (!current) return null;
  const paused: SharedFocusTimerState = {
    ...current,
    remainingSeconds: remainingSecondsAt(current),
    running: false,
    endAt: null,
  };
  writeSharedFocusTimer(paused);
  return paused;
}

export function resumeSharedFocusTimer() {
  const current = readSharedFocusTimer();
  if (!current) return null;
  const remainingSeconds = current.remainingSeconds || current.phaseDurationSeconds;
  const resumed: SharedFocusTimerState = {
    ...current,
    remainingSeconds,
    running: true,
    endAt: Date.now() + remainingSeconds * 1000,
  };
  writeSharedFocusTimer(resumed);
  return resumed;
}
