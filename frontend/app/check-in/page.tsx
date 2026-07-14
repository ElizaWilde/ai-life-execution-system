"use client";

import { FormEvent, useEffect, useState } from "react";
import {
  api,
  CoachingRecommendation,
  DailyCheckIn,
  EnergyLevel,
  MoodLevel,
} from "../../lib/api";

const energyOptions: { value: EnergyLevel; label: string; hint: string }[] = [
  { value: "depleted", label: "Depleted", hint: "Rest and essentials only" },
  { value: "low", label: "Low", hint: "Limited capacity" },
  { value: "steady", label: "Steady", hint: "A measured pace" },
  { value: "high", label: "High", hint: "Ready for focused work" },
  { value: "energized", label: "Energized", hint: "Strong sustainable capacity" },
];

const moodOptions: { value: MoodLevel; label: string }[] = [
  { value: "struggling", label: "Struggling" },
  { value: "low", label: "Low" },
  { value: "neutral", label: "Neutral" },
  { value: "good", label: "Good" },
  { value: "great", label: "Great" },
];

function localToday() {
  const now = new Date();
  const offset = now.getTimezoneOffset() * 60_000;
  return new Date(now.getTime() - offset).toISOString().slice(0, 10);
}

export default function CheckInPage() {
  const today = localToday();
  const [saved, setSaved] = useState<DailyCheckIn | null>(null);
  const [coaching, setCoaching] = useState<CoachingRecommendation | null>(null);
  const [energy, setEnergy] = useState<EnergyLevel>("steady");
  const [mood, setMood] = useState<MoodLevel>("neutral");
  const [sleepHours, setSleepHours] = useState("7");
  const [stress, setStress] = useState("3");
  const [notes, setNotes] = useState("");
  const [cycleDay, setCycleDay] = useState("");
  const [cycleNotes, setCycleNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [coachingBusy, setCoachingBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    async function load() {
      try {
        const existing = await api.getTodayCheckIn();
        setSaved(existing);
        setEnergy(existing.energy_level);
        setMood(existing.mood_level);
        setSleepHours(String(existing.sleep_hours));
        setStress(existing.stress_level === null ? "" : String(existing.stress_level));
        setNotes(existing.notes || "");
        setCycleDay(existing.cycle_day === null ? "" : String(existing.cycle_day));
        setCycleNotes(existing.cycle_notes || "");
      } catch {
        setSaved(null);
      }

      try {
        setCoaching(await api.getCoaching(today));
      } catch {
        setCoaching(null);
      }
    }
    load();
  }, [today]);

  async function saveCheckIn(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setMessage("");

    const payload = {
      energy_level: energy,
      mood_level: mood,
      sleep_hours: Number(sleepHours),
      stress_level: stress ? Number(stress) : null,
      notes: notes.trim() || null,
      cycle_day: cycleDay ? Number(cycleDay) : null,
      cycle_notes: cycleNotes.trim() || null,
    };

    try {
      const result = saved
        ? await api.updateCheckIn(today, payload)
        : await api.createCheckIn({ check_in_date: today, ...payload });
      setSaved(result);
      setMessage(saved ? "Today’s check-in was updated." : "Today’s check-in was saved.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save check-in");
    } finally {
      setBusy(false);
    }
  }

  async function generateCoaching() {
    setCoachingBusy(true);
    setError("");
    setMessage("");
    try {
      const result = await api.generateCoaching({ target_date: today });
      setCoaching(result);
      setMessage("Today’s coaching recommendation was generated and saved.");
    } catch (err) {
      const detail = err instanceof Error ? err.message : "Failed to generate coaching";
      if (detail.toLowerCase().includes("already exists")) {
        try {
          setCoaching(await api.getCoaching(today));
          setMessage("Today’s saved coaching recommendation is shown below.");
        } catch {
          setError(detail);
        }
      } else {
        setError(detail);
      }
    } finally {
      setCoachingBusy(false);
    }
  }

  return (
    <section className="page phase-page">
      <header className="page-header">
        <div>
          <p className="eyebrow">Daily condition</p>
          <h1>Check in before you plan</h1>
          <p className="muted">
            Describe your condition in human terms. These signals adjust capacity;
            they are not a score of your worth or effort.
          </p>
        </div>
        <span className="date-pill">{today}</span>
      </header>

      {error ? <div className="error">{error}</div> : null}
      {message ? <div className="success">{message}</div> : null}

      <div className="grid phase-layout">
        <form className="card form phase-form" onSubmit={saveCheckIn}>
          <div>
            <p className="eyebrow">Energy</p>
            <h2>What capacity do you have?</h2>
          </div>
          <div className="choice-grid energy-choices">
            {energyOptions.map((option) => (
              <button
                className={`choice-button ${energy === option.value ? "selected" : ""}`}
                key={option.value}
                onClick={() => setEnergy(option.value)}
                type="button"
              >
                <strong>{option.label}</strong>
                <small>{option.hint}</small>
              </button>
            ))}
          </div>

          <div>
            <p className="eyebrow">Mood</p>
            <h2>How does today feel?</h2>
          </div>
          <div className="choice-grid mood-choices">
            {moodOptions.map((option) => (
              <button
                className={`choice-button compact ${mood === option.value ? "selected" : ""}`}
                key={option.value}
                onClick={() => setMood(option.value)}
                type="button"
              >
                {option.label}
              </button>
            ))}
          </div>

          <div className="grid two">
            <label className="field">
              <span>Sleep hours</span>
              <input
                className="input"
                max="24"
                min="0"
                onChange={(event) => setSleepHours(event.target.value)}
                required
                step="0.5"
                type="number"
                value={sleepHours}
              />
            </label>
            <label className="field">
              <span>Stress level (1–5)</span>
              <input
                className="input"
                max="5"
                min="1"
                onChange={(event) => setStress(event.target.value)}
                type="number"
                value={stress}
              />
            </label>
          </div>

          <label className="field">
            <span>Anything affecting today?</span>
            <textarea
              className="input"
              onChange={(event) => setNotes(event.target.value)}
              placeholder="Optional context for your coach"
              rows={3}
              value={notes}
            />
          </label>

          <details className="optional-panel">
            <summary>Optional cycle context</summary>
            <div className="grid two">
              <label className="field">
                <span>Cycle day</span>
                <input
                  className="input"
                  min="1"
                  onChange={(event) => setCycleDay(event.target.value)}
                  type="number"
                  value={cycleDay}
                />
              </label>
              <label className="field">
                <span>Cycle notes</span>
                <input
                  className="input"
                  onChange={(event) => setCycleNotes(event.target.value)}
                  value={cycleNotes}
                />
              </label>
            </div>
          </details>

          <button className="button primary" disabled={busy} type="submit">
            {busy ? "Saving…" : saved ? "Update today’s check-in" : "Save today’s check-in"}
          </button>
        </form>

        <aside className="phase-stack">
          <article className="card coaching-card">
            <div className="section-heading">
              <div>
                <p className="eyebrow">Personal coaching</p>
                <h2>Today’s recommendation</h2>
              </div>
              {coaching ? (
                <span className={`workload-pill ${coaching.workload_level}`}>
                  {coaching.workload_level}
                </span>
              ) : null}
            </div>

            {coaching ? (
              <>
                <div className="readiness-block">
                  <strong>{Math.round(coaching.readiness_score)}</strong>
                  <span>readiness</span>
                  <div className="readiness-track">
                    <i style={{ width: `${coaching.readiness_score}%` }} />
                  </div>
                </div>
                <p className="coaching-summary">{coaching.summary}</p>
                <AdviceList title="Suggestions" items={coaching.suggestions} />
                <AdviceList title="Planning changes" items={coaching.planning_changes} />
                {coaching.risk_factors.length ? (
                  <AdviceList title="Signals to respect" items={coaching.risk_factors} />
                ) : null}
              </>
            ) : (
              <div className="empty-panel">
                <strong>No recommendation generated yet.</strong>
                <p>Save today’s check-in, then explicitly ask the coach for guidance.</p>
              </div>
            )}

            <button
              className="button secondary"
              disabled={!saved || coachingBusy || Boolean(coaching)}
              onClick={generateCoaching}
              type="button"
            >
              {coachingBusy
                ? "Generating…"
                : coaching
                  ? "Recommendation saved"
                  : "Generate today’s coaching"}
            </button>
          </article>

          <article className="card next-step-card">
            <p className="eyebrow">Next step</p>
            <h2>Turn capacity into a realistic plan</h2>
            <p className="muted">
              Daily planning uses the deterministic workload adjustment calculated
              from this check-in and recent execution history.
            </p>
            <a className="button primary" href="/today">Open today’s plan</a>
          </article>
        </aside>
      </div>
    </section>
  );
}

function AdviceList({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="advice-list">
      <h3>{title}</h3>
      <ul>
        {items.map((item) => <li key={item}>{item}</li>)}
      </ul>
    </div>
  );
}
