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
import { orderByWeekStart, useAppSettings, workloadMinutes } from "../../lib/settings";

type PlanIconName = "spark" | "clock" | "check" | "alert" | "calendar" | "refresh" | "arrow";

function PlanIcon({ name, size = 17 }: { name: PlanIconName; size?: number }) {
  const paths: Record<PlanIconName, React.ReactNode> = {
    spark: <path d="m12 2 1.6 5.1a5 5 0 0 0 3.3 3.3L22 12l-5.1 1.6a5 5 0 0 0-3.3 3.3L12 22l-1.6-5.1a5 5 0 0 0-3.3-3.3L2 12l5.1-1.6a5 5 0 0 0 3.3-3.3L12 2Z" />,
    clock: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
    check: <><circle cx="12" cy="12" r="9" /><path d="m8 12 2.5 2.5L16 9" /></>,
    alert: <><path d="M10.3 3.8 2.7 17a2 2 0 0 0 1.7 3h15.2a2 2 0 0 0 1.7-3L13.7 3.8a2 2 0 0 0-3.4 0Z" /><path d="M12 9v4M12 17h.01" /></>,
    calendar: <><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M16 3v4M8 3v4M3 10h18" /></>,
    refresh: <><path d="M20 7v5h-5" /><path d="M19 12a7 7 0 1 1-2-5" /></>,
    arrow: <path d="M5 12h14M15 8l4 4-4 4" />,
  };
  return <svg aria-hidden="true" className="plan-icon" fill="none" height={size} viewBox="0 0 24 24" width={size}>{paths[name]}</svg>;
}

function localToday() {
  const now = new Date();
  return new Date(now.getTime() - now.getTimezoneOffset() * 60_000).toISOString().slice(0, 10);
}

function dateAt(date: string) {
  return new Date(`${date}T00:00:00`);
}

function addDays(date: string, days: number) {
  const value = dateAt(date);
  value.setDate(value.getDate() + days);
  return value.toISOString().slice(0, 10);
}

function formatMinutes(minutes: number) {
  if (!minutes) return "0h";
  const hours = minutes / 60;
  return `${hours % 1 === 0 ? hours.toFixed(0) : hours.toFixed(1)}h`;
}

function taskRisk(tasks: DailyTask[]) {
  return tasks.filter((task) => task.priority === "high" && task.status !== "completed").length;
}

