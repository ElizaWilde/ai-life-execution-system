"use client";

import { useEffect, useState } from "react";
import { api, TodayDashboard, WeekDashboard } from "../../lib/api";

function percent(value: number) {
  return `${Math.round(value * 100)}%`;
}

export default function DashboardPage() {
  const [today, setToday] = useState<TodayDashboard | null>(null);
  const [week, setWeek] = useState<WeekDashboard | null>(null);
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

  const maxFocus = Math.max(1, ...(week?.daily_focus.map((point) => point.focus_minutes) || [1]));

  return (
    <section className="page">
      <header className="page-header">
        <div>
          <p className="eyebrow">Dashboard</p>
          <h1>Execution overview</h1>
          <p className="muted">Focus time, completion rate, and active goal progress.</p>
        </div>
      </header>

      {error ? <div className="error">{error}</div> : null}

      <div className="grid three">
        <div className="card">
          <p className="eyebrow">Today focus</p>
          <p className="stat">{today?.focus_minutes ?? 0} min</p>
        </div>
        <div className="card">
          <p className="eyebrow">Today completion</p>
          <p className="stat">{today ? percent(today.completion_rate) : "0%"}</p>
          <p className="muted">
            {today?.completed_tasks ?? 0}/{today?.planned_tasks ?? 0} tasks
          </p>
        </div>
        <div className="card">
          <p className="eyebrow">Weekly focus</p>
          <p className="stat">{week?.focus_minutes ?? 0} min</p>
        </div>
      </div>

      <div className="grid two">
        <div className="card">
          <h2>Weekly focus</h2>
          <div className="list">
            {week?.daily_focus.map((point) => (
              <div className="bar-row" key={point.date}>
                <div className="item-row">
                  <span>{point.date}</span>
                  <strong>{point.focus_minutes} min</strong>
                </div>
                <div className="bar">
                  <div className="bar-fill" style={{ width: `${(point.focus_minutes / maxFocus) * 100}%` }} />
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="card">
          <h2>Goal progress</h2>
          <p className="stat">{week?.active_goals ?? 0}</p>
          <p className="muted">active goals</p>
          <p className="stat">{week?.completed_goals ?? 0}</p>
          <p className="muted">completed goals this week</p>
        </div>
      </div>

      <div className="card">
        <h2>Unfinished today</h2>
        <div className="list">
          {today?.unfinished_tasks.length === 0 ? <p className="muted">Nothing unfinished. Nice.</p> : null}
          {today?.unfinished_tasks.map((task) => (
            <article className="item" key={task.id}>
              <div className="item-row">
                <strong>{task.title}</strong>
                <span className="badge">{task.status}</span>
              </div>
              <p className="muted">{task.estimated_minutes ?? 0} min · {task.priority}</p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
