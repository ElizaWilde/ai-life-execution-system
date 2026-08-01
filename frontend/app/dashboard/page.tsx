"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { api, DailyTask, ParkedThought, TodayDashboard, WeekDashboard } from "../../lib/api";
import { subscribeToCheckInUpdates } from "../../lib/check-in-sync";
import { FOCUS_TIMER_KEY } from "../../lib/focus-timer-sync";
import { loadAppSettings, orderByWeekStart, useAppSettings } from "../../lib/settings";
import { playTimerCompleteSound, primeTimerSound } from "../../lib/timer-sound";

type IconName =
  | "calendar"
  | "chart"
  | "clock"
  | "check"
  | "alert"
  | "spark"
  | "brain"
  | "energy"
  | "smile"
  | "moon";

type TimerMode = "focus" | "shortBreak" | "longBreak";

type TimerDurations = {
  focus: number;
  shortBreak: number;
  longBreak: number;
  cycleCount: number;
};

type PersistentTimerState = {
  mode: TimerMode;
  remainingSeconds: number;
  phaseDurationSeconds: number;
  running: boolean;
  endAt: number | null;
  completedFocusSessions: number;
  studySessionId: number | null;
};

function durationForMode(mode: TimerMode, durations: TimerDurations) {
  if (mode === "focus") return durations.focus;
  return mode === "longBreak" ? durations.longBreak : durations.shortBreak;
}

function initialTimerState(focusDurationSeconds: number): PersistentTimerState {
  return {
    mode: "focus",
    remainingSeconds: focusDurationSeconds,
    phaseDurationSeconds: focusDurationSeconds,
    running: false,
    endAt: null,
    completedFocusSessions: 0,
    studySessionId: null,
  };
}

function loadFocusTimer(focusDurationSeconds: number): PersistentTimerState {
  if (typeof window === "undefined") return initialTimerState(focusDurationSeconds);
  try {
    const parsed = JSON.parse(window.localStorage.getItem(FOCUS_TIMER_KEY) ?? "null") as Partial<PersistentTimerState> | null;
    if (!parsed || !["focus", "shortBreak", "longBreak"].includes(parsed.mode ?? "")) {
      return initialTimerState(focusDurationSeconds);
    }
    const phaseDurationSeconds = Math.max(1, Number(parsed.phaseDurationSeconds) || focusDurationSeconds);
    return {
      mode: parsed.mode as TimerMode,
      remainingSeconds: Math.min(
        phaseDurationSeconds,
        Math.max(0, Number(parsed.remainingSeconds) || 0),
      ),
      phaseDurationSeconds,
      running: Boolean(parsed.running && Number.isFinite(parsed.endAt)),
      endAt: parsed.running && Number.isFinite(parsed.endAt) ? Number(parsed.endAt) : null,
      completedFocusSessions: Math.max(0, Number(parsed.completedFocusSessions) || 0),
      studySessionId: Number(parsed.studySessionId) > 0 ? Number(parsed.studySessionId) : null,
    };
  } catch {
    return initialTimerState(focusDurationSeconds);
  }
}

function saveFocusTimer(timer: PersistentTimerState) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(FOCUS_TIMER_KEY, JSON.stringify(timer));
}

function reconcileTimer(
  timer: PersistentTimerState,
  now: number,
  durations: TimerDurations,
): PersistentTimerState {
  if (!timer.running || timer.endAt === null) return timer;

  let mode = timer.mode;
  let endAt = timer.endAt;
  let phaseDurationSeconds = timer.phaseDurationSeconds;
  let completedFocusSessions = timer.completedFocusSessions;
  let transitions = 0;

  while (endAt <= now && transitions < 100) {
    if (mode === "focus") {
      completedFocusSessions += 1;
      mode = completedFocusSessions >= durations.cycleCount ? "longBreak" : "shortBreak";
    } else if (mode === "longBreak") {
      return {
        mode: "focus",
        remainingSeconds: durations.focus,
        phaseDurationSeconds: durations.focus,
        running: false,
        endAt: null,
        completedFocusSessions: 0,
        studySessionId: null,
      };
    } else {
      mode = "focus";
    }
    phaseDurationSeconds = durationForMode(mode, durations);
    endAt += phaseDurationSeconds * 1000;
    transitions += 1;
  }

  if (transitions === 100 && endAt <= now) {
    mode = "focus";
    completedFocusSessions = 0;
    phaseDurationSeconds = durations.focus;
    endAt = now + phaseDurationSeconds * 1000;
  }

  return {
    mode,
    remainingSeconds: Math.max(0, Math.ceil((endAt - now) / 1000)),
    phaseDurationSeconds,
    running: true,
    endAt,
    completedFocusSessions,
    studySessionId: timer.studySessionId,
  };
}

