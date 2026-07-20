"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  api,
  DailyTask,
  Priority,
  TodayDashboard,
  WeekDashboard,
  WeeklyGoal,
} from "../../lib/api";

type PlanIconName = "spark" | "calendar" | "chart" | "check" | "arrow" | "plus" | "target";

function PlanIcon({ name, size = 17 }: { name: PlanIconName; size?: number }) {
  const paths: Record<PlanIconName, React.ReactNode> = {
    spark: <path d="m12 2 1.6 5.1a5 5 0 0 0 3.3 3.3L22 12l-5.1 1.6a5 5 0 0 0-3.3 3.3L12 22l-1.6-5.1a5 5 0 0 0-3.3-3.3L2 12l5.1-1.6a5 5 0 0 0 3.3-3.3L12 2Z" />,
    calendar: <><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M16 3v4M8 3v4M3 10h18" /></>,
    chart: <><path d="M4 19V9M10 19V5M16 19v-7M22 19H2" /></>,
    check: <><circle cx="12" cy="12" r="9" /><path d="m8 12 2.5 2.5L16 9" /></>,
    arrow: <path d="M5 12h14M15 8l4 4-4 4" />,
    plus: <path d="M12 5v14M5 12h14" />,
    target: <><circle cx="12" cy="12" r="9" /><circle cx="12" cy="12" r="4" /><path d="M12 8V5" /></>,
  };
  return <svg aria-hidden="true" className="plan-icon" fill="none" height={size} viewBox="0 0 24 24" width={size}>{paths[name]}</svg>;
}

function localToday() {
  const now = new Date();
  return new Date(now.getTime() - now.getTimezoneOffset() * 60_000).toISOString().slice(0, 10);
}

// Keep all week-scoped requests anchored to the week selected in the UI.
function dateAt(value: string) {
  return new Date(`${value}T00:00:00`);
}

