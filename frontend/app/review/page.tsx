"use client";

import { useEffect, useState } from "react";
import { api, DailyReview, DailyTask } from "../../lib/api";

function isoToday() {
  return new Date().toISOString().slice(0, 10);
}

export default function ReviewPage() {
  const [reviewDate, setReviewDate] = useState(isoToday());
  const [review, setReview] = useState<DailyReview | null>(null);
  const [tasks, setTasks] = useState<DailyTask[]>([]);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  async function load() {
    setError("");
    try {
      setTasks(await api.getTodayTasks());
      try {
        setReview(await api.getReview(reviewDate));
      } catch {
        setReview(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load review data");
    }
  }

  useEffect(() => {
    load();
  }, [reviewDate]);

  async function generateReview() {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const generated = await api.generateReview({ review_date: reviewDate });
      setReview(generated);
      setMessage("Review generated and saved.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate review");
    } finally {
      setBusy(false);
    }
  }

  const completed = tasks.filter((task) => task.status === "completed");
  const unfinished = tasks.filter((task) => task.status !== "completed" && task.status !== "cancelled");

  return (
    <section className="page">
      <header className="page-header">
        <div>
          <p className="eyebrow">Daily review</p>
          <h1>Close the loop</h1>
          <p className="muted">Generate an AI summary from today’s tasks and study sessions.</p>
        </div>
        <div className="actions">
          <input className="input" type="date" value={reviewDate} onChange={(event) => setReviewDate(event.target.value)} />
          <button className="button primary" disabled={busy} onClick={generateReview}>
            {busy ? "Generating..." : "Generate review"}
          </button>
        </div>
      </header>

      {error ? <div className="error">{error}</div> : null}
      {message ? <div className="success">{message}</div> : null}

      <div className="grid three">
        <div className="card">
          <p className="eyebrow">Planned</p>
          <p className="stat">{review?.planned_tasks ?? tasks.length}</p>
        </div>
        <div className="card">
          <p className="eyebrow">Completed</p>
          <p className="stat">{review?.completed_tasks ?? completed.length}</p>
        </div>
        <div className="card">
          <p className="eyebrow">Focus</p>
          <p className="stat">{review?.focus_minutes ?? 0} min</p>
        </div>
      </div>

      <div className="grid two">
        <div className="card">
          <h2>Completed tasks</h2>
          <div className="list">
            {completed.length === 0 ? <p className="muted">No completed tasks yet.</p> : null}
            {completed.map((task) => (
              <article className="item" key={task.id}>
                <strong>{task.title}</strong>
                <p className="muted">{task.estimated_minutes ?? 0} min · {task.priority}</p>
              </article>
            ))}
          </div>
        </div>

        <div className="card">
          <h2>Unfinished tasks</h2>
          <div className="list">
            {unfinished.length === 0 ? <p className="muted">No unfinished tasks.</p> : null}
            {unfinished.map((task) => (
              <article className="item" key={task.id}>
                <strong>{task.title}</strong>
                <p className="muted">{task.status} · {task.estimated_minutes ?? 0} min</p>
              </article>
            ))}
          </div>
        </div>
      </div>

      <div className="card">
        <h2>AI daily summary</h2>
        {review ? (
          <>
            <div className="review-text">{review.summary}</div>
            <h3>Tomorrow adjustment</h3>
            <p className="muted">{review.tomorrow_adjustment || "No adjustment saved."}</p>
          </>
        ) : (
          <p className="muted">No review saved for this date yet.</p>
        )}
      </div>
    </section>
  );
}
