"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import {
  AdaptiveDailyPlan,
  api,
  DailyCheckIn,
  DailyTask,
  EnergyLevel,
  MoodLevel,
  Priority,
  TodayDashboard,
} from "../../lib/api";
import { useAppSettings, workloadMinutes } from "../../lib/settings";
import { announceCheckInUpdate, subscribeToCheckInUpdates } from "../../lib/check-in-sync";
import { AVAILABLE_TIME_OPTIONS, availableTimeBucket } from "../../lib/check-in-options";

type TodayIconName = "spark" | "clock" | "check" | "trash" | "sleep" | "energy" | "mood" | "calendar" | "target" | "chart" | "edit";

function TodayIcon({ name, size = 18 }: { name: TodayIconName; size?: number }) {
  const paths: Record<TodayIconName, React.ReactNode> = {
    spark: <path d="m12 2 1.6 5.1a5 5 0 0 0 3.3 3.3L22 12l-5.1 1.6a5 5 0 0 0-3.3 3.3L12 22l-1.6-5.1a5 5 0 0 0-3.3-3.3L2 12l5.1-1.6a5 5 0 0 0 3.3-3.3L12 2Z" />,
    clock: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
    check: <><circle cx="12" cy="12" r="9" /><path d="m8 12 2.5 2.5L16 9" /></>,
    trash: <><path d="M4 7h16M9 7V4h6v3M7 7l1 14h8l1-14M10 11v6M14 11v6" /></>,
    sleep: <path d="M20 15.2A8.5 8.5 0 0 1 8.8 4a8.5 8.5 0 1 0 11.2 11.2Z" />,
    energy: <path d="m13 2-8 12h7l-1 8 8-12h-7l1-8Z" />,
    mood: <><circle cx="12" cy="12" r="9" /><path d="M8.5 10h.01M15.5 10h.01M8 14s1.5 2 4 2 4-2 4-2" /></>,
    calendar: <><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M16 3v4M8 3v4M3 10h18" /></>,
    target: <><circle cx="12" cy="12" r="9" /><circle cx="12" cy="12" r="5" /><circle cx="12" cy="12" r="1" /></>,
    chart: <path d="M4 19V9M10 19V5M16 19v-7M22 19H2" />,
    edit: <><path d="M4 20h4L19 9l-4-4L4 16v4Z" /><path d="m13.5 6.5 4 4" /></>,
  };
  return <svg aria-hidden="true" className="today-icon" fill="none" height={size} viewBox="0 0 24 24" width={size}>{paths[name]}</svg>;
}

function localToday() {
  const now = new Date();
  return new Date(now.getTime() - now.getTimezoneOffset() * 60_000).toISOString().slice(0, 10);
}

function formatMinutes(minutes: number) {
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return rest ? `${hours}h ${rest}m` : `${hours}h`;
}

function formatHours(minutes: number) {
  const hours = minutes / 60;
  return `${hours % 1 === 0 ? hours.toFixed(0) : hours.toFixed(1)}h`;
}

const sleepHourOptions = Array.from({ length: 19 }, (_, index) => 3 + index / 2);

function sleepHourLabel(value: number) {
  const hours = Math.floor(value);
  const hasHalfHour = value % 1 !== 0;
  if (hours === 0) return hasHalfHour ? "30 min" : "0 hours";
  const hourLabel = `${hours} ${hours === 1 ? "hour" : "hours"}`;
  return hasHalfHour ? `${hourLabel} 30 min` : hourLabel;
}