function addDays(value: string, days: number) {
  const [year, month, day] = value.split("-").map(Number);
  const date = new Date(Date.UTC(year, month - 1, day));
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

function formatHours(minutes: number) {
  const hours = minutes / 60;
  return `${hours % 1 === 0 ? hours.toFixed(0) : hours.toFixed(1)}h`;
}

function isoWeek(value: string) {
  const date = dateAt(value);
  const utc = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
  utc.setUTCDate(utc.getUTCDate() + 4 - (utc.getUTCDay() || 7));
  const yearStart = new Date(Date.UTC(utc.getUTCFullYear(), 0, 1));
  return Math.ceil((((utc.getTime() - yearStart.getTime()) / 86_400_000) + 1) / 7);
}

function taskRank(priority: Priority) {
  return priority === "high" ? 3 : priority === "medium" ? 2 : 1;
}

export default function WeeklyPlanPage() {
  const [weekAnchor, setWeekAnchor] = useState(localToday());
  const [goals, setGoals] = useState<WeeklyGoal[]>([]);
  const [week, setWeek] = useState<WeekDashboard | null>(null);
  const [days, setDays] = useState<TodayDashboard[]>([]);
  const [activeTab, setActiveTab] = useState<"weekly" | "phase">("weekly");
  const [showTaskForm, setShowTaskForm] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const [taskTitle, setTaskTitle] = useState("");
  const [taskHours, setTaskHours] = useState("1");
  const [taskPriority, setTaskPriority] = useState<Priority>("high");

  async function loadPlan(anchor: string) {
    setLoading(true);
    setError("");
    try {
      const [goalData, weekData] = await Promise.all([
        api.getGoalsForWeek(anchor),
        api.getWeekDashboard(anchor),
      ]);
      const dailyData = await Promise.all(
        Array.from({ length: 7 }, (_, index) => api.getDayDashboard(addDays(weekData.week_start, index))),
      );
      setGoals(goalData);
      setWeek(weekData);
      setDays(dailyData);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Failed to load weekly plan");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadPlan(weekAnchor);
  }, []);

  const allTasks = useMemo(
    () => days.flatMap((day) => day.unfinished_tasks).sort((left, right) =>
      taskRank(right.priority) - taskRank(left.priority) ||
      left.task_date.localeCompare(right.task_date) ||
      left.id - right.id,
    ),
    [days],
  );
  const priorities = allTasks.slice(0, 6);
  const highPriorityCount = allTasks.filter((task) => task.priority === "high").length;
  const plannedMinutes = week?.daily_focus.reduce((sum, point) => sum + point.planned_minutes, 0) ?? 0;
  const targetMinutes = goals.reduce((sum, goal) => sum + (goal.target_minutes ?? 0), 0);
  const completion = Math.round((week?.completion_rate ?? 0) * 100);
  const planVsGoal = targetMinutes ? Math.round((plannedMinutes / targetMinutes) * 100) : 0;
  const weekLabel = week
    ? `${dateAt(week.week_start).toLocaleDateString("en", { month: "short", day: "numeric" })} – ${dateAt(week.week_end).toLocaleDateString("en", { month: "short", day: "numeric", year: "numeric" })} (Week ${isoWeek(week.week_start)})`
    : "Loading week…";
  const suggestion = highPriorityCount > 3
    ? `You have ${highPriorityCount} high-impact priorities. Complete the first ${Math.min(3, highPriorityCount)} before adding more work.`
    : plannedMinutes > targetMinutes && targetMinutes > 0
      ? `This plan is ${formatHours(plannedMinutes - targetMinutes)} above your weekly goal. Move one lower-impact item into the buffer.`
      : "The week has room for focused work. Protect your strongest mornings for the first priorities.";

  async function selectWeek(anchor: string) {
    setMessage("");
    setWeekAnchor(anchor);
    await loadPlan(anchor);
  }

  async function moveWeek(offset: number) {
    await selectWeek(addDays(week?.week_start ?? weekAnchor, offset * 7));
  }

  async function createTask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!week) return;
    const today = localToday();
    const taskDate = today >= week.week_start && today <= week.week_end ? today : week.week_start;
    setBusy(true);
    try {
      await api.createTask({
        title: taskTitle,
        task_date: taskDate,
        estimated_minutes: taskHours ? Math.round(Number(taskHours) * 60) : null,
        priority: taskPriority,
        weekly_goal_id: goals.find((goal) => goal.status === "active")?.id ?? null,
        source: "manual",
      });
      setTaskTitle("");
      setShowTaskForm(false);
      setMessage("Priority added to the weekly plan.");
      await loadPlan(weekAnchor);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Failed to add priority");
    } finally {
      setBusy(false);
    }
  }

  async function completeTask(task: DailyTask) {
    setBusy(true);
    try {
      await api.updateTask(task.id, { status: "completed" });
      setMessage(`Completed: ${task.title}`);
      await loadPlan(weekAnchor);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Failed to complete priority");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="plans-page weekly-reference-page">
      <header className="plans-header">
        <div><h1>Weekly Plan</h1><p>Stay aligned with your goals. Adjust on the day, guided by AI.</p></div>
        <div className="plans-header-actions">
          <Link aria-label="Open calendar" href="/today"><PlanIcon name="calendar" size={20} /></Link>
          <Link className="plans-coach-button" href="/check-in"><PlanIcon name="spark" /> Ask my coach <span>⌄</span></Link>
        </div>
      </header>

      <div className="plans-tabs" role="tablist">
        <button aria-selected={activeTab === "weekly"} className={activeTab === "weekly" ? "active" : ""} onClick={() => setActiveTab("weekly")} role="tab" type="button">Weekly Plan</button>
        <button aria-selected={activeTab === "phase"} className={activeTab === "phase" ? "active" : ""} onClick={() => setActiveTab("phase")} role="tab" type="button">Phase Plan</button>
      </div>

      {error ? <div className="error plans-feedback">{error}</div> : null}
      {message ? <div className="success plans-feedback">{message}</div> : null}

      {activeTab === "phase" ? (
        <div className="phase-plan-view">
          <div><p className="eyebrow">Phase plan</p><h2>Build the next phase from weekly outcomes</h2><p>Use completed weeks as the foundation for your next longer planning cycle.</p></div>
          <button className="outline-purple" onClick={() => setActiveTab("weekly")} type="button">Return to weekly plan</button>
        </div>
      ) : (
        <main className="weekly-reference-content">
          <nav aria-label="Select week" className="week-selector">
            <div>
              <button aria-label="Previous week" disabled={loading} onClick={() => moveWeek(-1)} type="button">‹</button>
              <button aria-label="Next week" disabled={loading} onClick={() => moveWeek(1)} type="button">›</button>
              <PlanIcon name="calendar" size={15} />
              <strong>{weekLabel}</strong>
              <button aria-label="Go to current week" disabled={loading || weekAnchor === localToday()} onClick={() => selectWeek(localToday())} type="button">Today</button>
            </div>
            <Link className="outline-purple" href="/weekly-review"><PlanIcon name="chart" /> This Week&apos;s Review</Link>
          </nav>

          <section className="plan-card week-overview-card">
            <h2>This Week Overview</h2>
            <div className="week-overview-grid">
              <div><span>Weekly Goal</span><strong>{targetMinutes ? formatHours(targetMinutes) : "—"}</strong><small>Focus time</small></div>
              <div><span>Planned Focus</span><strong>{formatHours(plannedMinutes)}</strong><small>{targetMinutes ? `${planVsGoal}% of goal` : "Set a goal below"}</small></div>
              <div><span>Tasks</span><strong>{week?.planned_tasks ?? 0}</strong><small>Planned</small></div>
              <div><span>Priority Tasks</span><strong>{highPriorityCount}</strong><small>High impact</small></div>
              <div className="overview-progress">
                <i style={{ background: `conic-gradient(#24a84b ${completion * 3.6}deg, #e7eee8 0deg)` }}><b>{completion}%</b></i>
                <span><strong>Overall Progress</strong><small>{week?.completed_tasks ?? 0} of {week?.planned_tasks ?? 0} completed</small></span>
              </div>
            </div>
          </section>

          <section className="plan-card key-priorities-card">
            <div className="priority-section-heading">
              <div><h2><PlanIcon name="target" /> Key Priorities This Week</h2><p>Focus on what matters most. Check items off as you finish.</p></div>
            </div>
            <div className="priority-content-grid">
              <div className="reference-priority-list">
                {loading ? <p>Loading priorities…</p> : null}
                {!loading && priorities.length === 0 ? <p>No priorities yet. Add the first meaningful task for this week.</p> : null}
                {priorities.map((task, index) => (
                  <div key={task.id}>
                    <button aria-label={`Complete ${task.title}`} disabled={busy} onClick={() => completeTask(task)} type="button">{index + 1}</button>
                    <span>{task.title}</span>
                    <b className={task.priority}>{task.priority}</b>
                    <small>{task.estimated_minutes ? `Est. ${formatHours(task.estimated_minutes)}` : "Flexible"}</small>
                  </div>
                ))}
                <button className="add-priority-button" onClick={() => setShowTaskForm((show) => !show)} type="button"><PlanIcon name="plus" size={14} /> Add Priority</button>
              </div>
              <aside className="weekly-ai-suggestion">
                <h3><PlanIcon name="spark" /> AI Suggestion</h3>
                <p>{suggestion}</p>
                <Link href="/check-in">View Details <PlanIcon name="arrow" size={14} /></Link>
              </aside>
            </div>

            {showTaskForm ? <form className="reference-task-form" onSubmit={createTask}>
              <input maxLength={255} placeholder="Priority title" required value={taskTitle} onChange={(event) => setTaskTitle(event.target.value)} />
              <input aria-label="Estimated hours" min="0.25" placeholder="Hours" step="0.25" type="number" value={taskHours} onChange={(event) => setTaskHours(event.target.value)} />
              <select aria-label="Priority level" value={taskPriority} onChange={(event) => setTaskPriority(event.target.value as Priority)}><option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option></select>
              <button disabled={busy} type="submit">Save priority</button>
              <button onClick={() => setShowTaskForm(false)} type="button">Cancel</button>
            </form> : null}
          </section>
        </main>
      )}
    </section>
  );
}
