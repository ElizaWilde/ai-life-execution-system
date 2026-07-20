"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { api, DailyTask, ParkedThought, TodayDashboard, WeekDashboard } from "../../lib/api";
import { subscribeToCheckInUpdates } from "../../lib/check-in-sync";
import { loadAppSettings, orderByWeekStart, useAppSettings } from "../../lib/settings";

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
  const [timerSeconds, setTimerSeconds] = useState(() => {
    const savedMinutes = Number(loadAppSettings().focusMinutes) || 25;
    return Math.max(1, savedMinutes) * 60;
  });
  const [timerRunning, setTimerRunning] = useState(false);
  const [timerMode, setTimerMode] = useState<TimerMode>("focus");
  const [completedFocusSessions, setCompletedFocusSessions] = useState(0);
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
    if (!timerRunning || timerSeconds === 0) return;
    const interval = window.setInterval(() => {
      setTimerSeconds((seconds) => {
        if (seconds <= 1) {
          if (timerMode === "focus") {
            const nextCompletedSessions = completedFocusSessions + 1;
            const nextMode: TimerMode = nextCompletedSessions >= cycleCount ? "longBreak" : "shortBreak";
            setCompletedFocusSessions(nextCompletedSessions);
            setTimerMode(nextMode);
            return nextMode === "longBreak" ? longBreakDurationSeconds : shortBreakDurationSeconds;
          }

          if (timerMode === "longBreak") setCompletedFocusSessions(0);
          setTimerMode("focus");
          return focusDurationSeconds;
        }
        return seconds - 1;
      });
    }, 1000);
    return () => window.clearInterval(interval);
  }, [completedFocusSessions, cycleCount, focusDurationSeconds, longBreakDurationSeconds, shortBreakDurationSeconds, timerMode, timerRunning, timerSeconds]);

  useEffect(() => {
    setTimerRunning(false);
    setTimerMode("focus");
    setCompletedFocusSessions(0);
    setTimerSeconds(focusDurationSeconds);
  }, [cycleCount, focusDurationSeconds, longBreakDurationSeconds, shortBreakDurationSeconds]);

  const currentDate = useMemo(
    () => new Date(`${today?.date ?? new Date().toISOString().slice(0, 10)}T00:00:00`),
    [today?.date],
  );
  const todayCompletion = Math.round((today?.completion_rate ?? 0) * 100);
  const weekCompletion = Math.round((week?.completion_rate ?? 0) * 100);
  const focusHours = ((week?.focus_minutes ?? 0) / 60).toFixed(1);
  const atRisk = today?.unfinished_tasks.filter((task) => task.priority === "high").length ?? 0;
  const focusPoints = orderByWeekStart(week?.daily_focus ?? [], (point) => point.date, appSettings.weekStart);
  const maxFocus = Math.max(60, ...focusPoints.map((point) => point.focus_minutes));
  const tasks = today?.unfinished_tasks ?? [];
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
  const timerDurationSeconds = timerMode === "focus"
    ? focusDurationSeconds
    : timerMode === "longBreak"
      ? longBreakDurationSeconds
      : shortBreakDurationSeconds;
  const timerProgress = timerSeconds / timerDurationSeconds;
  const timerDisplay = `${String(Math.floor(timerSeconds / 60)).padStart(2, "0")}:${String(timerSeconds % 60).padStart(2, "0")}`;
  const timerCircumference = 2 * Math.PI * 72;

  function toggleTimer() {
    setTimerRunning((running) => !running);
  }

  function restartTimer() {
    setTimerRunning(false);
    setTimerSeconds(timerDurationSeconds);
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
        <Link className="coach-button" href="/check-in"><Icon name="spark" size={18} /> Ask Coach <span>⌄</span></Link>
      </header>

      {error ? <div className="error dashboard-error">{error}</div> : null}

      <div className="metric-grid">
        <article className="metric-card purple"><span className="metric-icon"><Icon name="chart" /></span><div><p>Progress</p><strong>{weekCompletion}%</strong><small><b>↑ {week?.completed_tasks ?? 0}</b> completed this week</small></div></article>
        <article className="metric-card blue"><span className="metric-icon"><Icon name="clock" /></span><div><p>Focus</p><strong>{focusHours}h</strong><small><b>↑ {formatDuration(today?.focus_minutes ?? 0)}</b> today</small></div></article>
        <article className="metric-card green"><span className="metric-icon"><Icon name="check" /></span><div><p>Completion</p><strong>{todayCompletion}%</strong><small><b>↑ {today?.completed_tasks ?? 0}</b> of {today?.planned_tasks ?? 0} tasks</small></div></article>
        <article className="metric-card orange"><span className="metric-icon"><Icon name="alert" /></span><div><p>At-Risk</p><strong>{atRisk}</strong><small><b>→</b> high-priority tasks</small></div></article>
      </div>

      <div className="dashboard-middle-grid">
        <article className="panel today-panel">
          <div className="panel-heading"><h2>Today</h2><Link href="/today">View all</Link></div>
          <div className="today-task-list">
            {!today ? <p className="panel-empty">Loading today&apos;s plan…</p> : null}
            {today && tasks.length === 0 ? <p className="panel-empty">Your plan is clear. Add a task to shape the day.</p> : null}
            {tasks.slice(0, 5).map((task, index) => (
              <div className="today-task-row" key={task.id}>
                <span className={`task-check ${task.status === "completed" ? "checked" : ""}`}>{task.status === "completed" ? "✓" : ""}</span>
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
            <div><strong>{timerDisplay}</strong><span>{timerMode === "focus" ? "Focus Time" : timerMode === "longBreak" ? "Long Break" : "Short Break"}</span></div>
          </div>
          <div className="timer-mode"><Icon name={timerMode === "focus" ? "brain" : "clock"} size={15} /> {timerMode === "focus" ? (today?.check_in?.focus_mode ?? "Deep work") : "Break"}</div>
          <div className="timer-actions">
            <button className="timer-toggle" onClick={toggleTimer} type="button">
              <span>{timerRunning ? "Ⅱ" : "▶"}</span> {timerRunning ? "Pause" : "Start"}
            </button>
            <button className="timer-restart" onClick={restartTimer} type="button">↻ Restart</button>
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
                return <div className="focus-column" key={point.date}><span className="bar-value">{(point.focus_minutes / 60).toFixed(1)}h</span><div className="focus-bar" style={{ height: `${Math.max(2, (point.focus_minutes / maxFocus) * 100)}%` }} /><small>{pointDate.toLocaleDateString("en", { weekday: "short" })} {pointDate.getDate()}</small></div>;
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
