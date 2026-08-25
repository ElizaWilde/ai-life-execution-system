"use client";

import Link from "next/link";
import { DragEvent, FormEvent, useCallback, useEffect, useState } from "react";
import {
  api,
  DailyCheckIn,
  DailyPlanPreview,
  DailyTask,
  EnergyLevel,
  MoodLevel,
  Priority,
  TaskChannel,
  TodayDashboard,
  WeeklyGoal,
} from "../../lib/api";
import { useAppSettings, workloadMinutes } from "../../lib/settings";
import { announceCheckInUpdate, subscribeToCheckInUpdates } from "../../lib/check-in-sync";
import { subscribeToTaskUpdates } from "../../lib/task-sync";
import { AVAILABLE_TIME_OPTIONS, availableTimeBucket } from "../../lib/check-in-options";
import DailyReviewModule from "../../components/daily-review-module";
import WitchHatIcon from "../../components/common/WitchHatIcon";
import TodayCalendar from "../../components/today-calendar";

type TodayIconName = "spark" | "clock" | "check" | "trash" | "sleep" | "energy" | "mood" | "calendar" | "target" | "chart" | "edit";

function TodayIcon({ name, size = 18 }: { name: TodayIconName; size?: number }) {
  if (name === "spark") return <WitchHatIcon size={size} />;
  const paths: Record<Exclude<TodayIconName, "spark">, React.ReactNode> = {
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

function addLocalDays(value: string, days: number) {
  const [year, month, day] = value.split("-").map(Number);
  const result = new Date(Date.UTC(year, month - 1, day + days));
  return result.toISOString().slice(0, 10);
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
const TASK_TIME_OPTIONS = [5, 10, 15, 20, 25, 30, 45, 60, 90, 120, 180];
const TASK_CHANNELS: { value: TaskChannel; label: string }[] = [
  { value: "work", label: "Work" },
  { value: "assignments", label: "Assignments" },
  { value: "networking", label: "Networking" },
  { value: "projects", label: "Projects" },
  { value: "study", label: "Study" },
  { value: "personal", label: "Personal" },
];

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
  const tomorrow = addLocalDays(today, 1);
  const [tasks, setTasks] = useState<DailyTask[]>([]);
  const [weeklyGoals, setWeeklyGoals] = useState<WeeklyGoal[]>([]);
  const [dashboard, setDashboard] = useState<TodayDashboard | null>(null);
  const [previewDate, setPreviewDate] = useState(today);
  const [dailyPreviews, setDailyPreviews] = useState<Record<string, DailyPlanPreview | null>>({});
  const [showAddTask, setShowAddTask] = useState(false);
  const [editingTaskId, setEditingTaskId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [activeTodayTab, setActiveTodayTab] = useState<"plan" | "review">("plan");
  const [comparisonDirection, setComparisonDirection] = useState<"previous" | "next" | null>(null);
  const [comparisonTasks, setComparisonTasks] = useState<DailyTask[]>([]);
  const [comparisonDashboard, setComparisonDashboard] = useState<TodayDashboard | null>(null);
  const [comparisonLoading, setComparisonLoading] = useState(false);
  const [draggedTaskId, setDraggedTaskId] = useState<number | null>(null);
  const [dragOverDate, setDragOverDate] = useState<string | null>(null);
  const [editingTaskDate, setEditingTaskDate] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [planInstruction, setPlanInstruction] = useState("");
  const [planAction, setPlanAction] = useState<"build" | "refine" | "confirm" | null>(null);

  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [taskMinutes, setTaskMinutes] = useState("30");
  const [taskChannel, setTaskChannel] = useState<TaskChannel | "">("");
  const [selectedGoalId, setSelectedGoalId] = useState("");
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
      const [taskData, dashboardData, todayPreview, tomorrowPreview, goalData] = await Promise.all([
        api.getTasksForDate(today),
        api.getTodayDashboard(),
        api.getLatestDailyPlanPreview(today),
        api.getLatestDailyPlanPreview(tomorrow),
        api.getCurrentGoals(),
      ]);
      setTasks(taskData);
      setWeeklyGoals(goalData.filter((goal) => goal.status === "active"));
      setDashboard(dashboardData);
      setDailyPreviews({ [today]: todayPreview, [tomorrow]: tomorrowPreview });
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
    const unsubscribeCheckIns = subscribeToCheckInUpdates(today, loadToday);
    const unsubscribeTasks = subscribeToTaskUpdates(loadToday);
    return () => {
      unsubscribeCheckIns();
      unsubscribeTasks();
    };
  }, [today]);

  useEffect(() => {
    if (dashboard?.check_in?.available_minutes === null || dashboard?.check_in?.available_minutes === undefined) {
      setAvailableMinutes(availableTimeBucket(workloadMinutes(appSettings.workload)));
    }
  }, [appSettings.workload, dashboard?.check_in?.available_minutes]);

  const completion = Math.round((dashboard?.weighted_progress_rate ?? 0) * 100);
  const circumference = 2 * Math.PI * 34;
  const plannedFocusMinutes = tasks
    .filter((task) => task.status !== "cancelled")
    .reduce((total, task) => total + (task.estimated_minutes ?? 0), 0);
  const comparisonDate = comparisonDirection
    ? addLocalDays(today, comparisonDirection === "previous" ? -1 : 1)
    : null;
  const sortedTasks = [...tasks].sort((left, right) =>
    Number(left.status === "completed") - Number(right.status === "completed") || left.id - right.id,
  );

  async function createTask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const taskData = {
        title,
        description: description.trim() || null,
        estimated_minutes: taskMinutes ? Number(taskMinutes) : null,
        channel: taskChannel || null,
        weekly_goal_id: selectedGoalId ? Number(selectedGoalId) : null,
        priority,
      };
      if (editingTaskId) {
        await api.updateTask(editingTaskId, taskData);
        setMessage("Task updated.");
      } else {
        await api.createTask({ ...taskData, task_date: today, source: "manual" });
        setMessage("Task added.");
      }
      setTitle("");
      setDescription("");
      setTaskMinutes("30");
      setTaskChannel("");
      setSelectedGoalId("");
      setPriority("medium");
      setEditingTaskId(null);
      setEditingTaskDate(null);
      setShowAddTask(false);
      await loadToday();
      if (comparisonDirection) await loadAdjacentPlan(comparisonDirection);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Failed to create task");
    } finally {
      setBusy(false);
    }
  }

  async function loadAdjacentPlan(direction: "previous" | "next") {
    const targetDate = addLocalDays(today, direction === "previous" ? -1 : 1);
    setComparisonLoading(true);
    try {
      const [taskData, dashboardData] = await Promise.all([
        api.getTasksForDate(targetDate),
        api.getDayDashboard(targetDate),
      ]);
      setComparisonTasks(taskData);
      setComparisonDashboard(dashboardData);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Failed to load adjacent plan");
      throw reason;
    } finally {
      setComparisonLoading(false);
    }
  }

  async function showAdjacentPlan(direction: "previous" | "next") {
    if (comparisonDirection === direction) {
      setComparisonDirection(null);
      setComparisonTasks([]);
      setComparisonDashboard(null);
      return;
    }
    setActiveTodayTab("plan");
    setComparisonDirection(direction);
    setError("");
    try {
      await loadAdjacentPlan(direction);
    } catch {
      setComparisonDirection(null);
    }
  }

  async function moveTaskToDate(task: DailyTask, targetDate: string) {
    if (!comparisonDirection) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await api.updateTask(task.id, { task_date: targetDate });
      await Promise.all([loadToday(), loadAdjacentPlan(comparisonDirection)]);
      setMessage(`Moved “${task.title}” to ${targetDate === today ? "today" : new Date(`${targetDate}T00:00:00`).toLocaleDateString("en", { weekday: "long", month: "short", day: "numeric" })}.`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Failed to move task");
    } finally {
      setBusy(false);
    }
  }

  function editTask(task: DailyTask) {
    setEditingTaskId(task.id);
    setEditingTaskDate(task.task_date);
    setTitle(task.title);
    setDescription(task.description ?? "");
    setTaskMinutes(task.estimated_minutes ? String(task.estimated_minutes) : "30");
    setTaskChannel(task.channel ?? "");
    setSelectedGoalId(task.weekly_goal_id ? String(task.weekly_goal_id) : "");
    setPriority(task.priority);
    setShowAddTask(true);
  }

  function cancelTaskForm() {
    setEditingTaskId(null);
    setTitle("");
    setDescription("");
    setTaskMinutes("30");
    setTaskChannel("");
    setSelectedGoalId("");
    setPriority("medium");
    setShowAddTask(false);
    setEditingTaskDate(null);
  }

  async function setStatus(task: DailyTask, status: DailyTask["status"]) {
    setBusy(true);
    try {
      await api.updateTask(task.id, { status });
      await loadToday();
      if (comparisonDirection) await loadAdjacentPlan(comparisonDirection);
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
      if (comparisonDirection) await loadAdjacentPlan(comparisonDirection);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Failed to delete task");
    } finally {
      setBusy(false);
    }
  }

  const updateTaskSchedule = useCallback(async (
    task: DailyTask,
    values: { scheduled_start_minutes: number; estimated_minutes: number },
  ) => {
    setBusy(true);
    setError("");
    try {
      const updated = await api.updateTask(task.id, values);
      setTasks((current) => current.map((item) => item.id === updated.id ? updated : item));
      setMessage(`Updated the time slot for ${task.title}.`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Failed to update the task time slot");
    } finally {
      setBusy(false);
    }
  }, []);

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

  async function generatePlan(targetDate = previewDate, userInstruction?: string) {
    setBusy(true);
    setPlanAction(userInstruction?.trim() ? "refine" : "build");
    setError("");
    setMessage("");
    try {
      const instruction = userInstruction?.trim();
      const existingPreview = dailyPreviews[targetDate];
      const result = await api.createDailyPlanPreview({
        available_minutes: Number(availableMinutes),
        target_date: targetDate,
        ...(instruction ? { user_instruction: instruction } : {}),
        ...(instruction && existingPreview ? { base_preview_id: existingPreview.id } : {}),
      });
      setDailyPreviews((current) => ({ ...current, [targetDate]: result }));
      setPreviewDate(targetDate);
      if (instruction) setPlanInstruction("");
      setMessage(`${instruction ? "Adjusted" : "Generated"} a ${targetDate === today ? "today" : "tomorrow"} preview with ${result.tasks.length} tasks. Confirm it before tasks are added.`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Failed to generate plan");
    } finally {
      setBusy(false);
      setPlanAction(null);
    }
  }

  function startTaskDrag(event: DragEvent<HTMLButtonElement>, task: DailyTask) {
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("text/plain", String(task.id));
    setDraggedTaskId(task.id);
  }

  function allowTaskDrop(event: DragEvent<HTMLElement>, targetDate: string) {
    const task = [...tasks, ...comparisonTasks].find((item) => item.id === draggedTaskId);
    if (!task || task.task_date === targetDate) return;
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
    setDragOverDate(targetDate);
  }

  async function dropTask(event: DragEvent<HTMLElement>, targetDate: string) {
    event.preventDefault();
    const taskId = Number(event.dataTransfer.getData("text/plain") || draggedTaskId);
    const task = [...tasks, ...comparisonTasks].find((item) => item.id === taskId);
    setDragOverDate(null);
    setDraggedTaskId(null);
    if (!task || task.task_date === targetDate) return;
    await moveTaskToDate(task, targetDate);
  }

  function finishTaskDrag() {
    setDraggedTaskId(null);
    setDragOverDate(null);
  }

  async function confirmPlanPreview(preview: DailyPlanPreview) {
    setBusy(true);
    setPlanAction("confirm");
    setError("");
    try {
      const confirmed = await api.confirmDailyPlanPreview(preview.id);
      setDailyPreviews((current) => ({ ...current, [preview.target_date]: confirmed }));
      setMessage(`${preview.target_date === today ? "Today’s" : "Tomorrow’s"} plan was confirmed.`);
      await loadToday();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Failed to confirm plan preview");
    } finally {
      setBusy(false);
      setPlanAction(null);
    }
  }

  function adjustPlan(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!planInstruction.trim()) return;
    void generatePlan(previewDate, planInstruction);
  }

  function renderTaskForm(submitLabel: string) {
    return (
      <form className="today-add-form" onSubmit={createTask}>
        <div className="today-task-core-fields">
          <label>
            <span>Task</span>
            <input className="input" placeholder="What needs to get done?" required value={title} onChange={(event) => setTitle(event.target.value)} />
          </label>
          <label>
            <span>Description</span>
            <input className="input" placeholder="Add helpful details or a clear next step" value={description} onChange={(event) => setDescription(event.target.value)} />
          </label>
        </div>
        <div className="today-task-metadata">
          <label>
            <span><TodayIcon name="clock" size={14} /> Planned time</span>
            <select aria-label="Planned time" className="input" value={taskMinutes} onChange={(event) => setTaskMinutes(event.target.value)}>
              {TASK_TIME_OPTIONS.map((minutes) => <option key={minutes} value={minutes}>{formatMinutes(minutes)}</option>)}
            </select>
          </label>
          <label>
            <span><b className="today-form-hash">#</b> Channel</span>
            <select aria-label="Assign to channel" className="input" value={taskChannel} onChange={(event) => setTaskChannel(event.target.value as TaskChannel | "")}>
              <option value="">Unassigned</option>
              {TASK_CHANNELS.map((channel) => <option key={channel.value} value={channel.value}>{channel.label}</option>)}
            </select>
          </label>
          <label>
            <span><TodayIcon name="target" size={14} /> Objective</span>
            <select aria-label="Align with objective" className="input" value={selectedGoalId} onChange={(event) => setSelectedGoalId(event.target.value)}>
              <option value="">Unassigned</option>
              {weeklyGoals.map((goal) => <option key={goal.id} value={goal.id}>{goal.title}</option>)}
            </select>
          </label>
          <label>
            <span><TodayIcon name="chart" size={14} /> Daily priority</span>
            <select aria-label="Daily priority" className="input" value={priority} onChange={(event) => setPriority(event.target.value as Priority)}>
              <option value="urgent">Urgent</option>
              <option value="high">Priority</option>
              <option value="medium">Normal</option>
              <option value="low">Low Priority</option>
            </select>
          </label>
        </div>
        <div className="today-task-form-actions">
          <button className="today-primary-button" disabled={busy} type="submit">{submitLabel}</button>
          <button className="today-add-cancel" onClick={cancelTaskForm} type="button">Cancel</button>
        </div>
      </form>
    );
  }

  const date = new Date(`${today}T00:00:00`);

  return (
    <section className="today-workspace">
      <header className="today-workspace-header">
        <div><h1>Today</h1><p>{date.toLocaleDateString("en", { weekday: "short", month: "short", day: "numeric", year: "numeric" })} <span>⌄</span></p></div>
        <div className="today-greeting"><TodayIcon name="spark" size={34} /><div><strong>Hey, ready to make today count?</strong><span>Plan your day, check in with yourself, and let’s get things done.</span></div></div>
        <Link className="today-coach-button" href="/coach"><TodayIcon name="spark" /> Ask my coach <span>⌄</span></Link>
      </header>

      {error ? <div className="error today-feedback">{error}</div> : null}
      {message ? <div className="success today-feedback">{message}</div> : null}

      <nav aria-label="Today sections" className="workspace-section-tabs">
        <button className={activeTodayTab === "plan" ? "active" : ""} onClick={() => setActiveTodayTab("plan")} type="button">Today’s Plan</button>
        <button className={activeTodayTab === "review" ? "active" : ""} onClick={() => { setActiveTodayTab("review"); setComparisonDirection(null); }} type="button">Today’s Review</button>
        <span className="today-date-arrows">
          <button aria-label="Compare with previous day" className={comparisonDirection === "previous" ? "selected" : ""} disabled={comparisonLoading} onClick={() => showAdjacentPlan("previous")} title="Previous day" type="button">←</button>
          <button aria-label="Compare with next day" className={comparisonDirection === "next" ? "selected" : ""} disabled={comparisonLoading} onClick={() => showAdjacentPlan("next")} title="Next day" type="button">→</button>
        </span>
      </nav>

      <div className={`today-workspace-grid ${activeTodayTab === "review" ? "show-review" : "show-plan"} ${comparisonDirection ? `is-comparing compare-${comparisonDirection}` : ""}`}>
        <main className="today-main-column">
          {comparisonDirection ? (
            <section
              className={`today-card adjacent-plan-card ${dragOverDate === comparisonDate ? "drag-over" : ""}`}
              onDragLeave={() => setDragOverDate(null)}
              onDragOver={(event) => comparisonDate && allowTaskDrop(event, comparisonDate)}
              onDrop={(event) => comparisonDate && dropTask(event, comparisonDate)}
            >
              <div className="today-plan-heading">
                <div>
                  <h2>{comparisonDirection === "previous" ? "Previous Day’s Plan" : "Next Day’s Plan"}</h2>
                  <span>{new Date(`${comparisonDate}T00:00:00`).toLocaleDateString("en", { weekday: "short", month: "short", day: "numeric" })}</span>
                </div>
              </div>
              <div className="adjacent-plan-summary">
                <div><strong>{Math.round((comparisonDashboard?.weighted_progress_rate ?? 0) * 100)}%</strong><span>Time + priority</span></div>
                <div><strong>{formatMinutes(comparisonDashboard?.focus_minutes ?? 0)}</strong><span>Focus time</span></div>
                <div><strong>{comparisonDashboard?.completed_tasks ?? 0} / {comparisonDashboard?.planned_tasks ?? comparisonTasks.length}</strong><span>Completed</span></div>
              </div>
              <div className="today-work-list">
                {comparisonLoading ? <p className="today-empty">Loading plan…</p> : null}
                {!comparisonLoading && !comparisonTasks.length ? <p className="today-empty">No tasks planned for this day.</p> : null}
                {comparisonTasks.map((task) => (
                  <article className={`today-work-row adjacent-task-row ${task.status === "completed" ? "completed" : ""} ${draggedTaskId === task.id ? "dragging" : ""}`} key={task.id}>
                    <button
                      aria-label={`Drag ${task.title} to another day`}
                      className={`plan-completion-toggle task-drag-handle ${task.status === "completed" ? "completed" : ""}`}
                      disabled={busy}
                      draggable
                      onClick={() => setStatus(task, task.status === "completed" ? "pending" : "completed")}
                      onDragEnd={finishTaskDrag}
                      onDragStart={(event) => startTaskDrag(event, task)}
                      title="Click to complete or drag to another day"
                      type="button"
                    >{task.status === "completed" ? <TodayIcon name="check" size={12} /> : null}</button>
                    <span className="priority-title">{task.title}{task.is_overdue ? <em className="task-overdue-badge">Overdue</em> : null}</span>
                    <b className={`today-priority ${task.priority}`}>{task.priority}</b>
                    <small>{task.estimated_minutes ? `Est. ${formatHours(task.estimated_minutes)}` : "Flexible"}</small>
                    <div className="priority-row-actions">
                      <button aria-label={`Edit ${task.title}`} className="priority-edit-button" disabled={busy} onClick={() => editTask(task)} title="Edit task" type="button"><TodayIcon name="edit" size={17} /></button>
                      <button aria-label={`Delete ${task.title}`} className="priority-delete-button" disabled={busy} onClick={() => deleteTask(task)} title="Delete task" type="button"><TodayIcon name="trash" size={17} /></button>
                    </div>
                  </article>
                ))}
                {showAddTask && editingTaskId && editingTaskDate === comparisonDate ? renderTaskForm("Save changes") : null}
              </div>
            </section>
          ) : null}
          <section
            className={`today-card today-plan-card ${dragOverDate === today ? "drag-over" : ""}`}
            onDragLeave={() => setDragOverDate(null)}
            onDragOver={(event) => allowTaskDrop(event, today)}
            onDrop={(event) => dropTask(event, today)}
          >
            <div className="today-plan-heading"><div><h2>Today’s Plan</h2><span>{tasks.length} tasks · includes Weekly Plan</span></div></div>

            <div className="today-progress-card">
              <div className="today-progress-ring"><svg viewBox="0 0 80 80"><circle className="track" cx="40" cy="40" r="34" /><circle className="value" cx="40" cy="40" r="34" strokeDasharray={circumference} strokeDashoffset={circumference * (1 - completion / 100)} /></svg><strong>{completion}%</strong></div>
              <div className="progress-copy"><strong>Daily Progress</strong><span>Focused time + priority weighted</span></div>
              <div className="progress-divider" />
              <span className="progress-metric-icon blue"><TodayIcon name="clock" /></span><div className="progress-copy"><strong>Focus Time</strong><span>{formatMinutes(dashboard?.focus_minutes ?? 0)} / {formatHours(plannedFocusMinutes)}</span></div>
              <div className="progress-divider" />
              <span className="progress-metric-icon green"><TodayIcon name="check" /></span><div className="progress-copy"><strong>Tasks Completed</strong><span>{dashboard?.completed_tasks ?? 0} / {dashboard?.planned_tasks ?? tasks.length}</span></div>
            </div>

            <div className="today-work-list">
              {loading ? <p className="today-empty">Loading today’s plan…</p> : null}
              {!loading && !sortedTasks.length ? <p className="today-empty">No tasks yet. Add the first task for today.</p> : null}
              {sortedTasks.map((task) => <article className={`today-work-row ${task.status === "completed" ? "completed" : ""} ${task.is_overdue ? "overdue" : ""} ${draggedTaskId === task.id ? "dragging" : ""}`} key={task.id}>
                <button aria-label={`Drag ${task.title} to another day`} className={`plan-completion-toggle task-drag-handle ${task.status === "completed" ? "completed" : ""}`} disabled={busy} draggable={Boolean(comparisonDirection)} onClick={() => setStatus(task, task.status === "completed" ? "pending" : "completed")} onDragEnd={finishTaskDrag} onDragStart={(event) => startTaskDrag(event, task)} title={comparisonDirection ? "Click to complete or drag to another day" : task.status === "completed" ? "Reopen task" : "Mark complete"} type="button">{task.status === "completed" ? <TodayIcon name="check" size={12} /> : null}</button>
                <span className="priority-title">{task.title}{task.is_overdue ? <em className="task-overdue-badge">Overdue</em> : null}</span>
                <b className={`today-priority ${task.priority}`}>{task.priority}</b>
                <small>{task.estimated_minutes ? `Est. ${formatHours(task.estimated_minutes)}` : "Flexible"}</small>
                <div className="priority-row-actions">
                  <button aria-label={`Edit ${task.title}`} className="priority-edit-button" disabled={busy} onClick={() => editTask(task)} title="Edit task" type="button"><TodayIcon name="edit" size={17} /></button>
                  <button aria-label={`Delete ${task.title}`} className="priority-delete-button" disabled={busy} onClick={() => deleteTask(task)} title="Delete task" type="button"><TodayIcon name="trash" size={17} /></button>
                </div>
              </article>)}
              {showAddTask && (!editingTaskId || editingTaskDate === today) ? renderTaskForm(editingTaskId ? "Save changes" : "Add task") : null}
              {!showAddTask ? <button className="today-add-bottom" onClick={() => { setEditingTaskId(null); setEditingTaskDate(today); setShowAddTask(true); }} type="button">＋ Add Task</button> : null}
            </div>
          </section>

          <DailyReviewModule
            dashboard={dashboard}
            date={today}
            tasks={tasks}
          />

          <form className="today-card daily-checkin-card today-review-checkin" onSubmit={saveCheckIn}>
            <div className="side-card-heading"><h2>Daily Check-in</h2><span className={dashboard?.check_in ? "completed" : "pending"}>{dashboard?.check_in ? "Completed" : "Not started"}</span></div>
            <div className="today-review-checkin-grid">
              <label className="checkin-control"><i className="sleep"><TodayIcon name="sleep" /></i><span>Sleep</span><select value={sleepHours} onChange={(event) => setSleepHours(event.target.value)}>{sleepHourOptions.map((hours) => <option key={hours} value={String(hours)}>{sleepHourLabel(hours)}</option>)}</select></label>
              <label className="checkin-control"><i className="energy"><TodayIcon name="energy" /></i><span>Energy</span><select value={energy} onChange={(event) => setEnergy(event.target.value as EnergyLevel)}><option value="depleted">Depleted</option><option value="low">Low</option><option value="steady">Medium</option><option value="high">High</option><option value="energized">Energized</option></select></label>
              <label className="checkin-control"><i className="mood"><TodayIcon name="mood" /></i><span>Mood</span><select value={mood} onChange={(event) => setMood(event.target.value as MoodLevel)}><option value="struggling">Struggling</option><option value="low">Low</option><option value="neutral">Neutral</option><option value="good">Good</option><option value="great">Great</option></select></label>
              <label className="checkin-control"><i className="calendar"><TodayIcon name="calendar" /></i><span>Available Time Today</span><select value={availableMinutes} onChange={(event) => setAvailableMinutes(event.target.value)}>{AVAILABLE_TIME_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>
              <label className="checkin-control"><i className="target"><TodayIcon name="target" /></i><span>Today’s Focus</span><select value={focusMode} onChange={(event) => setFocusMode(event.target.value as NonNullable<DailyCheckIn["focus_mode"]>)}><option>Deep work</option><option>Meetings</option><option>Study</option><option>Recovery</option></select></label>
              <label className="checkin-control"><i className="difficulty"><TodayIcon name="chart" /></i><span>Difficulty</span><select value={difficulty} onChange={(event) => setDifficulty(event.target.value)}><option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option></select></label>
            </div>
            <label className="checkin-note"><span>Note (optional)</span><textarea placeholder="How are you feeling today?" rows={3} value={notes} onChange={(event) => setNotes(event.target.value)} /></label>
            <button className="update-checkin-button" disabled={busy} type="submit"><TodayIcon name="check" size={15} /> {dashboard?.check_in ? "Update Check-in" : "Save Check-in"}</button>
          </form>

          <section className="today-card ai-plan-card ai-plan-main-card">
            <div className="side-card-heading"><h2>Plan Preview</h2><span>Nothing changes until you confirm</span></div><p>Preview a calibrated plan for today or tomorrow.</p>
            <div className="daily-preview-tabs">
              <button className={previewDate === today ? "active" : ""} onClick={() => setPreviewDate(today)} type="button">Today</button>
              <button className={previewDate === tomorrow ? "active" : ""} onClick={() => setPreviewDate(tomorrow)} type="button">Tomorrow</button>
            </div>
            {dailyPreviews[previewDate] ? <div className="adaptive-inline"><strong>{Math.round(dailyPreviews[previewDate]!.readiness_score)} readiness</strong><span>{dailyPreviews[previewDate]!.recommended_minutes} min planned · {dailyPreviews[previewDate]!.calibration.factor.toFixed(2)}× estimate calibration</span></div> : null}
            {dailyPreviews[previewDate]?.tasks.length ? <div className="daily-preview-list">{dailyPreviews[previewDate]!.tasks.map((task, index) => <div key={`${task.title}-${index}`}><span>{task.title}</span><b className={task.priority}>{task.priority}</b><small>{formatMinutes(task.estimated_minutes)}</small></div>)}</div> : null}
            <div className="ai-plan-actions">
              <article>
                <h3><b>1</b> Build Preview</h3>
                <p>Use weekly goals, check-in data, history, and linked focus sessions.</p>
                <button disabled={busy} onClick={() => generatePlan(previewDate)} type="button">
                  <TodayIcon name="spark" />
                  {planAction === "build" ? "Building preview…" : dailyPreviews[previewDate] ? "Regenerate Preview" : "Generate Preview"}
                </button>
              </article>
              <article className="ai-adjust-card">
                <h3><b>2</b> Refine & Confirm</h3>
                <form className="ai-adjust-form" onSubmit={adjustPlan}>
                  <input aria-label="Tell AI how to adjust the plan preview" disabled={busy} maxLength={1000} onChange={(event) => setPlanInstruction(event.target.value)} placeholder="e.g. Make it lighter and prioritize API work" value={planInstruction} />
                  <button aria-label="Adjust plan preview with AI" disabled={busy || !planInstruction.trim() || !dailyPreviews[previewDate]} title={dailyPreviews[previewDate] ? "Adjust preview" : "Build a preview first"} type="submit"><TodayIcon name="spark" size={15} /></button>
                </form>
                {planAction === "refine" ? <span className="preview-working">Refining the current preview…</span> : dailyPreviews[previewDate]?.status === "pending" ? <button className="confirm-plan-preview" disabled={busy} onClick={() => confirmPlanPreview(dailyPreviews[previewDate]!)} type="button"><TodayIcon name="check" size={14} /> {planAction === "confirm" ? "Confirming…" : `Confirm ${previewDate === today ? "Today" : "Tomorrow"}`}</button> : dailyPreviews[previewDate]?.status === "confirmed" ? <span className="preview-confirmed"><TodayIcon name="check" size={13} /> Confirmed</span> : null}
              </article>
            </div>
          </section>
        </main>

        <aside className="today-side-column">
          <TodayCalendar busy={busy} date={today} onScheduleChange={updateTaskSchedule} tasks={tasks} />
        </aside>
      </div>
    </section>
  );
}
