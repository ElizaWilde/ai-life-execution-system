"use client";

import { FormEvent, useEffect, useState } from "react";
import { api, Priority, WeeklyGoal } from "../../lib/api";

function isoToday() {
  return new Date().toISOString().slice(0, 10);
}

function weekEndFrom(start: string) {
  const date = new Date(`${start}T00:00:00`);
  date.setDate(date.getDate() + 6);
  return date.toISOString().slice(0, 10);
}

export default function WeeklyPlanPage() {
  const [goals, setGoals] = useState<WeeklyGoal[]>([]);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [weekStart, setWeekStart] = useState(isoToday());
  const [priority, setPriority] = useState<Priority>("high");
  const [targetMinutes, setTargetMinutes] = useState("300");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function loadGoals() {
    setError("");
    try {
      setGoals(await api.getCurrentGoals());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load goals");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadGoals();
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      await api.createGoal({
        title,
        description: description || null,
        week_start: weekStart,
        week_end: weekEndFrom(weekStart),
        priority,
        target_minutes: targetMinutes ? Number(targetMinutes) : null,
      });
      setTitle("");
      setDescription("");
      await loadGoals();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create goal");
    } finally {
      setSaving(false);
    }
  }

  async function completeGoal(goal: WeeklyGoal) {
    await api.updateGoal(goal.id, { status: "completed" });
    await loadGoals();
  }

  return (
    <section className="page">
      <header className="page-header">
        <div>
          <p className="eyebrow">Weekly plan</p>
          <h1>This week’s goals</h1>
          <p className="muted">Create active goals that feed AI daily planning.</p>
        </div>
      </header>

      {error ? <div className="error">{error}</div> : null}

      <div className="grid two">
        <div className="card">
          <h2>Create goal</h2>
          <form className="form" onSubmit={submit}>
            <label className="field">
              <span>Title</span>
              <input className="input" value={title} onChange={(event) => setTitle(event.target.value)} required />
            </label>
            <label className="field">
              <span>Description</span>
              <textarea className="input" value={description} onChange={(event) => setDescription(event.target.value)} rows={3} />
            </label>
            <div className="grid two">
              <label className="field">
                <span>Week start</span>
                <input className="input" type="date" value={weekStart} onChange={(event) => setWeekStart(event.target.value)} />
              </label>
              <label className="field">
                <span>Target minutes</span>
                <input className="input" type="number" min="0" value={targetMinutes} onChange={(event) => setTargetMinutes(event.target.value)} />
              </label>
            </div>
            <label className="field">
              <span>Priority</span>
              <select className="input" value={priority} onChange={(event) => setPriority(event.target.value as Priority)}>
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
              </select>
            </label>
            <button className="button primary" disabled={saving} type="submit">
              {saving ? "Creating..." : "Create weekly goal"}
            </button>
          </form>
        </div>

        <div className="card">
          <h2>Current goals</h2>
          <div className="list">
            {loading ? <p className="muted">Loading goals...</p> : null}
            {!loading && goals.length === 0 ? <p className="muted">No active goals yet.</p> : null}
            {goals.map((goal) => (
              <article className="item" key={goal.id}>
                <div className="item-row">
                  <strong>{goal.title}</strong>
                  <span className="badge">{goal.priority}</span>
                </div>
                <p className="muted">{goal.description || "No description"}</p>
                <p className="muted">
                  {goal.week_start} → {goal.week_end}
                  {goal.target_minutes ? ` · ${goal.target_minutes} min` : ""}
                </p>
                <button className="button secondary" onClick={() => completeGoal(goal)}>
                  Mark completed
                </button>
              </article>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
