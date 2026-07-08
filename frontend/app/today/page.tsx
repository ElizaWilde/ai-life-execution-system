"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { api, DailyTask, Priority } from "../../lib/api";

function isoToday() {
  return new Date().toISOString().slice(0, 10);
}

export default function TodayPage() {
  const [tasks, setTasks] = useState<DailyTask[]>([]);
  const [title, setTitle] = useState("");
  const [minutes, setMinutes] = useState("30");
  const [priority, setPriority] = useState<Priority>("medium");
  const [availableMinutes, setAvailableMinutes] = useState("90");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  async function loadTasks() {
    setError("");
    try {
      setTasks(await api.getTodayTasks());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load tasks");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadTasks();
  }, []);

  async function createTask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api.createTask({
        title,
        task_date: isoToday(),
        estimated_minutes: minutes ? Number(minutes) : null,
        priority,
        source: "manual",
      });
      setTitle("");
      await loadTasks();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create task");
    } finally {
      setBusy(false);
    }
  }

  async function generatePlan() {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const result = await api.generatePlan({
        available_minutes: Number(availableMinutes),
        task_date: isoToday(),
      });
      setMessage(`Generated ${result.tasks.length} tasks (${result.total_estimated_minutes} min).`);
      await loadTasks();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate plan");
    } finally {
      setBusy(false);
    }
  }

  async function setStatus(task: DailyTask, status: DailyTask["status"]) {
    await api.updateTask(task.id, { status });
    await loadTasks();
  }

  return (
    <section className="page">
      <header className="page-header">
        <div>
          <p className="eyebrow">Today</p>
          <h1>Daily execution</h1>
          <p className="muted">Generate an AI plan, add manual tasks, and mark progress.</p>
        </div>
      </header>

      {error ? <div className="error">{error}</div> : null}
      {message ? <div className="success">{message}</div> : null}

      <div className="grid two">
        <div className="card">
          <h2>Generate today’s plan</h2>
          <label className="field">
            <span>Available minutes</span>
            <input className="input" type="number" min="1" value={availableMinutes} onChange={(event) => setAvailableMinutes(event.target.value)} />
          </label>
          <button className="button primary" disabled={busy} onClick={generatePlan}>
            {busy ? "Working..." : "Generate AI plan"}
          </button>
        </div>

        <div className="card">
          <h2>Add manual task</h2>
          <form className="form" onSubmit={createTask}>
            <label className="field">
              <span>Title</span>
              <input className="input" value={title} onChange={(event) => setTitle(event.target.value)} required />
            </label>
            <div className="grid two">
              <label className="field">
                <span>Minutes</span>
                <input className="input" type="number" min="0" value={minutes} onChange={(event) => setMinutes(event.target.value)} />
              </label>
              <label className="field">
                <span>Priority</span>
                <select className="input" value={priority} onChange={(event) => setPriority(event.target.value as Priority)}>
                  <option value="high">High</option>
                  <option value="medium">Medium</option>
                  <option value="low">Low</option>
                </select>
              </label>
            </div>
            <button className="button secondary" disabled={busy} type="submit">
              Add task
            </button>
          </form>
        </div>
      </div>

      <div className="card">
        <h2>Today’s tasks</h2>
        <div className="list">
          {loading ? <p className="muted">Loading tasks...</p> : null}
          {!loading && tasks.length === 0 ? <p className="muted">No tasks yet.</p> : null}
          {tasks.map((task) => (
            <article className="item" key={task.id}>
              <div className="item-row">
                <strong>{task.title}</strong>
                <span className={`badge ${task.status === "completed" ? "done" : ""}`}>{task.status}</span>
              </div>
              <p className="muted">
                {task.estimated_minutes ?? 0} min · {task.priority} · {task.source}
              </p>
              <div className="actions">
                <button className="button secondary" onClick={() => setStatus(task, "in_progress")}>
                  Start
                </button>
                <button className="button primary" onClick={() => setStatus(task, "completed")}>
                  Complete
                </button>
                <Link className="button secondary" href="/timer">
                  Open timer
                </Link>
              </div>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