export default function WeeklyPlanPage() {
  const appSettings = useAppSettings();
  const [goals, setGoals] = useState<WeeklyGoal[]>([]);
  const [week, setWeek] = useState<WeekDashboard | null>(null);
  const [days, setDays] = useState<TodayDashboard[]>([]);
  const [activeTab, setActiveTab] = useState<"weekly" | "phase">("weekly");
  const [showGoalForm, setShowGoalForm] = useState(false);
  const [showTaskForm, setShowTaskForm] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const [goalTitle, setGoalTitle] = useState("");
  const [goalDescription, setGoalDescription] = useState("");
  const [goalPriority, setGoalPriority] = useState<Priority>("high");
  const [goalMinutes, setGoalMinutes] = useState("300");
  const [taskTitle, setTaskTitle] = useState("");
  const [taskDate, setTaskDate] = useState(localToday());
  const [taskMinutes, setTaskMinutes] = useState("30");
  const [taskPriority, setTaskPriority] = useState<Priority>("medium");

  async function loadPlan() {
    setError("");
    try {
      const [goalData, weekData] = await Promise.all([
        api.getCurrentGoals(),
        api.getWeekDashboard(),
      ]);
      const dailyData = await Promise.all(
        Array.from({ length: 7 }, (_, index) => api.getDayDashboard(addDays(weekData.week_start, index))),
      );
      setGoals(goalData);
      setWeek(weekData);
      setDays(dailyData);
      setTaskDate((current) => current || weekData.week_start);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Failed to load weekly plan");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadPlan();
  }, []);

  const weekLabel = useMemo(() => {
    if (!week) return "This week";
    const start = dateAt(week.week_start);
    const end = dateAt(week.week_end);
    return `${start.toLocaleDateString("en", { month: "short", day: "numeric" })} – ${end.toLocaleDateString("en", { month: "short", day: "numeric", year: "numeric" })}`;
  }, [week]);

  const completion = Math.round((week?.completion_rate ?? 0) * 100);
  const targetMinutes = goals.reduce((sum, goal) => sum + (goal.target_minutes ?? 0), 0);
  const totalAtRisk = days.reduce((sum, day) => sum + taskRisk(day.unfinished_tasks), 0);
  const topTasks = days.flatMap((day) => day.unfinished_tasks).sort((a, b) => {
    const rank = { high: 3, medium: 2, low: 1 };
    return rank[b.priority] - rank[a.priority];
  }).slice(0, 3);
  const chartMax = Math.max(60, ...(week?.daily_focus.map((point) => point.focus_minutes) ?? [60]));
  const displayedDays = orderByWeekStart(days, (day) => day.date, appSettings.weekStart);
  const displayedFocus = orderByWeekStart(week?.daily_focus ?? [], (point) => point.date, appSettings.weekStart);
  const todayData = days.find((day) => day.date === localToday());

  async function generatePlan() {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await api.generatePlan({ available_minutes: workloadMinutes(appSettings.workload), task_date: localToday() });
      setMessage("Today’s AI plan was regenerated from your active weekly goals.");
      await loadPlan();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Failed to generate plan");
    } finally {
      setBusy(false);
    }
  }

  async function createGoal(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!week) return;
    setBusy(true);
    try {
      await api.createGoal({
        title: goalTitle,
        description: goalDescription || null,
        week_start: week.week_start,
        week_end: week.week_end,
        priority: goalPriority,
        target_minutes: goalMinutes ? Number(goalMinutes) : null,
      });
      setGoalTitle("");
      setGoalDescription("");
      setShowGoalForm(false);
      await loadPlan();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Failed to create weekly goal");
    } finally {
      setBusy(false);
    }
  }

  async function completeGoal(goal: WeeklyGoal) {
    setBusy(true);
    try {
      await api.updateGoal(goal.id, { status: "completed" });
      await loadPlan();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Failed to update goal");
    } finally {
      setBusy(false);
    }
  }

  async function createTask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    try {
      await api.createTask({
        title: taskTitle,
        task_date: taskDate,
        estimated_minutes: taskMinutes ? Number(taskMinutes) : null,
        priority: taskPriority,
        source: "manual",
      });
      setTaskTitle("");
      setShowTaskForm(false);
      await loadPlan();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Failed to create task");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="plans-page">
      <header className="plans-header">
        <div><h1>Plans</h1><p>Plan your weeks and phases. Stay aligned with your bigger goals.</p></div>
        <div className="plans-header-actions">
          <Link aria-label="Open calendar" href="/today"><PlanIcon name="calendar" size={20} /></Link>
          <Link className="plans-coach-button" href="/check-in"><PlanIcon name="spark" /> Ask my coach <span>⌄</span></Link>
        </div>
      </header>

      <div className="plans-tabs" role="tablist">
        <button className={activeTab === "weekly" ? "active" : ""} onClick={() => setActiveTab("weekly")} role="tab" type="button">Weekly Plan</button>
        <button className={activeTab === "phase" ? "active" : ""} onClick={() => setActiveTab("phase")} role="tab" type="button">Phase Plan</button>
      </div>

      {error ? <div className="error plans-feedback">{error}</div> : null}
      {message ? <div className="success plans-feedback">{message}</div> : null}

      {activeTab === "phase" ? (
        <div className="phase-plan-view">
          <div><p className="eyebrow">Phase plan</p><h2>Build the next phase from weekly outcomes</h2><p>Use your active goals as the foundation for a longer planning cycle.</p></div>
          <button className="outline-purple" onClick={() => setShowGoalForm(true)} type="button">+ Add phase goal</button>
        </div>
      ) : (
        <div className="plans-layout">
          <main className="weekly-plan-main">
            <section className="plan-card glance-card">
              <div className="glance-heading"><h2>This Week at a Glance</h2><span>{weekLabel}</span></div>
              <div className="glance-content">
                <div className="glance-stats">
                  <div><span>Weekly Goal</span><strong>{targetMinutes ? formatMinutes(targetMinutes) : "—"}</strong><small>Focus time</small></div>
                  <div><span>Progress</span><strong>{completion}%</strong><small className="positive">↑ {week?.completed_tasks ?? 0} completed</small></div>
                  <div><span>Completed Tasks</span><strong>{week?.completed_tasks ?? 0} / {week?.planned_tasks ?? 0}</strong></div>
                  <div><span>At-Risk Tasks</span><strong className="danger-number">{totalAtRisk}</strong></div>
                </div>
                <div className="weekly-mini-chart">
                  <div className="mini-chart-key"><span><i /> Focus Time</span><span className="goal-key">Goal: {targetMinutes ? formatMinutes(targetMinutes) : "—"}</span></div>
                  <div className="mini-chart-body">
                    <div className="mini-axis"><span>10h</span><span>5h</span><span>0h</span></div>
                    <div className="mini-bars">
                      {displayedFocus.map((point) => <div key={point.date}><span style={{ height: `${Math.max(3, point.focus_minutes / chartMax * 100)}%` }} /><small>{dateAt(point.date).toLocaleDateString("en", { weekday: "short" })}</small></div>)}
                    </div>
                  </div>
                </div>
              </div>
            </section>

            <section className="plan-card week-table-card">
              <div className="plan-toolbar">
                <div><button className="outline-purple" disabled={busy} onClick={generatePlan} type="button"><PlanIcon name="spark" /> {busy ? "Working…" : "Regenerate Plan with AI"}</button><span>Uses today’s capacity and weekly goals</span></div>
                <Link className="outline-neutral" href="/today"><PlanIcon name="refresh" /> Adjust Unfinished Tasks</Link>
              </div>

              <div className="week-table">
                <div className="week-table-header"><span>Day</span><span>Focus Goal</span><span>Key Tasks</span><span>Progress</span><span /></div>
                {loading ? <p className="plan-loading">Loading your week…</p> : null}
                {displayedDays.map((day) => {
                  const point = week?.daily_focus.find((item) => item.date === day.date);
                  const progress = Math.round(day.completion_rate * 100);
                  const risks = taskRisk(day.unfinished_tasks);
                  const date = dateAt(day.date);
                  return <div className={`week-day-row ${day.date === localToday() ? "today" : ""}`} key={day.date}>
                    <time><b>{date.toLocaleDateString("en", { weekday: "short" })}</b><span>{date.toLocaleDateString("en", { month: "short", day: "numeric" })}</span></time>
                    <div className="day-focus"><strong>{formatMinutes(point?.focus_minutes ?? day.focus_minutes)}</strong><span>of {formatMinutes(point?.planned_minutes ?? 0)}</span></div>
                    <div className="day-tasks">
                      {day.unfinished_tasks.slice(0, 2).map((task) => <span key={task.id}>• {task.title}</span>)}
                      {!day.unfinished_tasks.length ? <span className="empty-task">No scheduled tasks</span> : null}
                    </div>
                    <div className="day-progress"><div><i className={progress >= 75 ? "green" : progress >= 40 ? "amber" : "gray"} style={{ width: `${progress}%` }} /></div><span>{progress}%</span>{risks ? <b>{risks} at risk</b> : null}</div>
                    <span className="row-chevron">⌄</span>
                  </div>;
                })}
              </div>

              {showTaskForm ? (
                <form className="inline-plan-form" onSubmit={createTask}>
                  <input className="input" placeholder="Task title" required value={taskTitle} onChange={(event) => setTaskTitle(event.target.value)} />
                  <input className="input" type="date" min={week?.week_start} max={week?.week_end} value={taskDate} onChange={(event) => setTaskDate(event.target.value)} />
                  <input className="input" min="0" type="number" value={taskMinutes} onChange={(event) => setTaskMinutes(event.target.value)} />
                  <select className="input" value={taskPriority} onChange={(event) => setTaskPriority(event.target.value as Priority)}><option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option></select>
                  <button className="outline-purple" disabled={busy} type="submit">Add task</button>
                  <button className="form-cancel" onClick={() => setShowTaskForm(false)} type="button">Cancel</button>
                </form>
              ) : <button className="add-week-task" onClick={() => setShowTaskForm(true)} type="button">＋ Add Task to Week</button>}
            </section>
          </main>

          <aside className="plan-side-column">
            <section className="plan-card summary-card"><h3>Weekly Summary</h3><div className="summary-list">
              <div><i className="purple"><PlanIcon name="clock" /></i><span>Total Focus Time</span><strong>{formatMinutes(week?.focus_minutes ?? 0)} <small>/ {targetMinutes ? formatMinutes(targetMinutes) : "—"}</small></strong></div>
              <div><i className="blue"><PlanIcon name="check" /></i><span>Completion Rate</span><strong>{completion}%</strong></div>
              <div><i className="green"><PlanIcon name="check" /></i><span>Tasks Completed</span><strong>{week?.completed_tasks ?? 0} / {week?.planned_tasks ?? 0}</strong></div>
              <div><i className="red"><PlanIcon name="alert" /></i><span>At-Risk Tasks</span><strong>{totalAtRisk}</strong></div>
              <div><i className="orange"><PlanIcon name="alert" /></i><span>Overdue Tasks</span><strong>0</strong></div>
            </div></section>

            <section className="plan-card priorities-card"><h3>Top Priorities This Week</h3><div className="priority-list">
              {(topTasks.length ? topTasks.map((task) => task.title) : goals.map((goal) => goal.title)).slice(0, 3).map((title, index) => <div key={`${title}-${index}`}><b>{index + 1}</b><span>{title}</span></div>)}
              {!topTasks.length && !goals.length ? <p>No priorities yet.</p> : null}
            </div><button className="outline-purple" onClick={() => setShowGoalForm((show) => !show)} type="button">Manage Priorities</button></section>

            {showGoalForm ? <section className="plan-card goal-form-card"><h3>Create Weekly Goal</h3><form className="compact-goal-form" onSubmit={createGoal}>
              <input className="input" placeholder="Goal title" required value={goalTitle} onChange={(event) => setGoalTitle(event.target.value)} />
              <textarea className="input" placeholder="Description" rows={2} value={goalDescription} onChange={(event) => setGoalDescription(event.target.value)} />
              <div><input className="input" min="0" type="number" value={goalMinutes} onChange={(event) => setGoalMinutes(event.target.value)} /><select className="input" value={goalPriority} onChange={(event) => setGoalPriority(event.target.value as Priority)}><option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option></select></div>
              <button className="outline-purple" disabled={busy} type="submit">Create goal</button>
            </form>
            {goals.map((goal) => <div className="goal-manage-row" key={goal.id}><span>{goal.title}</span><button disabled={busy} onClick={() => completeGoal(goal)} type="button">Complete</button></div>)}</section> : null}

            <section className="plan-card insight-card"><h3><PlanIcon name="spark" /> AI Coach Insight</h3><p>{todayData?.coaching?.summary ?? (totalAtRisk ? `You have ${totalAtRisk} at-risk tasks this week. Protect focused time for the highest-priority work.` : "Your week is balanced. Keep protecting focused time for your top priorities.")}</p><Link className="outline-purple" href="/check-in">View Recommendations <PlanIcon name="arrow" /></Link></section>

            <section className="plan-card next-week-card"><div><h3>Next Week</h3><span>Draft is ready</span></div><p>Build next week from this week’s progress and your active goals.</p><Link className="outline-purple" href="/review">Preview Next Week <PlanIcon name="arrow" /></Link></section>
          </aside>
        </div>
      )}
    </section>
  );
}
