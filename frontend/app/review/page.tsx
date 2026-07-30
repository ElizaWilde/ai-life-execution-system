"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { api, TodayDashboard, WeekDashboard, WeeklyReview, WorkingDay } from "../../lib/api";

function ReviewIcon({ name, size = 18 }: { name: "spark" | "check" | "clock" | "alert" | "calendar"; size?: number }) {
  const paths = {
    spark: <path d="m12 2 1.6 5.1a5 5 0 0 0 3.3 3.3L22 12l-5.1 1.6a5 5 0 0 0-3.3 3.3L12 22l-1.6-5.1a5 5 0 0 0-3.3-3.3L2 12l5.1-1.6a5 5 0 0 0 3.3-3.3L12 2Z" />,
    check: <><circle cx="12" cy="12" r="9" /><path d="m8 12 2.5 2.5L16 9" /></>,
    clock: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
    alert: <><path d="M10.3 3.8 2.7 17a2 2 0 0 0 1.7 3h15.2a2 2 0 0 0 1.7-3L13.7 3.8a2 2 0 0 0-3.4 0Z" /><path d="M12 9v4M12 17h.01" /></>,
    calendar: <><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M16 3v4M8 3v4M3 10h18" /></>,
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

function toLocalDate(date: Date) {
  return new Date(date.getTime() - date.getTimezoneOffset() * 60_000).toISOString().slice(0, 10);
}

function addDays(value: string, days: number) {
  const date = dateAt(value);
  date.setDate(date.getDate() + days);
  return toLocalDate(date);
}

function startOfWeek(value: string) {
  const date = dateAt(value);
  const day = date.getDay();
  date.setDate(date.getDate() - (day === 0 ? 6 : day - 1));
  return toLocalDate(date);
}

function weeksForMonth(month: string) {
  const [year, monthNumber] = month.split("-").map(Number);
  const first = new Date(year, monthNumber - 1, 1);
  const last = new Date(year, monthNumber, 0);
  const starts: string[] = [];
  let cursor = startOfWeek(toLocalDate(first));
  while (dateAt(cursor) <= last) {
    starts.push(cursor);
    cursor = addDays(cursor, 7);
  }
  return starts;
}

function formatMinutes(minutes: number) {
  if (minutes < 60) return `${minutes}m`;
  const hours = minutes / 60;
  return `${hours % 1 === 0 ? hours.toFixed(0) : hours.toFixed(1)}h`;
}

const REVIEW_CHART_COLORS = ["#a98f86", "#6d42e8", "#45b978", "#e4a13b", "#4d8ee7", "#df6d86", "#28a6a0"];
const WORKING_DAY_OFFSET: Record<WorkingDay, number> = {
  monday: 0,
  tuesday: 1,
  wednesday: 2,
  thursday: 3,
  friday: 4,
  saturday: 5,
  sunday: 6,
};

export default function ReviewPage() {
  const today = localToday();
  const [week, setWeek] = useState<WeekDashboard | null>(null);
  const [weekDays, setWeekDays] = useState<TodayDashboard[]>([]);
  const [weeklyReview, setWeeklyReview] = useState<WeeklyReview | null>(null);
  const [selectedMonth, setSelectedMonth] = useState(today.slice(0, 7));
  const [monthWeeks, setMonthWeeks] = useState<WeekDashboard[]>([]);
  const [activeReviewTab, setActiveReviewTab] = useState<"weekly" | "monthly">("weekly");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    let active = true;
    async function load() {
      setLoading(true);
      setError("");
      try {
        const [currentWeek, automationPreferences] = await Promise.all([
          api.getWeekDashboard(),
          api.getAutomationPreferences(),
        ]);
        if (!active) return;
        setWeek(currentWeek);
        const workingDayOffsets = automationPreferences.working_days
          .map((day) => WORKING_DAY_OFFSET[day])
          .sort((left, right) => left - right);
        const dailyDashboards = await Promise.all(
          workingDayOffsets.map((offset) => api.getDayDashboard(addDays(currentWeek.week_start, offset))),
        );
        if (active) setWeekDays(dailyDashboards);
        try {
          const saved = await api.getWeeklyReview(currentWeek.week_start);
          if (active) setWeeklyReview(saved);
        } catch {
          if (active) setWeeklyReview(null);
        }
        const monthly = await Promise.all(weeksForMonth(selectedMonth).map((weekStart) => api.getWeekDashboard(weekStart)));
        if (active) setMonthWeeks(monthly);
      } catch (reason) {
        if (active) setError(reason instanceof Error ? reason.message : "Failed to load review data");
      } finally {
        if (active) setLoading(false);
      }
    }
    void load();
    return () => {
      active = false;
    };
  }, [selectedMonth]);

  const monthly = useMemo(() => {
    const focusMinutes = monthWeeks.reduce((total, item) => total + item.focus_minutes, 0);
    const plannedTasks = monthWeeks.reduce((total, item) => total + item.planned_tasks, 0);
    const completedTasks = monthWeeks.reduce((total, item) => total + item.completed_tasks, 0);
    const completionRate = plannedTasks ? Math.round(completedTasks / plannedTasks * 100) : 0;
    const bestWeek = monthWeeks.reduce<WeekDashboard | null>(
      (best, item) => !best || item.focus_minutes > best.focus_minutes ? item : best,
      null,
    );
    return { focusMinutes, plannedTasks, completedTasks, completionRate, bestWeek };
  }, [monthWeeks]);

  const weekLabel = week
    ? `${dateAt(week.week_start).toLocaleDateString("en", { month: "short", day: "numeric" })} – ${dateAt(week.week_end).toLocaleDateString("en", { month: "short", day: "numeric", year: "numeric" })}`
    : "This week";
  const monthLabel = dateAt(`${selectedMonth}-01`).toLocaleDateString("en", { month: "long", year: "numeric" });
  const weeklyFocusPeak = Math.max(
    6 * 60,
    ...weekDays.map((day) => day.focus_minutes),
  );
  const weeklyAllocation = (week?.time_allocation ?? []).filter((item) => item.focus_minutes > 0);
  const weeklyAllocationTotal = weeklyAllocation.reduce((total, item) => total + item.focus_minutes, 0);
  const donutRadius = 42;
  const donutCircumference = 2 * Math.PI * donutRadius;
  let donutOffset = 0;
  const donutSegments = weeklyAllocation.map((item, index) => {
    const length = weeklyAllocationTotal
      ? item.focus_minutes / weeklyAllocationTotal * donutCircumference
      : 0;
    const segment = {
      ...item,
      color: REVIEW_CHART_COLORS[index % REVIEW_CHART_COLORS.length],
      length,
      offset: donutOffset,
    };
    donutOffset += length;
    return segment;
  });
  const [hoveredDonutIndex, setHoveredDonutIndex] = useState<number | null>(null);

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
        <div><h1>Review</h1><p>Understand longer-term progress and improve the next cycle.</p></div>
        <div className="review-greeting"><ReviewIcon name="spark" size={32} /><div><strong>Turn your history into better plans.</strong><span>Weekly reflection and monthly patterns now live together.</span></div></div>
        <Link className="review-coach-button" href="/check-in"><ReviewIcon name="spark" /> Ask my coach <span>⌄</span></Link>
      </header>

      {error ? <div className="error review-feedback">{error}</div> : null}
      {message ? <div className="success review-feedback">{message}</div> : null}

      <nav aria-label="Review periods" className="workspace-section-tabs review-period-tabs">
        <button className={activeReviewTab === "weekly" ? "active" : ""} onClick={() => setActiveReviewTab("weekly")} type="button">Weekly Review</button>
        <button className={activeReviewTab === "monthly" ? "active" : ""} onClick={() => setActiveReviewTab("monthly")} type="button">Monthly Review</button>
      </nav>

      <div className={`review-period-grid show-${activeReviewTab}`}>
        <section className="review-card weekly-detail-card period-review-card">
          <div className="daily-review-heading">
            <div><h2>Weekly Review</h2><span>{weekLabel}</span></div>
            <button disabled={busy || loading} onClick={generateWeeklyReview} type="button">
              <ReviewIcon name="spark" size={15} /> {weeklyReview ? "Regenerate" : "Generate review"}
            </button>
          </div>
          <div className="weekly-review-board">
            <aside className="weekly-review-analytics">
              <div className="weekly-review-intro">
                <h3>What got done</h3>
                <p>You logged <strong>{formatMinutes(week?.focus_minutes ?? 0)}</strong> this week in total.</p>
              </div>

              <section className="weekly-productivity-chart">
                <h3>Daily productivity</h3>
                <div className="weekly-chart-canvas">
                  <span className="weekly-chart-ceiling">{formatMinutes(weeklyFocusPeak)}</span>
                  <div className="weekly-chart-bars">
                    {weekDays.map((day) => {
                      const completed = day.tasks.filter((task) => task.status === "completed").length;
                      const planned = day.tasks.filter((task) => task.status !== "cancelled").reduce((total, task) => total + (task.estimated_minutes ?? 0), 0);
                      return <div className="weekly-productivity-day" key={day.date}>
                        <div aria-label={`${dateAt(day.date).toLocaleDateString("en", { weekday: "long" })}: ${formatMinutes(day.focus_minutes)} focused`} className="weekly-productivity-bar" style={{ height: `${Math.max(day.focus_minutes / weeklyFocusPeak * 100, day.focus_minutes ? 4 : 0)}%` }} tabIndex={0}>
                          <span className="weekly-bar-tooltip"><b>{dateAt(day.date).toLocaleDateString("en", { weekday: "short" })}</b><em>{formatMinutes(day.focus_minutes)} focused</em><small>{formatMinutes(planned)} planned · {completed}/{day.tasks.length} done</small></span>
                        </div>
                        <small>{dateAt(day.date).toLocaleDateString("en", { weekday: "short" })}</small>
                      </div>;
                    })}
                  </div>
                </div>
              </section>

              <section className="weekly-time-chart">
                <h3>How you spent your time</h3>
                <div className="weekly-review-donut">
                  <svg aria-label="Weekly focused time distribution" role="img" viewBox="0 0 120 120">
                    <circle className="weekly-donut-track" cx="60" cy="60" r={donutRadius} />
                    {donutSegments.map((segment, index) => <circle aria-label={`${segment.label}: ${formatMinutes(segment.focus_minutes)}`} className="weekly-donut-segment" cx="60" cy="60" key={segment.label} onBlur={() => setHoveredDonutIndex(null)} onClick={() => setHoveredDonutIndex(index)} onFocus={() => setHoveredDonutIndex(index)} onMouseEnter={() => setHoveredDonutIndex(index)} onMouseLeave={() => setHoveredDonutIndex(null)} r={donutRadius} stroke={segment.color} strokeDasharray={`${segment.length} ${donutCircumference - segment.length}`} strokeDashoffset={-segment.offset} tabIndex={0} />)}
                  </svg>
                  <span className="weekly-donut-total"><strong>{formatMinutes(weeklyAllocationTotal)}</strong><small>focused</small></span>
                  {hoveredDonutIndex !== null && donutSegments[hoveredDonutIndex] ? <span className="weekly-donut-tooltip"><i style={{ background: donutSegments[hoveredDonutIndex].color }} /><b>{donutSegments[hoveredDonutIndex].label}</b><em>{formatMinutes(donutSegments[hoveredDonutIndex].focus_minutes)}</em></span> : null}
                </div>
                <ul className="weekly-time-legend">
                  {donutSegments.length ? donutSegments.map((segment, index) => <li key={segment.label} onBlur={() => setHoveredDonutIndex(null)} onClick={() => setHoveredDonutIndex(index)} onFocus={() => setHoveredDonutIndex(index)} onMouseEnter={() => setHoveredDonutIndex(index)} onMouseLeave={() => setHoveredDonutIndex(null)} tabIndex={0}><i style={{ background: segment.color }} /><span>{segment.label}</span></li>) : <li><i /><span>Uncategorized</span></li>}
                </ul>
              </section>
            </aside>

            <div className="weekly-review-days">
              {weekDays.map((day) => {
                const allocationByTitle = new Map(day.time_allocation.map((item) => [item.label, item.focus_minutes]));
                const planned = day.tasks.filter((task) => task.status !== "cancelled").reduce((total, task) => total + (task.estimated_minutes ?? 0), 0);
                return <section className="weekly-review-day" key={day.date}>
                  <header><h3>{dateAt(day.date).toLocaleDateString("en", { weekday: "long" })}</h3><span>{dateAt(day.date).toLocaleDateString("en", { month: "short", day: "numeric" })}</span></header>
                  <div className="weekly-day-total"><ReviewIcon name="clock" size={14} /><span>{formatMinutes(day.focus_minutes)} / {formatMinutes(planned)}</span></div>
                  <div className="weekly-day-tasks">
                    {day.tasks.length ? day.tasks.map((task) => {
                      const focused = allocationByTitle.get(task.title) ?? 0;
                      return <article className={task.status === "completed" ? "completed" : ""} key={task.id}>
                        <div><strong>{task.title}</strong><small>{formatMinutes(focused)} / {formatMinutes(task.estimated_minutes ?? 0)}</small></div>
                        <footer><span className={`weekly-task-state ${task.status}`}>{task.status === "completed" ? "✓ Done" : task.status.replace("_", " ")}</span><b className={task.priority}>{task.priority}</b></footer>
                      </article>;
                    }) : <p>No tasks planned.</p>}
                  </div>
                </section>;
              })}
            </div>
          </div>

          <section className="weekly-agent-review">
            <header><ReviewIcon name="spark" size={18} /><div><h3>AI weekly reflection</h3><p>Generated from your tasks, focus sessions, and check-ins.</p></div></header>
          {weeklyReview ? <>
            <p className="weekly-review-summary">{weeklyReview.summary}</p>
            <div className="weekly-review-lists">
              <article><h3>Achievements</h3><ul>{weeklyReview.achievements_json.map((item) => <li key={item}>{item}</li>)}</ul></article>
              <article><h3>Obstacles</h3><ul>{weeklyReview.obstacles_json.map((item) => <li key={item}>{item}</li>)}</ul></article>
              <article><h3>Next-week actions</h3><ul>{weeklyReview.next_week_actions_json.map((item) => <li key={item}>{item}</li>)}</ul></article>
            </div>
          </> : <div className="weekly-empty"><p>{loading ? "Loading weekly review…" : "No weekly review saved yet."}</p></div>}
          </section>
        </section>

        <section className="review-card monthly-review-card period-review-card">
          <div className="daily-review-heading">
            <div><h2>Monthly Review</h2><span>{monthLabel}</span></div>
            <label className="month-review-picker"><span>Choose month</span><input aria-label="Review month" onChange={(event) => setSelectedMonth(event.target.value)} type="month" value={selectedMonth} /></label>
          </div>
          <div className="daily-review-metrics">
            <div><i className="green"><ReviewIcon name="check" /></i><strong>{monthly.completedTasks} / {monthly.plannedTasks}</strong><span>Completed</span></div>
            <div><i className="blue"><ReviewIcon name="clock" /></i><strong>{formatMinutes(monthly.focusMinutes)}</strong><span>Focus Time</span></div>
            <div><i className="ring"><b>{monthly.completionRate}%</b></i><strong>{monthly.completionRate}%</strong><span>Completion</span></div>
            <div><i className="green"><ReviewIcon name="calendar" /></i><strong>{monthWeeks.length}</strong><span>Weeks Reviewed</span></div>
          </div>
          <div className="monthly-insights">
            <article><ReviewIcon name="spark" /><div><h3>Monthly pattern</h3><p>{monthly.bestWeek ? `Your strongest focus week began ${dateAt(monthly.bestWeek.week_start).toLocaleDateString("en", { month: "short", day: "numeric" })}, with ${formatMinutes(monthly.bestWeek.focus_minutes)} of focused work.` : "Complete focused work to reveal your strongest week."}</p></div></article>
            <article><ReviewIcon name={monthly.completionRate >= 70 ? "check" : "alert"} /><div><h3>Planning insight</h3><p>{monthly.completionRate >= 70 ? "Your completion rate is healthy. Keep next month’s workload close to this level." : "Completion is below 70%. Reduce planned volume or protect more focus time next month."}</p></div></article>
            <article><ReviewIcon name="calendar" /><div><h3>Next-month action</h3><p>{monthly.focusMinutes ? `Use ${formatMinutes(Math.round(monthly.focusMinutes / Math.max(monthWeeks.length, 1)))} as your evidence-based weekly focus baseline.` : "Start with a realistic weekly focus target and review it after the first week."}</p></div></article>
          </div>
        </section>
      </div>
    </section>
  );
}