function Icon({ name, size = 22 }: { name: IconName; size?: number }) {
  const paths: Record<IconName, React.ReactNode> = {
    calendar: <><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 10h18M8 14h.01M12 14h.01M16 14h.01M8 18h.01M12 18h.01"/></>,
    chart: <><path d="M4 19V9M10 19V5M16 19v-7M22 19H2"/></>,
    clock: <><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></>,
    check: <><circle cx="12" cy="12" r="9"/><path d="m8 12 2.5 2.5L16 9"/></>,
    alert: <><path d="M10.3 3.8 2.7 17a2 2 0 0 0 1.7 3h15.2a2 2 0 0 0 1.7-3L13.7 3.8a2 2 0 0 0-3.4 0Z"/><path d="M12 9v4M12 17h.01"/></>,
    spark: <><path d="m12 2 1.6 5.1a5 5 0 0 0 3.3 3.3L22 12l-5.1 1.6a5 5 0 0 0-3.3 3.3L12 22l-1.6-5.1a5 5 0 0 0-3.3-3.3L2 12l5.1-1.6a5 5 0 0 0 3.3-3.3L12 2Z"/></>,
    brain: <><path d="M9.5 4.5A3 3 0 0 0 4 6a3 3 0 0 0 .5 5.5A3 3 0 0 0 6 17a3 3 0 0 0 5.5 1.5V5.2a2.7 2.7 0 0 0-2-2.7ZM14.5 4.5A3 3 0 0 1 20 6a3 3 0 0 1-.5 5.5A3 3 0 0 1 18 17a3 3 0 0 1-5.5 1.5V5.2a2.7 2.7 0 0 1 2-2.7Z"/><path d="M7 9.5h2.5M17 9.5h-2.5"/></>,
    energy: <path d="m13 2-8 12h7l-1 8 8-12h-7l1-8Z"/>,
    smile: <><circle cx="12" cy="12" r="9"/><path d="M8.5 10h.01M15.5 10h.01M8 14s1.5 2 4 2 4-2 4-2"/></>,
    moon: <path d="M20 15.2A8.5 8.5 0 0 1 8.8 4a8.5 8.5 0 1 0 11.2 11.2Z"/>,
  };
  return <svg aria-hidden="true" className="ui-icon" fill="none" height={size} viewBox="0 0 24 24" width={size}>{paths[name]}</svg>;
}

function formatDuration(minutes: number) {
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return rest ? `${hours}h ${rest}m` : `${hours}h`;
}