export default function TodayPage() {
  const appSettings = useAppSettings();
  const today = localToday();
  const [tasks, setTasks] = useState<DailyTask[]>([]);
  const [dashboard, setDashboard] = useState<TodayDashboard | null>(null);
  const [generatedPlan, setGeneratedPlan] = useState<AdaptiveDailyPlan | null>(null);
  const [showAddTask, setShowAddTask] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const [title, setTitle] = useState("");
  const [taskHours, setTaskHours] = useState("0.5");
  const [priority, setPriority] = useState<Priority>("medium");
  const [availableMinutes, setAvailableMinutes] = useState("360");
  const [energy, setEnergy] = useState<EnergyLevel>("steady");
  const [mood, setMood] = useState<MoodLevel>("good");
  const [sleepHours, setSleepHours] = useState("7.5");
  const [focusMode, setFocusMode] = useState<NonNullable<DailyCheckIn["focus_mode"]>>("Deep work");
  const [difficulty, setDifficulty] = useState("medium");
  const [notes, setNotes] = useState("");

  async function loadToday() {
    setError("");
    try {
      const [taskData, dashboardData] = await Promise.all([
        api.getTodayTasks(),
        api.getTodayDashboard(),
      ]);
      setTasks(taskData);
      setDashboard(dashboardData);
      if (dashboardData.check_in) {
        setEnergy(dashboardData.check_in.energy_level);
        setMood(dashboardData.check_in.mood_level);
        setSleepHours(String(dashboardData.check_in.sleep_hours));
        if (dashboardData.check_in.available_minutes !== null) setAvailableMinutes(availableTimeBucket(dashboardData.check_in.available_minutes));
        if (dashboardData.check_in.focus_mode) setFocusMode(dashboardData.check_in.focus_mode);
        setNotes(dashboardData.check_in.notes ?? "");
        setDifficulty((dashboardData.check_in.stress_level ?? 3) >= 4 ? "high" : (dashboardData.check_in.stress_level ?? 3) <= 2 ? "low" : "medium");
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Failed to load today");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadToday();
    return subscribeToCheckInUpdates(today, loadToday);
  }, [today]);

  useEffect(() => {
    if (dashboard?.check_in?.available_minutes === null || dashboard?.check_in?.available_minutes === undefined) {
      setAvailableMinutes(availableTimeBucket(workloadMinutes(appSettings.workload)));
    }
  }, [appSettings.workload, dashboard?.check_in?.available_minutes]);

  const completion = Math.round((dashboard?.completion_rate ?? 0) * 100);
  const circumference = 2 * Math.PI * 34;
  const plannedFocusMinutes = tasks
    .filter((task) => task.status !== "cancelled")
    .reduce((total, task) => total + (task.estimated_minutes ?? 0), 0);
  const sortedTasks = [...tasks].sort((left, right) =>
    Number(left.status === "completed") - Number(right.status === "completed") || left.id - right.id,
  );

  async function createTask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api.createTask({ title, task_date: today, estimated_minutes: taskHours ? Math.round(Number(taskHours) * 60) : null, priority, source: "manual" });
      setTitle("");
      setShowAddTask(false);
      await loadToday();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Failed to create task");
    } finally {
      setBusy(false);
    }
  }

  async function setStatus(task: DailyTask, status: DailyTask["status"]) {
    setBusy(true);
    try {
      await api.updateTask(task.id, { status });
      await loadToday();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Failed to update task");
    } finally {
      setBusy(false);
    }
  }

  async function deleteTask(task: DailyTask) {
    if (!window.confirm(`Delete "${task.title}"? This cannot be undone.`)) return;
    setBusy(true);
    setError("");
    try {
      await api.deleteTask(task.id);
      setMessage(`Deleted: ${task.title}`);
      await loadToday();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Failed to delete task");
    } finally {
      setBusy(false);
    }
  }

  async function saveCheckIn(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const payload = {
      energy_level: energy,
      mood_level: mood,
      sleep_hours: Number(sleepHours),
      stress_level: difficulty === "high" ? 4 : difficulty === "low" ? 2 : 3,
      available_minutes: Number(availableMinutes),
      focus_mode: focusMode,
      notes: notes.trim() || null,
      cycle_day: dashboard?.check_in?.cycle_day ?? null,
      cycle_notes: dashboard?.check_in?.cycle_notes ?? null,
    };
    try {
      if (dashboard?.check_in) await api.updateCheckIn(today, payload);
      else await api.createCheckIn({ check_in_date: today, ...payload });
      setMessage("Today’s check-in was updated.");
      await loadToday();
      announceCheckInUpdate(today);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Failed to save check-in");
    } finally {
      setBusy(false);
    }
  }

  async function generatePlan() {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const result = await api.generatePlan({ available_minutes: Number(availableMinutes), task_date: today });
      setGeneratedPlan(result);
      setMessage(`Generated ${result.tasks.length} tasks for ${result.adjusted_available_minutes} minutes of planning capacity.`);
      await loadToday();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Failed to generate plan");
    } finally {
      setBusy(false);
    }
  }

  const date = new Date(`${today}T00:00:00`);

  return (
    <section className="today-workspace">
      <header className="today-workspace-header">
        <div><h1>Today</h1><p>{date.toLocaleDateString("en", { weekday: "short", month: "short", day: "numeric", year: "numeric" })} <span>⌄</span></p></div>
        <div className="today-greeting"><TodayIcon name="spark" size={34} /><div><strong>Hey, ready to make today count?</strong><span>Plan your day, check in with yourself, and let’s get things done.</span></div></div>
        <Link className="today-coach-button" href="/check-in"><TodayIcon name="spark" /> Ask my coach <span>⌄</span></Link>
      </header>

      {error ? <div className="error today-feedback">{error}</div> : null}
      {message ? <div className="success today-feedback">{message}</div> : null}

      <div className="today-workspace-grid">
        <main className="today-main-column">
          <section className="today-card today-plan-card">
            <div className="today-plan-heading"><div><h2>Today’s Plan</h2><span>{tasks.length} tasks</span></div></div>

            <div className="today-progress-card">
              <div className="today-progress-ring"><svg viewBox="0 0 80 80"><circle className="track" cx="40" cy="40" r="34" /><circle className="value" cx="40" cy="40" r="34" strokeDasharray={circumference} strokeDashoffset={circumference * (1 - completion / 100)} /></svg><strong>{completion}%</strong></div>
              <div className="progress-copy"><strong>Daily Progress</strong><span>{dashboard?.completed_tasks ?? 0} of {dashboard?.planned_tasks ?? tasks.length} tasks completed</span></div>
              <div className="progress-divider" />
              <span className="progress-metric-icon blue"><TodayIcon name="clock" /></span><div className="progress-copy"><strong>Focus Time</strong><span>{formatMinutes(dashboard?.focus_minutes ?? 0)} / {formatHours(plannedFocusMinutes)}</span></div>
              <div className="progress-divider" />
              <span className="progress-metric-icon green"><TodayIcon name="check" /></span><div className="progress-copy"><strong>Tasks Completed</strong><span>{dashboard?.completed_tasks ?? 0} / {dashboard?.planned_tasks ?? tasks.length}</span></div>
            </div>

            <div className="today-work-list">
              {loading ? <p className="today-empty">Loading today’s plan…</p> : null}
              {!loading && !sortedTasks.length ? <p className="today-empty">No tasks yet. Add the first task for today.</p> : null}
              {sortedTasks.map((task, index) => <article className={`today-work-row ${task.status === "completed" ? "completed" : ""}`} key={task.id}>
                <span className="priority-index">{index + 1}</span>
                <span className="priority-title">{task.title}</span>
                <b className={`today-priority ${task.priority}`}>{task.priority}</b>
                <small>{task.estimated_minutes ? `Est. ${formatHours(task.estimated_minutes)}` : "Flexible"}</small>
                <div className="priority-row-actions">
                  <button aria-label={task.status === "completed" ? `Completed ${task.title}` : `Done ${task.title}`} className="priority-done-button" disabled={busy || task.status === "completed"} onClick={() => setStatus(task, "completed")} title={task.status === "completed" ? "Completed" : "Mark done"} type="button"><TodayIcon name="check" size={17} /></button>
                  <button aria-label={`Delete ${task.title}`} className="priority-delete-button" disabled={busy} onClick={() => deleteTask(task)} title="Delete task" type="button"><TodayIcon name="trash" size={17} /></button>
                </div>
              </article>)}
              {showAddTask ? <form className="today-add-form" onSubmit={createTask}><input className="input" placeholder="What needs to get done?" required value={title} onChange={(event) => setTitle(event.target.value)} /><input aria-label="Estimated hours" className="input" min="0.25" placeholder="Hours" step="0.25" type="number" value={taskHours} onChange={(event) => setTaskHours(event.target.value)} /><select aria-label="Priority level" className="input" value={priority} onChange={(event) => setPriority(event.target.value as Priority)}><option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option></select><button className="today-primary-button" disabled={busy} type="submit">Add task</button><button className="today-add-cancel" onClick={() => setShowAddTask(false)} type="button">Cancel</button></form> : null}
              {!showAddTask ? <button className="today-add-bottom" onClick={() => setShowAddTask(true)} type="button">＋ Add Task</button> : null}
            </div>
          </section>

          <section className="today-card ai-plan-card ai-plan-main-card">
            <div className="side-card-heading"><h2>Today’s AI Plan</h2><span>Based on weekly goals + today’s condition</span></div><p>Generate or refine today’s plan.</p>
            {generatedPlan ? <div className="adaptive-inline"><strong>{Math.round(generatedPlan.readiness_score)} readiness</strong><span>{generatedPlan.adjusted_available_minutes} min capacity · {generatedPlan.workload_level} workload</span></div> : null}
            <div className="ai-plan-actions"><article><h3><b>1</b> Generate Plan</h3><p>Create today’s plan from weekly goals, energy, mood and available time.</p><button disabled={busy} onClick={generatePlan} type="button"><TodayIcon name="spark" /> Generate Plan</button></article><article><h3><b>2</b> Adjust Plan</h3><p>Revise the plan from your check-in and current progress.</p><button disabled={busy} onClick={generatePlan} type="button"><TodayIcon name="edit" /> Adjust Plan</button></article></div>
          </section>
        </main>

        <aside className="today-side-column">
          <form className="today-card daily-checkin-card" onSubmit={saveCheckIn}>
            <div className="side-card-heading"><h2>Daily Check-in</h2><span className={dashboard?.check_in ? "completed" : "pending"}>{dashboard?.check_in ? "Completed" : "Not started"}</span></div>
            <label className="checkin-control"><i className="sleep"><TodayIcon name="sleep" /></i><span>Sleep</span><select value={sleepHours} onChange={(event) => setSleepHours(event.target.value)}>{sleepHourOptions.map((hours) => <option key={hours} value={String(hours)}>{sleepHourLabel(hours)}</option>)}</select></label>
            <label className="checkin-control"><i className="energy"><TodayIcon name="energy" /></i><span>Energy</span><select value={energy} onChange={(event) => setEnergy(event.target.value as EnergyLevel)}><option value="depleted">Depleted</option><option value="low">Low</option><option value="steady">Medium</option><option value="high">High</option><option value="energized">Energized</option></select></label>
            <label className="checkin-control"><i className="mood"><TodayIcon name="mood" /></i><span>Mood</span><select value={mood} onChange={(event) => setMood(event.target.value as MoodLevel)}><option value="struggling">Struggling</option><option value="low">Low</option><option value="neutral">Neutral</option><option value="good">Good</option><option value="great">Great</option></select></label>
            <label className="checkin-control"><i className="calendar"><TodayIcon name="calendar" /></i><span>Available Time Today</span><select value={availableMinutes} onChange={(event) => setAvailableMinutes(event.target.value)}>{AVAILABLE_TIME_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>
            <label className="checkin-control"><i className="target"><TodayIcon name="target" /></i><span>Today’s Focus</span><select value={focusMode} onChange={(event) => setFocusMode(event.target.value as NonNullable<DailyCheckIn["focus_mode"]>)}><option>Deep work</option><option>Meetings</option><option>Study</option><option>Recovery</option></select></label>
            <label className="checkin-control"><i className="difficulty"><TodayIcon name="chart" /></i><span>Difficulty</span><select value={difficulty} onChange={(event) => setDifficulty(event.target.value)}><option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option></select></label>
            <label className="checkin-note"><span>Note (optional)</span><textarea placeholder="How are you feeling today?" rows={3} value={notes} onChange={(event) => setNotes(event.target.value)} /></label>
            <button className="update-checkin-button" disabled={busy} type="submit"><TodayIcon name="check" size={15} /> {dashboard?.check_in ? "Update Check-in" : "Save Check-in"}</button>
          </form>

          <Link className="today-card reflection-button" href="/review"><TodayIcon name="edit" /> Start Reflection</Link>
        </aside>
      </div>
    </section>
  );
}
