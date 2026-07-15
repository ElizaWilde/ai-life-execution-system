"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  api,
  DailyReview,
  DailyTask,
  TodayDashboard,
  WeekDashboard,
  WeeklyReview,
} from "../../lib/api";
import { orderByWeekStart, useAppSettings } from "../../lib/settings";

type ReviewIconName = "spark" | "check" | "clock" | "mood" | "alert" | "pattern" | "energy" | "calendar" | "refresh";

function ReviewIcon({ name, size = 18 }: { name: ReviewIconName; size?: number }) {
  const paths: Record<ReviewIconName, React.ReactNode> = {
    spark: <path d="m12 2 1.6 5.1a5 5 0 0 0 3.3 3.3L22 12l-5.1 1.6a5 5 0 0 0-3.3 3.3L12 22l-1.6-5.1a5 5 0 0 0-3.3-3.3L2 12l5.1-1.6a5 5 0 0 0 3.3-3.3L12 2Z" />,
    check: <><circle cx="12" cy="12" r="9" /><path d="m8 12 2.5 2.5L16 9" /></>,
    clock: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
    mood: <><circle cx="12" cy="12" r="9" /><path d="M8.5 10h.01M15.5 10h.01M8 14s1.5 2 4 2 4-2 4-2" /></>,
    alert: <><path d="M10.3 3.8 2.7 17a2 2 0 0 0 1.7 3h15.2a2 2 0 0 0 1.7-3L13.7 3.8a2 2 0 0 0-3.4 0Z" /><path d="M12 9v4M12 17h.01" /></>,
    pattern: <><path d="M4 18V8M10 18V4M16 18v-6M22 18V7" /><path d="m3 11 7-5 6 4 6-5" /></>,
    energy: <path d="m13 2-8 12h7l-1 8 8-12h-7l1-8Z" />,
    calendar: <><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M16 3v4M8 3v4M3 10h18" /></>,
    refresh: <><path d="M20 7v5h-5" /><path d="M19 12a7 7 0 1 1-2-5" /></>,
  };
  return <svg aria-hidden="true" className="review-icon" fill="none" height={size} viewBox="0 0 24 24" width={size}>{paths[name]}</svg>;
}

function localToday() {
  const now = new Date();
  return new Date(now.getTime() - now.getTimezoneOffset() * 60_000).toISOString().slice(0, 10);
}

function dateAt(value: string) {
  return new Date(`${value}T00:00:00`);
}

function formatMinutes(minutes: number) {
  if (!minutes) return "0h";
  const hours = minutes / 60;
  return `${hours % 1 === 0 ? hours.toFixed(0) : hours.toFixed(1)}h`;
}

