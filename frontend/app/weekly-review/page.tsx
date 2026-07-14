"use client";

import { useEffect, useState } from "react";
import { api, WeeklyReview } from "../../lib/api";

function currentMonday() {
  const now = new Date();
  const day = now.getDay();
  const distance = day === 0 ? 6 : day - 1;
  const monday = new Date(now);
  monday.setDate(now.getDate() - distance);
  const year = monday.getFullYear();
  const month = String(monday.getMonth() + 1).padStart(2, "0");
  const dayOfMonth = String(monday.getDate()).padStart(2, "0");
  return `${year}-${month}-${dayOfMonth}`;
}

function percent(value: number) {
  return `${Math.round(value * 100)}%`;
}

function label(value: string) {
  return value.replaceAll("_", " ");
}

export default function WeeklyReviewPage() {
  const [weekStart, setWeekStart] = useState(currentMonday());
  const [review, setReview] = useState<WeeklyReview | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    async function load() {
      setError("");
      try {
        setReview(await api.getWeeklyReview(weekStart));
      } catch {
        setReview(null);
      }
    }
    load();
  }, [weekStart]);

  async function generateReview() {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const generated = await api.generateWeeklyReview({ week_start: weekStart });
      setReview(generated);
      setMessage(review ? "Weekly review refreshed from stored behavior." : "Weekly review generated and saved.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate weekly review");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="page phase-page">
      <header className="page-header">
        <div>
          <p className="eyebrow">Weekly reflection</p>
          <h1>Review what actually happened</h1>
          <p className="muted">
            Statistics come from stored tasks, focus sessions, and check-ins. The AI
            explains those facts; it does not guess your week.
          </p>
        </div>
        <div className="review-controls">
          <label className="field">
            <span>Week starting Monday</span>
            <input
              className="input"
              onChange={(event) => setWeekStart(event.target.value)}
              type="date"
              value={weekStart}
            />
          </label>
          <button className="button primary" disabled={busy} onClick={generateReview}>
            {busy ? "Generating…" : review ? "Refresh review" : "Generate weekly review"}
          </button>
        </div>
      </header>

      {error ? <div className="error">{error}</div> : null}
      {message ? <div className="success">{message}</div> : null}

      {review ? (
        <>
          <div className="grid four review-metrics">
            <Metric label="Completion" value={percent(review.completion_rate)} detail={`${review.completed_tasks} of ${review.planned_tasks} tasks`} />
            <Metric label="Focus time" value={`${review.focus_minutes}`} detail="minutes recorded" />
            <Metric label="Average sleep" value={review.average_sleep_hours === null ? "—" : `${review.average_sleep_hours}`} detail={review.average_sleep_hours === null ? "no check-ins" : "hours per check-in"} />
            <Metric label="Check-ins" value={`${review.check_in_days}`} detail="days represented" />
          </div>

          <article className="card weekly-summary-card">
            <div className="section-heading">
              <div>
                <p className="eyebrow">{review.week_start} → {review.week_end}</p>
                <h2>Weekly summary</h2>
              </div>
              <span className="grounded-pill">Grounded in stored data</span>
            </div>
            <p className="weekly-summary">{review.summary}</p>
          </article>

          <div className="grid two">
            <DistributionCard title="Energy pattern" values={review.energy_distribution_json} empty="No energy check-ins for this week." />
            <DistributionCard title="Mood pattern" values={review.mood_distribution_json} empty="No mood check-ins for this week." />
          </div>

          <div className="grid three review-columns">
            <ReviewList title="Achievements" items={review.achievements_json} tone="positive" />
            <ReviewList title="Obstacles" items={review.obstacles_json} tone="caution" />
            <ReviewList title="Next-week actions" items={review.next_week_actions_json} tone="action" />
          </div>
        </>
      ) : (
        <article className="card empty-review-card">
          <div className="empty-orbit">7d</div>
          <div>
            <p className="eyebrow">No saved review</p>
            <h2>Generate this week when you are ready</h2>
            <p className="muted">
              This is a manual action. Nothing will run automatically on Sunday.
            </p>
          </div>
        </article>
      )}
    </section>
  );
}

function Metric({ label: metricLabel, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <article className="card metric-card">
      <p className="eyebrow">{metricLabel}</p>
      <strong>{value}</strong>
      <span>{detail}</span>
    </article>
  );
}

function DistributionCard({ title, values, empty }: { title: string; values: Record<string, number>; empty: string }) {
  const entries = Object.entries(values);
  return (
    <article className="card distribution-card">
      <h2>{title}</h2>
      {entries.length ? (
        <div className="distribution-list">
          {entries.map(([name, count]) => (
            <span key={name}><strong>{count}</strong>{label(name)}</span>
          ))}
        </div>
      ) : <p className="muted">{empty}</p>}
    </article>
  );
}

function ReviewList({ title, items, tone }: { title: string; items: string[]; tone: string }) {
  return (
    <article className={`card review-list-card ${tone}`}>
      <h2>{title}</h2>
      {items.length ? <ul>{items.map((item) => <li key={item}>{item}</li>)}</ul> : <p className="muted">Nothing recorded.</p>}
    </article>
  );
}
