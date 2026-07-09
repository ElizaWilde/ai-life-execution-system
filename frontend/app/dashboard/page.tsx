"use client";

import { useEffect, useMemo, useState } from "react";
import {
  api,
  TodayDashboard,
  WeekDashboard,
} from "../../lib/api";

const coral = "#ef684f";
const chartColors = [
  "#7657e8",
  "#5279ef",
  "#c94fe1",
  "#56bfe0",
  "#54dca5",
  "#f54ab5",
  "#f06461",
  "#f4b345",
];

function formatDay(value?: string) {
  if (!value) return { day: "--", weekday: "Today", month: "" };
  const date = new Date(`${value}T00:00:00`);
  return {
    day: String(date.getDate()).padStart(2, "0"),
    weekday: date.toLocaleDateString("en", { weekday: "short" }),
    month: date.toLocaleDateString("en", { month: "long" }),
  };
}

function Icon({ children }: { children: React.ReactNode }) {
  return <span className="dash-icon">{children}</span>;
}

export default function DashboardPage() {
  const [today, setToday] = useState<TodayDashboard | null>(null);
  const [week, setWeek] = useState<WeekDashboard | null>(null);
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [selectedDay, setSelectedDay] = useState<TodayDashboard | null>(null);
  const [chartLoading, setChartLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    async function load() {
      try {
        const [todayData, weekData] = await Promise.all([
          api.getTodayDashboard(),
          api.getWeekDashboard(),
        ]);
        setToday(todayData);
        setWeek(weekData);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load dashboard");
      }
    }
    load();
  }, []);

  const date = formatDay(today?.date);
  const completion = Math.round((today?.completion_rate ?? 0) * 100);
  const weekCompletion = Math.round((week?.completion_rate ?? 0) * 100);
  const circumference = 2 * Math.PI * 48;
  const chartMax = Math.max(
    1,
    ...(week?.daily_focus.map((point) => point.focus_minutes) ?? [1]),
  );
  const weeklyBars = week?.daily_focus.length
    ? week.daily_focus.map((point) => ({
        label: new Date(`${point.date}T00:00:00`).toLocaleDateString("en", {
          weekday: "narrow",
        }),
        minutes: point.focus_minutes,
      }))
    : ["M", "T", "W", "T", "F", "S", "S"].map((label) => ({
        label,
        minutes: 0,
      }));
  const focusHours = ((week?.focus_minutes ?? 0) / 60).toFixed(1);
  const allocation = (
    selectedDate ? selectedDay?.time_allocation : week?.time_allocation
  ) ?? [];
  const allocationTotal = allocation.reduce(
    (sum, point) => sum + (point.planned_minutes || point.focus_minutes),
    0,
  );
  const donutGradient = useMemo(() => {
    if (!allocationTotal) return "#ebe9e4 0deg 360deg";
    let cursor = 0;
    return allocation
      .slice(0, 8)
      .map((point, index) => {
        const value = point.planned_minutes || point.focus_minutes;
        const start = cursor;
        cursor += (value / allocationTotal) * 360;
        return `${chartColors[index % chartColors.length]} ${start}deg ${cursor}deg`;
      })
      .join(", ");
  }, [allocation, allocationTotal]);
  const comparisonBars = selectedDate
    ? allocation.slice(0, 7).map((point) => ({
        label: point.label,
        planned: point.planned_minutes,
        focused: point.focus_minutes,
      }))
    : (week?.daily_focus ?? []).map((point) => ({
        label: new Date(`${point.date}T00:00:00`).toLocaleDateString("en", {
          weekday: "short",
        }),
        planned: point.planned_minutes,
        focused: point.focus_minutes,
      }));
  const comparisonMax = Math.max(
    1,
    ...comparisonBars.flatMap((point) => [point.planned, point.focused]),
  );
  const weekLabel = useMemo(() => {
    if (!week) return "This week";
    const start = new Date(`${week.week_start}T00:00:00`);
    const end = new Date(`${week.week_end}T00:00:00`);
    return `${start.toLocaleDateString("en", { month: "short", day: "numeric" })} – ${end.toLocaleDateString("en", { month: "short", day: "numeric" })}`;
  }, [week]);

  async function selectChartPeriod(dateValue: string | null) {
    setSelectedDate(dateValue);
    if (!dateValue) {
      setSelectedDay(null);
      return;
    }
    setChartLoading(true);
    try {
      setSelectedDay(await api.getDayDashboard(dateValue));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load day statistics");
    } finally {
      setChartLoading(false);
    }
  }

  return (
    <section className="dash-page">
      <header className="dash-topbar">
        <div className="dash-title-lockup">
          <span className="dash-mark">Nº</span>
          <div>
            <strong>Life Execution</strong>
            <span>Personal dashboard</span>
          </div>
        </div>
        <div className="dash-top-actions">
          <span className="dash-period">{weekLabel}</span>
          <span className="dash-avatar">ME</span>
          <div className="dash-profile">
            <strong>MVP User</strong>
            <span>Building momentum</span>
          </div>
        </div>
      </header>

      <div className="dash-hero">
        <div className="dash-date">
          <span className="dash-date-number">{date.day}</span>
          <span>
            <strong>{date.weekday},</strong>
            {date.month}
          </span>
        </div>
        <div className="dash-hero-copy">
          <p>Hey, ready to make today count? <span>✦</span></p>
          <h1>Keep the important things moving.</h1>
        </div>
        <a className="dash-cta" href="/today">
          Show my tasks <span>→</span>
        </a>
      </div>

      {error ? <div className="error">{error}</div> : null}

      <div className="dash-mosaic">
        <article className="dash-card dash-focus-card">
          <div className="dash-card-head">
            <Icon>◷</Icon>
            <span className="dash-chip">Today</span>
          </div>
          <p className="dash-label">Focus time</p>
          <p className="dash-big">{today?.focus_minutes ?? 0}<small> min</small></p>
          <div className="dash-hairline" />
          <p className="dash-note">Every focused minute is a vote for the life you want.</p>
        </article>

        <article className="dash-card dash-completion-card">
          <div>
            <p className="dash-label">Today&apos;s completion</p>
            <p className="dash-big">{today?.completed_tasks ?? 0}<small> / {today?.planned_tasks ?? 0} tasks</small></p>
            <span className="dash-trend">↗ {completion}% complete</span>
          </div>
          <div className="dash-ring" aria-label={`${completion}% complete`}>
            <svg viewBox="0 0 120 120">
              <circle className="dash-ring-track" cx="60" cy="60" r="48" />
              <circle
                className="dash-ring-value"
                cx="60"
                cy="60"
                r="48"
                strokeDasharray={circumference}
                strokeDashoffset={circumference * (1 - completion / 100)}
              />
            </svg>
            <strong>{completion}%</strong>
          </div>
        </article>

        <article className="dash-card dash-week-focus">
          <div className="dash-card-head">
            <div>
              <p className="dash-label">Weekly focus</p>
              <p className="dash-big">{focusHours}<small> hrs</small></p>
            </div>
            <span className="dash-chip">Weekly⌄</span>
          </div>
          <div className="dash-mini-bars">
            {weeklyBars.map((point, index) => (
              <div className="dash-mini-bar" key={`${point.label}-${index}`}>
                <span
                  style={{
                    height: `${Math.max(8, (point.minutes / chartMax) * 100)}%`,
                    background:
                      point.minutes > 0 && point.minutes === chartMax
                        ? coral
                        : undefined,
                  }}
                />
                <small>{point.label}</small>
              </div>
            ))}
          </div>
        </article>

        <div className="dash-stats-toolbar">
          <div>
            <p className="dash-label">Time intelligence</p>
            <p className="dash-section-title">
              {selectedDate
                ? new Date(`${selectedDate}T00:00:00`).toLocaleDateString("en", {
                    weekday: "long",
                    month: "short",
                    day: "numeric",
                  })
                : "Weekly statistics"}
            </p>
          </div>
          <div className="dash-period-toggle" aria-label="Statistics period">
            <button
              className={!selectedDate ? "active" : ""}
              onClick={() => selectChartPeriod(null)}
              type="button"
            >
              Week
            </button>
            {(week?.daily_focus ?? []).map((point) => (
              <button
                className={selectedDate === point.date ? "active" : ""}
                key={point.date}
                onClick={() => selectChartPeriod(point.date)}
                type="button"
              >
                {new Date(`${point.date}T00:00:00`).toLocaleDateString("en", {
                  weekday: "short",
                })}
              </button>
            ))}
          </div>
        </div>

        <article className="dash-card dash-allocation-card">
          <div className="dash-card-head">
            <div>
              <p className="dash-label">Where to spend time</p>
              <p className="dash-section-title">Planned allocation</p>
            </div>
            <span className="dash-chip">
              {allocationTotal} min
            </span>
          </div>
          <div className={`dash-donut-layout ${chartLoading ? "is-loading" : ""}`}>
            <div
              className="dash-donut"
              style={{ background: `conic-gradient(${donutGradient})` }}
              aria-label={`${allocationTotal} planned minutes`}
            >
              <div><strong>{allocationTotal}</strong><span>minutes</span></div>
            </div>
            <div className="dash-legend">
              {allocation.slice(0, 8).map((point, index) => (
                <div key={point.label}>
                  <i style={{ background: chartColors[index % chartColors.length] }} />
                  <span title={point.label}>{point.label}</span>
                  <strong>{point.planned_minutes || point.focus_minutes}m</strong>
                </div>
              ))}
              {!allocation.length ? (
                <p className="dash-empty">Add estimated time to tasks to see your allocation.</p>
              ) : null}
            </div>
          </div>
        </article>

        <article className="dash-card dash-comparison-card">
          <div className="dash-card-head">
            <div>
              <p className="dash-label">What time to spend</p>
              <p className="dash-section-title">Plan versus focused</p>
            </div>
            <div className="dash-chart-key">
              <span><i className="planned" /> Planned</span>
              <span><i className="focused" /> Focused</span>
            </div>
          </div>
          <div className={`dash-grouped-chart ${chartLoading ? "is-loading" : ""}`}>
            {comparisonBars.map((point, index) => (
              <div className="dash-bar-group" key={`${point.label}-${index}`}>
                <div className="dash-bar-pair">
                  <span
                    className="planned"
                    style={{ height: `${Math.max(3, (point.planned / comparisonMax) * 100)}%` }}
                    title={`Planned ${point.planned} minutes`}
                  />
                  <span
                    className="focused"
                    style={{ height: `${Math.max(3, (point.focused / comparisonMax) * 100)}%` }}
                    title={`Focused ${point.focused} minutes`}
                  />
                </div>
                <small title={point.label}>{point.label}</small>
              </div>
            ))}
            {!comparisonBars.length ? (
              <p className="dash-empty">No time data for this period yet.</p>
            ) : null}
          </div>
        </article>

        <article className="dash-card dash-goal-card">
          <div className="dash-card-head">
            <div>
              <p className="dash-label">Goal portfolio</p>
              <p className="dash-section-title">This week&apos;s direction</p>
            </div>
            <Icon>◎</Icon>
          </div>
          <div className="dash-goal-stats">
            <div>
              <strong>{week?.active_goals ?? 0}</strong>
              <span>Active</span>
            </div>
            <div>
              <strong>{week?.completed_goals ?? 0}</strong>
              <span>Completed</span>
            </div>
            <div>
              <strong>{weekCompletion}%</strong>
              <span>Task rate</span>
            </div>
          </div>
          <a href="/weekly-plan" className="dash-link">Manage weekly plan <span>↗</span></a>
        </article>

        <article className="dash-card dash-activity">
          <div className="dash-card-head">
            <div>
              <p className="dash-label">Activity manager</p>
              <p className="dash-section-title">Unfinished today</p>
            </div>
            <span className="dash-chip">{today?.unfinished_tasks.length ?? 0} remaining</span>
          </div>
          <div className="dash-task-list">
            {!today ? <p className="dash-empty">Loading your day…</p> : null}
            {today?.unfinished_tasks.length === 0 ? (
              <div className="dash-empty-state">
                <span>✓</span>
                <div><strong>Everything is clear.</strong><p>Nice work—protect that calm.</p></div>
              </div>
            ) : null}
            {today?.unfinished_tasks.slice(0, 4).map((task, index) => (
              <div className="dash-task" key={task.id}>
                <span className="dash-task-index">{String(index + 1).padStart(2, "0")}</span>
                <div>
                  <strong>{task.title}</strong>
                  <p>{task.estimated_minutes ?? 0} min · {task.priority} priority</p>
                </div>
                <span className={`dash-status ${task.status}`}>{task.status.replace("_", " ")}</span>
              </div>
            ))}
          </div>
          <a href="/today" className="dash-link">Open today&apos;s plan <span>→</span></a>
        </article>

        <article className="dash-card dash-review-card">
          <p className="dash-label">Daily reflection</p>
          <div className="dash-spark">✺</div>
          <p className="dash-section-title">How did today&apos;s execution feel?</p>
          <p className="dash-note">Turn today&apos;s data into one useful adjustment for tomorrow.</p>
          <a href="/review" className="dash-review-button">Write review <span>→</span></a>
        </article>
      </div>
    </section>
  );
}