function titleCase(value?: string | null) {
  if (!value) return "Not set";
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export default function ReviewPage() {
  const appSettings = useAppSettings();
  const [reviewDate, setReviewDate] = useState(localToday());
  const [activeTab, setActiveTab] = useState<"daily" | "weekly">("daily");
  const [review, setReview] = useState<DailyReview | null>(null);
  const [weeklyReview, setWeeklyReview] = useState<WeeklyReview | null>(null);
  const [tasks, setTasks] = useState<DailyTask[]>([]);
  const [today, setToday] = useState<TodayDashboard | null>(null);
  const [week, setWeek] = useState<WeekDashboard | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  async function load() {
    setError("");
    try {
      const [taskData, todayData, weekData] = await Promise.all([
        api.getTodayTasks(),
        api.getTodayDashboard(),
        api.getWeekDashboard(),
      ]);
      setTasks(taskData);
      setToday(todayData);
      setWeek(weekData);
      try { setReview(await api.getReview(reviewDate)); } catch { setReview(null); }
      try { setWeeklyReview(await api.getWeeklyReview(weekData.week_start)); } catch { setWeeklyReview(null); }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Failed to load review data");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [reviewDate]);

  const completed = tasks.filter((task) => task.status === "completed");
  const unfinished = tasks.filter((task) => task.status !== "completed" && task.status !== "cancelled");
  const completion = Math.round((today?.completion_rate ?? 0) * 100);
  const weekCompletion = Math.round((week?.completion_rate ?? 0) * 100);
  const atRisk = unfinished.filter((task) => task.priority === "high").length;
  const bestDay = useMemo(() => {
    const points = week?.daily_focus ?? [];
    return points.reduce<(typeof points)[number] | null>((best, point) => !best || point.focus_minutes > best.focus_minutes ? point : best, null);
  }, [week]);
  const chartMax = Math.max(60, ...(week?.daily_focus.map((point) => point.focus_minutes) ?? [60]));
  const displayedFocus = orderByWeekStart(week?.daily_focus ?? [], (point) => point.date, appSettings.weekStart);
  const date = dateAt(reviewDate);
  const weekLabel = week ? `${dateAt(week.week_start).toLocaleDateString("en", { month: "short", day: "numeric" })} – ${dateAt(week.week_end).toLocaleDateString("en", { month: "short", day: "numeric", year: "numeric" })}` : "This week";

  async function generateDailyReview() {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      setReview(await api.generateReview({ review_date: reviewDate }));
      setMessage("Daily review generated and saved.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Failed to generate daily review");
    } finally {
      setBusy(false);
    }
  }

  async function generateWeeklyReview() {
    if (!week) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      setWeeklyReview(await api.generateWeeklyReview({ week_start: week.week_start }));
      setMessage("Weekly review generated and saved.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Failed to generate weekly review");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="review-workspace">
      <header className="review-workspace-header">
        <div><h1>Review</h1><p>Reflect on today and this week.</p></div>
        <div className="review-greeting"><ReviewIcon name="spark" size={32} /><div><strong>Review your progress and improve tomorrow.</strong><span>Small reflections create big improvements.</span></div></div>
        <Link className="review-coach-button" href="/check-in"><ReviewIcon name="spark" /> Ask my coach <span>⌄</span></Link>
      </header>

      <div className="review-tabs"><button className={activeTab === "daily" ? "active" : ""} onClick={() => setActiveTab("daily")} type="button">Daily Review</button><button className={activeTab === "weekly" ? "active" : ""} onClick={() => setActiveTab("weekly")} type="button">Weekly Review</button></div>
      {error ? <div className="error review-feedback">{error}</div> : null}
      {message ? <div className="success review-feedback">{message}</div> : null}

      <div className="review-layout">
        <main className="review-main-column">
          {activeTab === "daily" ? <section className="review-card daily-review-card">
            <div className="daily-review-heading"><h2>Daily Review</h2><label><span>{date.toLocaleDateString("en", { weekday: "short", month: "short", day: "numeric", year: "numeric" })}</span><input aria-label="Review date" type="date" value={reviewDate} onChange={(event) => setReviewDate(event.target.value)} /></label></div>
            <div className="daily-review-metrics">
              <div><i className="green"><ReviewIcon name="check" /></i><strong>{today?.completed_tasks ?? completed.length} / {today?.planned_tasks ?? tasks.length}</strong><span>Completed</span></div>
              <div><i className="blue"><ReviewIcon name="clock" /></i><strong>{formatMinutes(today?.focus_minutes ?? review?.focus_minutes ?? 0)}</strong><span>Focus Time</span></div>
              <div><i className="ring"><b>{completion}%</b></i><strong>{completion}%</strong><span>Completion</span></div>
              <div><i className="green"><ReviewIcon name="mood" /></i><strong>{titleCase(today?.check_in?.mood_level)}</strong><span>Mood</span></div>
            </div>

            <div className="review-highlights">
              <article><h3><ReviewIcon name="spark" /> What went well</h3>{completed.length ? <ul>{completed.slice(0, 3).map((task) => <li key={task.id}>{task.title} was completed.</li>)}</ul> : <p>No completed tasks recorded yet.</p>}</article>
              <article><h3><ReviewIcon name="alert" /> What slipped</h3>{unfinished.length ? <ul>{unfinished.slice(0, 3).map((task) => <li key={task.id}>{task.title}<span className={task.priority === "high" ? "risk" : "planned"}>{task.priority === "high" ? "At Risk" : titleCase(task.status)}</span></li>)}</ul> : <p>Nothing slipped today.</p>}</article>
            </div>

            <div className="review-task-results"><h3>Task Results</h3><div className="review-task-header"><span>Task</span><span>Planned</span><span>Focus Time</span><span>Status</span><span /></div>{loading ? <p className="review-empty">Loading results…</p> : null}{tasks.map((task) => <div className="review-task-row" key={task.id}><span className={`result-check ${task.status === "completed" ? "done" : task.priority === "high" ? "risk" : ""}`}>{task.status === "completed" ? "✓" : ""}</span><div><strong>{task.title}</strong><b>{task.source}</b></div><span>{task.estimated_minutes ? formatMinutes(task.estimated_minutes) : "Flexible"}</span><span>{task.status === "completed" ? formatMinutes(task.estimated_minutes ?? 0) : "—"}</span><span className={`result-status ${task.status} ${task.priority === "high" && task.status !== "completed" ? "risk" : ""}`}>{task.status === "completed" ? "Completed" : task.priority === "high" ? "At Risk" : titleCase(task.status)}</span><b className="result-menu">•••</b></div>)}</div>

            <div className="tomorrow-suggestion"><ReviewIcon name="spark" size={30} /><div><h3>Tomorrow Suggestion</h3><p>{review?.tomorrow_adjustment ?? "Prioritize at-risk work early and protect one focused deep-work block."}</p><div><span>Prioritize at-risk tasks</span><span>Morning deep work</span><span>Limit meetings</span></div></div><button disabled={busy} onClick={generateDailyReview} type="button"><ReviewIcon name="refresh" /> {review ? "Regenerate Suggestion" : "Generate Review"}</button></div>
          </section> : <section className="review-card weekly-detail-card">
            <div className="daily-review-heading"><h2>Weekly Review</h2><span>{weekLabel}</span></div>
            {weeklyReview ? <><p className="weekly-review-summary">{weeklyReview.summary}</p><div className="weekly-review-lists"><article><h3>Achievements</h3><ul>{weeklyReview.achievements_json.map((item) => <li key={item}>{item}</li>)}</ul></article><article><h3>Obstacles</h3><ul>{weeklyReview.obstacles_json.map((item) => <li key={item}>{item}</li>)}</ul></article><article><h3>Next-week actions</h3><ul>{weeklyReview.next_week_actions_json.map((item) => <li key={item}>{item}</li>)}</ul></article></div></> : <div className="weekly-empty"><p>No weekly review saved yet.</p><button disabled={busy} onClick={generateWeeklyReview} type="button">Generate Weekly Review</button></div>}
          </section>}
        </main>

        <aside className="review-side-column">
          <section className="review-card weekly-snapshot"><div className="review-side-heading"><h2>Weekly Snapshot</h2><span>{weekLabel}</span></div><div className="snapshot-grid"><div><i className="blue"><ReviewIcon name="clock" /></i><strong>{formatMinutes(week?.focus_minutes ?? 0)}</strong><span>Total Focus Time</span><b>{weekCompletion}% of goal</b></div><div><i className="green"><ReviewIcon name="check" /></i><strong>{weekCompletion}%</strong><span>Goal Progress</span><b>↑ {week?.completed_tasks ?? 0} completed</b></div><div><i className="green"><ReviewIcon name="check" /></i><strong>{week?.completed_tasks ?? 0} / {week?.planned_tasks ?? 0}</strong><span>Completed Tasks</span><b>{weekCompletion}%</b></div><div><i className="red"><ReviewIcon name="alert" /></i><strong>{atRisk}</strong><span>At-Risk Tasks</span><b>{atRisk ? "Needs attention" : "On track"}</b></div></div></section>

          <section className="review-card ai-review-summary"><h2><ReviewIcon name="spark" /> AI Review Summary</h2><p>{review?.summary ?? weeklyReview?.summary ?? "Generate a daily review to get a grounded AI summary of your progress."}</p><div><span><ReviewIcon name="check" /> {completed.length ? `You completed ${completed.length} task${completed.length === 1 ? "" : "s"} today.` : "No completed tasks yet."}</span><span><ReviewIcon name="alert" /> {atRisk ? `Protect time for ${atRisk} at-risk task${atRisk === 1 ? "" : "s"}.` : "No high-priority tasks are at risk."}</span></div></section>

          <section className="review-card patterns-card"><h2><ReviewIcon name="pattern" /> Patterns</h2><div><span><i className="green">☀</i><b>Best focus</b><em>{bestDay ? dateAt(bestDay.date).toLocaleDateString("en", { weekday: "long" }) : "Not enough data"}</em></span><span><i className="orange"><ReviewIcon name="energy" size={14} /></i><b>Energy</b><em>{titleCase(today?.check_in?.energy_level)}</em></span><span><i className="red">◎</i><b>Delay pattern</b><em>{atRisk ? "High-priority work needs attention" : "No current delay pattern"}</em></span></div></section>

          <section className="review-card review-actions"><h2><ReviewIcon name="energy" /> Actions</h2><div><button disabled={busy} onClick={generateWeeklyReview} type="button"><ReviewIcon name="spark" /> Generate Weekly Review</button><Link href="/weekly-plan"><ReviewIcon name="calendar" /> Plan Tomorrow</Link></div></section>

          <section className="review-card weekly-focus-chart"><div className="review-side-heading"><h2>This Week: Focus Hours</h2><span><i /> Focus Time (h)</span></div><div className="review-chart"><div className="review-chart-axis"><span>15h</span><span>10h</span><span>5h</span><span>0h</span></div><div className="review-chart-bars">{displayedFocus.map((point) => <div key={point.date}><span style={{ height: `${Math.max(3, point.focus_minutes / chartMax * 100)}%` }} /><small>{dateAt(point.date).toLocaleDateString("en", { weekday: "short" })}</small></div>)}</div></div></section>
        </aside>
      </div>
    </section>
  );
}