function dateKey(value: Date) {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function titleCase(value?: string | null) {
  if (!value) return "-";
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function taskTone(task: DailyTask) {
  if (task.status === "completed") return "done";
  if (task.status === "in_progress") return "progress";
  if (task.priority === "high") return "risk";
  return "planned";
}

function taskLabel(task: DailyTask) {
  if (task.status === "completed") return "Done";
  if (task.status === "in_progress") return "In progress";
  if (task.priority === "high") return "At risk";
  return "Planned";
}

function orderParkedThoughts(thoughts: ParkedThought[]) {
  return [...thoughts].sort(
    (left, right) => Number(left.completed) - Number(right.completed) || right.id - left.id,
  );
}

export default function DashboardPage() {
  const appSettings = useAppSettings();
  const focusMinutes = Math.max(1, Number(appSettings.focusMinutes) || 25);
  const focusDurationSeconds = focusMinutes * 60;
  const shortBreakDurationSeconds = Math.max(1, Number(appSettings.shortBreak) || 5) * 60;
  const longBreakDurationSeconds = Math.max(1, Number(appSettings.longBreak) || 15) * 60;
  const cycleCount = Math.min(12, Math.max(1, Number(appSettings.cycleCount) || 4));
  const [today, setToday] = useState<TodayDashboard | null>(null);
  const [week, setWeek] = useState<WeekDashboard | null>(null);
  const [error, setError] = useState("");
  const [timer, setTimer] = useState(() => initialTimerState(25 * 60));
  const [timerHydrated, setTimerHydrated] = useState(false);
  const [timerControlBusy, setTimerControlBusy] = useState(false);
  const [taskBusyId, setTaskBusyId] = useState<number | null>(null);
  const timerRef = useRef(timer);
  const lastSoundedEndAtRef = useRef<number | null>(null);
  timerRef.current = timer;
  const [parkedThoughts, setParkedThoughts] = useState<ParkedThought[]>([]);
  const [parkInput, setParkInput] = useState("");
  const [parkBusy, setParkBusy] = useState(false);

  useEffect(() => {
    async function loadDashboard() {
      try {
        const [todayData, weekData, thoughtData] = await Promise.all([
          api.getTodayDashboard(),
          api.getWeekDashboard(),
          api.getParkedThoughts(),
        ]);
        setToday(todayData);
        setWeek(weekData);
        setParkedThoughts(orderParkedThoughts(thoughtData));
        setError("");
      } catch (reason: unknown) {
        setError(reason instanceof Error ? reason.message : "Failed to load dashboard");
      }
    }

    loadDashboard();
    return subscribeToCheckInUpdates(dateKey(new Date()), loadDashboard);
  }, []);

  useEffect(() => {
    const savedMinutes = Number(loadAppSettings().focusMinutes) || 25;
    setTimer(loadFocusTimer(Math.max(1, savedMinutes) * 60));
    setTimerHydrated(true);
  }, []);

  useEffect(() => {
    if (!timerHydrated) return;
    const syncSharedTimer = (event: StorageEvent) => {
      if (event.key !== FOCUS_TIMER_KEY) return;
      setTimer(loadFocusTimer(focusDurationSeconds));
      void refreshPlanStats();
    };
    window.addEventListener("storage", syncSharedTimer);
    return () => window.removeEventListener("storage", syncSharedTimer);
  }, [focusDurationSeconds, timerHydrated]);

  useEffect(() => {
    if (!timerHydrated) return;
    const durations: TimerDurations = {
      focus: focusDurationSeconds,
      shortBreak: shortBreakDurationSeconds,
      longBreak: longBreakDurationSeconds,
      cycleCount,
    };
    const syncTimer = () => {
      const now = Date.now();
      const current = timerRef.current;
      const next = reconcileTimer(current, now, durations);
      if (
        current.running &&
        current.endAt !== null &&
        current.endAt <= now &&
        lastSoundedEndAtRef.current !== current.endAt
      ) {
        lastSoundedEndAtRef.current = current.endAt;
        void playTimerCompleteSound(current.endAt);
      }
      if (
        next.mode !== current.mode ||
        next.remainingSeconds !== current.remainingSeconds ||
        next.running !== current.running
      ) {
        timerRef.current = next;
        setTimer(next);
      }
    };
    syncTimer();
    const interval = window.setInterval(syncTimer, 1000);
    window.addEventListener("focus", syncTimer);
    document.addEventListener("visibilitychange", syncTimer);
    return () => {
      window.clearInterval(interval);
      window.removeEventListener("focus", syncTimer);
      document.removeEventListener("visibilitychange", syncTimer);
    };
  }, [cycleCount, focusDurationSeconds, longBreakDurationSeconds, shortBreakDurationSeconds, timerHydrated]);

  useEffect(() => {
    if (!timerHydrated) return;
    const durations: TimerDurations = {
      focus: focusDurationSeconds,
      shortBreak: shortBreakDurationSeconds,
      longBreak: longBreakDurationSeconds,
      cycleCount,
    };
    setTimer((current) => {
      const synced = reconcileTimer(current, Date.now(), durations);
      if (synced.running) return synced;
      const hasPausedProgress = synced.remainingSeconds > 0 && synced.remainingSeconds < synced.phaseDurationSeconds;
      if (hasPausedProgress) return synced;
      const configuredDuration = durationForMode(synced.mode, durations);
      if (
        synced.phaseDurationSeconds === configuredDuration &&
        synced.remainingSeconds === configuredDuration
      ) {
        return synced;
      }
      return {
        ...synced,
        remainingSeconds: configuredDuration,
        phaseDurationSeconds: configuredDuration,
        endAt: null,
      };
    });
  }, [cycleCount, focusDurationSeconds, longBreakDurationSeconds, shortBreakDurationSeconds, timerHydrated]);

  useEffect(() => {
    if (!timerHydrated) return;
    saveFocusTimer(timer);
  }, [timer, timerHydrated]);

  useEffect(() => {
    if (!timerHydrated || timer.mode === "focus" || !timer.studySessionId) return;
    const sessionId = timer.studySessionId;
    void api.finishSession({ session_id: sessionId, duration_seconds: focusDurationSeconds })
      .then(() => {
        setTimer((current) => current.studySessionId === sessionId
          ? { ...current, studySessionId: null }
          : current);
        void refreshPlanStats();
      })
      .catch((reason) => {
        setError(reason instanceof Error ? reason.message : "Could not finish the linked study session");
      });
  }, [focusDurationSeconds, timer.mode, timer.studySessionId, timerHydrated]);

  useEffect(() => {
    if (!timerHydrated) return;
    const pauseWhenDocumentCloses = () => {
      const durations: TimerDurations = {
        focus: focusDurationSeconds,
        shortBreak: shortBreakDurationSeconds,
        longBreak: longBreakDurationSeconds,
        cycleCount,
      };
      const currentTimer = reconcileTimer(timerRef.current, Date.now(), durations);
      const paused = { ...currentTimer, running: false, endAt: null };
      timerRef.current = paused;
      saveFocusTimer(paused);
    };
    window.addEventListener("beforeunload", pauseWhenDocumentCloses);
    window.addEventListener("pagehide", pauseWhenDocumentCloses);
    return () => {
      window.removeEventListener("beforeunload", pauseWhenDocumentCloses);
      window.removeEventListener("pagehide", pauseWhenDocumentCloses);
    };
  }, [cycleCount, focusDurationSeconds, longBreakDurationSeconds, shortBreakDurationSeconds, timerHydrated]);

  const currentDate = useMemo(
    () => new Date(`${today?.date ?? new Date().toISOString().slice(0, 10)}T00:00:00`),
    [today?.date],
  );
  const focusPoints = orderByWeekStart(week?.daily_focus ?? [], (point) => point.date, appSettings.weekStart);
  const focusChartMaximumMinutes = 6 * 60;
  const tasks = today?.tasks.filter((task) => task.status !== "cancelled") ?? [];
  const weekCalendar = useMemo(() => {
    const firstDay = appSettings.weekStart === "Sunday" ? 0 : 1;
    const start = new Date(currentDate);
    start.setDate(start.getDate() - ((start.getDay() - firstDay + 7) % 7));
    const pointsByDate = new Map((week?.daily_focus ?? []).map((point) => [point.date, point]));

    return Array.from({ length: 7 }, (_, index) => {
      const date = new Date(start);
      date.setDate(start.getDate() + index);
      const key = dateKey(date);
      const point = pointsByDate.get(key);
      return {
        date,
        key,
        isToday: key === dateKey(currentDate),
        plannedMinutes: point?.planned_minutes ?? 0,
        focusMinutes: point?.focus_minutes ?? 0,
      };
    });
  }, [appSettings.weekStart, currentDate, week?.daily_focus]);
  const timerDurationSeconds = timer.phaseDurationSeconds;
  const timerProgress = Math.min(1, timer.remainingSeconds / timerDurationSeconds);
  const timerDisplay = `${String(Math.floor(timer.remainingSeconds / 60)).padStart(2, "0")}:${String(timer.remainingSeconds % 60).padStart(2, "0")}`;
  const timerCircumference = 2 * Math.PI * 72;
  const timerHasStarted = timer.running || Boolean(timer.studySessionId) || timer.remainingSeconds < timer.phaseDurationSeconds;

  async function toggleTimer() {
    if (timerControlBusy) return;
    void primeTimerSound();
    const durations: TimerDurations = {
      focus: focusDurationSeconds,
      shortBreak: shortBreakDurationSeconds,
      longBreak: longBreakDurationSeconds,
      cycleCount,
    };
    const synced = reconcileTimer(timerRef.current, Date.now(), durations);
    if (synced.running) {
      setTimer({ ...synced, running: false, endAt: null });
      return;
    }

    setTimerControlBusy(true);
    try {
      let studySessionId = synced.studySessionId;
      if (synced.mode === "focus" && !studySessionId) {
        try {
          const session = await api.startSession({
            subject: today?.check_in?.focus_mode ?? "Dashboard focus session",
          });
          studySessionId = session.id;
        } catch (reason) {
          const sessions = await api.getTodaySessions();
          const activeSession = sessions.find((session) => session.status === "running");
          if (!activeSession) throw reason;
          studySessionId = activeSession.id;
        }
      }
      const remainingSeconds = synced.remainingSeconds || durationForMode(synced.mode, durations);
      setTimer({
        ...synced,
        remainingSeconds,
        phaseDurationSeconds: Math.max(synced.phaseDurationSeconds, remainingSeconds),
        running: true,
        endAt: Date.now() + remainingSeconds * 1000,
        studySessionId,
      });
      setError("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not start the focus session");
    } finally {
      setTimerControlBusy(false);
    }
  }

  async function finishTimer() {
    if (timerControlBusy) return;
    setTimerControlBusy(true);
    const durations: TimerDurations = {
      focus: focusDurationSeconds,
      shortBreak: shortBreakDurationSeconds,
      longBreak: longBreakDurationSeconds,
      cycleCount,
    };
    const synced = reconcileTimer(timerRef.current, Date.now(), durations);
    let completedFocusSessions = synced.completedFocusSessions;
    let mode: TimerMode;
    if (synced.mode === "focus") {
      completedFocusSessions += 1;
      mode = completedFocusSessions >= cycleCount ? "longBreak" : "shortBreak";
    } else {
      if (synced.mode === "longBreak") completedFocusSessions = 0;
      mode = "focus";
    }
    const duration = durationForMode(mode, durations);
    const finishedTimer: PersistentTimerState = {
      mode,
      remainingSeconds: duration,
      phaseDurationSeconds: duration,
      running: false,
      endAt: null,
      completedFocusSessions,
      studySessionId: null,
    };
    if (synced.studySessionId) {
      try {
        const focusedSeconds = synced.mode === "focus"
          ? Math.max(0, synced.phaseDurationSeconds - synced.remainingSeconds)
          : focusDurationSeconds;
        await api.finishSession({
          session_id: synced.studySessionId,
          duration_seconds: focusedSeconds,
        });
        await refreshPlanStats();
      } catch (reason) {
        setError(reason instanceof Error ? reason.message : "Could not finish the linked study session");
        setTimerControlBusy(false);
        return;
      }
    }
    void playTimerCompleteSound(synced.endAt ?? `dashboard-finish-${Date.now()}`);
    setTimer(finishedTimer);
    setTimerControlBusy(false);
  }

  async function refreshPlanStats() {
    try {
      const [todayData, weekData] = await Promise.all([
        api.getTodayDashboard(),
        api.getWeekDashboard(),
      ]);
      setToday(todayData);
      setWeek(weekData);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not refresh task progress");
    }
  }

  async function toggleTaskCompleted(task: DailyTask) {
    if (taskBusyId !== null) return;
    setTaskBusyId(task.id);
    try {
      await api.updateTask(task.id, {
        status: task.status === "completed" ? "pending" : "completed",
      });
      await refreshPlanStats();
      setError("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not update the task");
    } finally {
      setTaskBusyId(null);
    }
  }

  async function addParkedThought(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const content = parkInput.trim();
    if (!content || parkBusy) return;
    setParkBusy(true);
    try {
      const thought = await api.createParkedThought(content);
      setParkedThoughts((current) => orderParkedThoughts([thought, ...current]));
      setParkInput("");
      setError("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not park that thought");
    } finally {
      setParkBusy(false);
    }
  }

  async function toggleParkedThought(thought: ParkedThought) {
    if (parkBusy) return;
    setParkBusy(true);
    try {
      const updated = await api.updateParkedThought(thought.id, { completed: !thought.completed });
      setParkedThoughts((current) => orderParkedThoughts(current.map((item) => item.id === updated.id ? updated : item)));
      setError("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not update that thought");
    } finally {
      setParkBusy(false);
    }
  }

  async function removeParkedThought(thoughtId: number) {
    if (parkBusy) return;
    setParkBusy(true);
    try {
      await api.deleteParkedThought(thoughtId);
      setParkedThoughts((current) => current.filter((thought) => thought.id !== thoughtId));
      setError("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not remove that thought");
    } finally {
      setParkBusy(false);
    }
  }

  return (
    <section className="life-dashboard">
      <header className="life-hero">
        <div className="today-date-card">
          <span className="hero-icon"><Icon name="calendar" size={30} /></span>
          <div><strong>Today</strong><span>{currentDate.toLocaleDateString("en", { weekday: "short", month: "short", day: "numeric" })}</span></div>
        </div>
        <div className="hero-copy"><h1>Ready for today? <i><Icon name="spark" size={28} /></i></h1><p>Let your AI coach guide the day.</p></div>
        <Link className="coach-button" href="/coach"><Icon name="spark" size={18} /> Ask Coach <span>⌄</span></Link>
      </header>

      {error ? <div className="error dashboard-error">{error}</div> : null}

      <div className="dashboard-middle-grid">
        <article className="panel today-panel">
          <div className="panel-heading"><h2>Today</h2><Link href="/today">View all</Link></div>
          <div className="today-task-list">
            {!today ? <p className="panel-empty">Loading today&apos;s plan…</p> : null}
            {today && tasks.length === 0 ? <p className="panel-empty">Your plan is clear. Add a task to shape the day.</p> : null}
            {tasks.slice(0, 5).map((task, index) => (
              <div className={`today-task-row ${task.status === "completed" ? "completed" : ""}`} key={task.id}>
                <button
                  aria-label={task.status === "completed" ? `Reopen ${task.title}` : `Complete ${task.title}`}
                  className={`task-check ${task.status === "completed" ? "checked" : ""}`}
                  disabled={taskBusyId !== null}
                  onClick={() => toggleTaskCompleted(task)}
                  title={task.status === "completed" ? "Reopen task" : "Mark complete"}
                  type="button"
                >{task.status === "completed" ? "✓" : ""}</button>
                <strong title={task.title}>{task.title}</strong>
                <span className={`priority-pill ${task.priority}`}>{titleCase(task.priority)}</span>
                <span className="task-time">{task.estimated_minutes ? formatDuration(task.estimated_minutes) : "Flexible"}</span>
                <span className={`status-pill ${taskTone(task)}`}>{taskLabel(task)}</span>
              </div>
            ))}
          </div>
        </article>

        <article className="panel focus-timer-panel">
          <div className="panel-heading">
            <h2>Focus Timer</h2>
            <Link aria-label="Open timer settings" className="timer-settings" href="/timer">⚙</Link>
          </div>
          <div className="timer-dial">
            <svg aria-hidden="true" viewBox="0 0 180 180">
              <circle className="timer-track" cx="90" cy="90" r="72" />
              <circle
                className="timer-progress"
                cx="90"
                cy="90"
                r="72"
                strokeDasharray={timerCircumference}
                strokeDashoffset={timerCircumference * (1 - timerProgress)}
              />
            </svg>
            <div><strong>{timerDisplay}</strong><span>{timer.mode === "focus" ? "Focus Time" : timer.mode === "longBreak" ? "Long Break" : "Short Break"}</span></div>
          </div>
          <div className={`timer-mode ${timer.mode === "longBreak" ? "celebration" : ""}`}>
            {timer.mode === "longBreak" ? (
              "Congratulations! 🥳"
            ) : (
              <><Icon name={timer.mode === "focus" ? "brain" : "clock"} size={15} /> {timer.mode === "focus" ? (today?.check_in?.focus_mode ?? "Deep work") : "Break"}</>
            )}
          </div>
          <div className="timer-actions">
            <button className="timer-toggle" disabled={timerControlBusy} onClick={toggleTimer} type="button">
              <span>{timer.running ? "Ⅱ" : "▶"}</span> {timer.running ? "Pause" : "Start"}
            </button>
            <button className="timer-finish" disabled={timerControlBusy || !timerHasStarted} onClick={finishTimer} type="button">✓ Finish</button>
          </div>
        </article>

        <article className="panel park-panel">
          <div className="panel-heading">
            <div className="park-heading"><h2>Park</h2><span>{parkedThoughts.filter((thought) => !thought.completed).length}</span></div>
            <small>Capture it, keep focusing</small>
          </div>
          <form className="park-form" onSubmit={addParkedThought}>
            <input
              aria-label="Park a sudden thought"
              maxLength={500}
              onChange={(event) => setParkInput(event.target.value)}
              placeholder="A sudden thought or idea..."
              value={parkInput}
            />
            <button aria-label="Add thought to Park" disabled={parkBusy || !parkInput.trim()} type="submit">+</button>
          </form>
          <div className="park-list">
            {parkedThoughts.length === 0 ? <p className="park-empty">Ideas that interrupt your focus can wait safely here.</p> : null}
            {parkedThoughts.map((thought) => (
              <div className={thought.completed ? "completed" : ""} key={thought.id}>
                <button
                  aria-label={thought.completed ? `Mark ${thought.content} as open` : `Mark ${thought.content} complete`}
                  className="park-check"
                  disabled={parkBusy}
                  onClick={() => toggleParkedThought(thought)}
                  type="button"
                >{thought.completed ? "✓" : ""}</button>
                <span title={thought.content}>{thought.content}</span>
                <button
                  aria-label={`Remove ${thought.content}`}
                  className="park-remove"
                  disabled={parkBusy}
                  onClick={() => removeParkedThought(thought.id)}
                  type="button"
                >×</button>
              </div>
            ))}
          </div>
        </article>

      </div>

      <div className="dashboard-bottom-grid">
        <article className="panel schedule-panel">
          <div className="panel-heading"><div><h2>Schedule</h2><span className="schedule-range">{weekCalendar[0].date.toLocaleDateString("en", { month: "short", day: "numeric" })} – {weekCalendar[6].date.toLocaleDateString("en", { month: "short", day: "numeric", year: "numeric" })}</span></div><Link href="/weekly-plan">View plan</Link></div>
          <div className="week-calendar">
            {weekCalendar.map((day) => (
              <article className={`week-calendar-day ${day.isToday ? "today" : ""}`} key={day.key}>
                <header><span>{day.date.toLocaleDateString("en", { weekday: "short" })}</span><strong>{day.date.getDate()}</strong></header>
                <div className={day.plannedMinutes ? "planned" : "open"}><b>{day.plannedMinutes ? formatDuration(day.plannedMinutes) : "Open"}</b><span>{day.plannedMinutes ? "planned" : "capacity"}</span></div>
                <small>{day.focusMinutes ? `${formatDuration(day.focusMinutes)} focused` : "No focus logged"}</small>
              </article>
            ))}
          </div>
        </article>

        <article className="panel focus-panel">
          <div className="panel-heading"><h2>Focus</h2><span className="chart-key"><i /> Focus (h)</span></div>
          <div className="focus-chart">
            <div className="chart-scale"><span>6h</span><span>4h</span><span>2h</span><span>0h</span></div>
            <div className="chart-plot">
              <div className="goal-line"><span>Goal: 5h</span></div>
              {(focusPoints.length ? focusPoints : Array.from({ length: 7 }, (_, index) => ({ date: new Date(currentDate.getTime() + index * 86400000).toISOString().slice(0, 10), focus_minutes: 0, planned_minutes: 0 }))).map((point) => {
                const pointDate = new Date(`${point.date}T00:00:00`);
                const barHeight = Math.min(100, (point.focus_minutes / focusChartMaximumMinutes) * 100);
                return <div className="focus-column" key={point.date}>
                  <div className="focus-bar-area">
                    <span className="bar-value" style={{ bottom: `calc(${barHeight}% + 4px)` }}>{(point.focus_minutes / 60).toFixed(1)}h</span>
                    <div className="focus-bar" style={{ height: `${barHeight}%` }} />
                  </div>
                  <small>{pointDate.toLocaleDateString("en", { weekday: "short" })} {pointDate.getDate()}</small>
                </div>;
              })}
            </div>
          </div>
        </article>

        <article className="panel checkin-panel">
          <div className="panel-heading"><h2>Check-in</h2><Link href="/check-in">Edit</Link></div>
          <div className="checkin-list">
            <div><span className="checkin-icon mood"><Icon name="smile" /></span><label>Mood</label><strong>{today?.check_in ? titleCase(today.check_in.mood_level) : ""}</strong><b>{today?.check_in && today.readiness_score !== null ? `${Math.round(today.readiness_score)}/100` : "-"}</b></div>
            <div><span className="checkin-icon energy"><Icon name="energy" /></span><label>Energy</label><strong>{today?.check_in ? titleCase(today.check_in.energy_level) : ""}</strong><b>{today?.check_in && today.workload_level ? titleCase(today.workload_level) : "-"}</b></div>
            <div><span className="checkin-icon sleep"><Icon name="moon" /></span><label>Sleep</label><strong>{today?.check_in ? `${today.check_in.sleep_hours}h` : ""}</strong><b>{today?.check_in ? (today.check_in.sleep_hours >= 7 ? "Good" : "-") : "-"}</b></div>
          </div>
          {today?.coaching?.summary ? <div className="coach-note"><Icon name="spark" size={17} /> {today.coaching.summary}</div> : null}
        </article>
      </div>
    </section>
  );
}
