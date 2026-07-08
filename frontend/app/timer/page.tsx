"use client";

import { useEffect, useMemo, useState } from "react";
import { api, DailyTask, StudySession } from "../../lib/api";

export default function TimerPage() {
  const [tasks, setTasks] = useState<DailyTask[]>([]);
  const [sessions, setSessions] = useState<StudySession[]>([]);
  const [selectedTaskId, setSelectedTaskId] = useState("");
  const [subject, setSubject] = useState("Backend testing");
  const [notes, setNotes] = useState("");
  const [running, setRunning] = useState<StudySession | null>(null);
  const [now, setNow] = useState(Date.now());
  const [error, setError] = useState("");

  const elapsedSeconds = useMemo(() => {
    if (!running) return 0;
    return Math.max(0, Math.floor((now - new Date(running.started_at).getTime()) / 1000));
  }, [now, running]);

  async function load() {
    try {
      const [loadedTasks, loadedSessions] = await Promise.all([
        api.getTodayTasks(),
        api.getTodaySessions(),
      ]);
      setTasks(loadedTasks);
      setSessions(loadedSessions);
      setRunning(loadedSessions.find((session) => session.status === "running") || null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load timer data");
    }
  }

  useEffect(() => {
    load();
  }, []);

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  async function startSession() {
    setError("");
    try {
      const session = await api.startSession({
        daily_task_id: selectedTaskId ? Number(selectedTaskId) : null,
        subject,
      });
      setRunning(session);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start session");
    }
  }

  async function finishSession() {
    if (!running) return;
    setError("");
    try {
      await api.finishSession({
        session_id: running.id,
        notes: notes || null,
      });
      setRunning(null);
      setNotes("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to finish session");
    }
  }

  const minutes = Math.floor(elapsedSeconds / 60);
  const seconds = elapsedSeconds % 60;

  return (
    <section className="page">
      <header className="page-header">
        <div>
          <p className="eyebrow">Timer</p>
          <h1>Study session</h1>
          <p className="muted">Start a focus session linked to a daily task.</p>
        </div>
      </header>

      {error ? <div className="error">{error}</div> : null}

      <div className="grid two">
        <div className="card">
          <h2>{running ? "Running session" : "Start session"}</h2>
          <p className="stat">
            {String(minutes).padStart(2, "0")}:{String(seconds).padStart(2, "0")}
          </p>
          <div className="form">
            <label className="field">
              <span>Task</span>
              <select className="input" disabled={Boolean(running)} value={selectedTaskId} onChange={(event) => setSelectedTaskId(event.target.value)}>
                <option value="">No linked task</option>
                {tasks.map((task) => (
                  <option key={task.id} value={task.id}>
                    {task.title}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>Subject</span>
              <input className="input" disabled={Boolean(running)} value={subject} onChange={(event) => setSubject(event.target.value)} />
            </label>
            {running ? (
              <label className="field">
                <span>Finish notes</span>
                <textarea className="input" rows={4} value={notes} onChange={(event) => setNotes(event.target.value)} />
              </label>
            ) : null}
          </div>
          <div className="actions">
            {!running ? (
              <button className="button primary" onClick={startSession}>
                Start session
              </button>
            ) : (
              <button className="button danger" onClick={finishSession}>
                Finish session
              </button>
            )}
          </div>
        </div>

        <div className="card">
          <h2>Today’s sessions</h2>
          <div className="list">
            {sessions.length === 0 ? <p className="muted">No sessions today.</p> : null}
            {sessions.map((session) => (
              <article className="item" key={session.id}>
                <div className="item-row">
                  <strong>{session.subject}</strong>
                  <span className={`badge ${session.status === "completed" ? "done" : ""}`}>{session.status}</span>
                </div>
                <p className="muted">
                  {session.duration_minutes ?? 0} min
                  {session.notes ? ` · ${session.notes}` : ""}
                </p>
              </article>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
