"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { announceCheckInUpdate, subscribeToCheckInUpdates } from "../../lib/check-in-sync";
import { AVAILABLE_TIME_OPTIONS, availableTimeBucket } from "../../lib/check-in-options";
import {
  api,
  CoachingRecommendation,
  DailyCheckIn,
  EnergyLevel,
  MoodLevel,
} from "../../lib/api";

type ConditionIconName = EnergyLevel | "moodLow" | "struggling" | "neutral" | "good" | "great" | "smile" | "spark" | "target" | "calendar" | "clock" | "focus" | "difficulty";

const energyOptions: { value: EnergyLevel; label: string; hint: string; icon: ConditionIconName; tone: string }[] = [
  { value: "depleted", label: "Depleted", hint: "Rest and essentials only", icon: "depleted", tone: "red" },
  { value: "low", label: "Low", hint: "Limited capacity", icon: "low", tone: "amber" },
  { value: "steady", label: "Steady", hint: "A measured pace", icon: "steady", tone: "purple" },
  { value: "high", label: "High", hint: "Ready for focused work", icon: "high", tone: "green" },
  { value: "energized", label: "Energized", hint: "Strong sustainable capacity", icon: "energized", tone: "green" },
];

const moodOptions: { value: MoodLevel; label: string; icon: ConditionIconName; tone: string }[] = [
  { value: "struggling", label: "Struggling", icon: "struggling", tone: "red" },
  { value: "low", label: "Low", icon: "moodLow", tone: "amber" },
  { value: "neutral", label: "Neutral", icon: "neutral", tone: "purple" },
  { value: "good", label: "Good", icon: "good", tone: "green" },
  { value: "great", label: "Great", icon: "great", tone: "green" },
];

const focusOptions = ["Deep work", "Meetings", "Study", "Recovery"] as const;
const difficultyOptions = [
  { value: "low", label: "Low", hint: "Keep it light" },
  { value: "medium", label: "Medium", hint: "Balanced effort" },
  { value: "high", label: "High", hint: "Demanding day" },
] as const;

function ConditionIcon({ name, size = 22 }: { name: ConditionIconName; size?: number }) {
  const paths: Record<ConditionIconName, React.ReactNode> = {
    depleted: <><rect x="4" y="7" width="15" height="10" rx="2"/><path d="M21 10v4"/></>,
    low: <><rect x="4" y="7" width="15" height="10" rx="2"/><path d="M7 10v4M21 10v4"/></>,
    steady: <path d="M3 12c2.2-5 4.4 5 6.6 0s4.4 5 6.6 0 3.2-2.5 4.8 0"/>,
    high: <><circle cx="12" cy="12" r="9"/><path d="m8 12 4-4 4 4M12 8v9"/></>,
    energized: <path d="m13 2-8 12h7l-1 8 8-12h-7l1-8Z"/>,
    struggling: <><circle cx="12" cy="12" r="9"/><path d="M8.5 10h.01M15.5 10h.01M8.5 17c1.4-2 5.6-2 7 0"/></>,
    moodLow: <><circle cx="12" cy="12" r="9"/><path d="M8.5 10h.01M15.5 10h.01M9 16h6"/></>,
    neutral: <><circle cx="12" cy="12" r="9"/><path d="M8.5 10h.01M15.5 10h.01M9 15.5h6"/></>,
    good: <><circle cx="12" cy="12" r="9"/><path d="M8.5 10h.01M15.5 10h.01M8.5 14.5c1.5 2 5.5 2 7 0"/></>,
    great: <><circle cx="12" cy="12" r="9"/><path d="m12 7 1.2 2.4 2.7.4-2 1.9.5 2.7-2.4-1.3-2.4 1.3.5-2.7-2-1.9 2.7-.4L12 7Z"/></>,
    smile: <><circle cx="12" cy="12" r="9"/><path d="M8.5 10h.01M15.5 10h.01M8.5 14.5c1.5 2 5.5 2 7 0"/></>,
    spark: <path d="m12 2 1.6 5.1a5 5 0 0 0 3.3 3.3L22 12l-5.1 1.6a5 5 0 0 0-3.3 3.3L12 22l-1.6-5.1a5 5 0 0 0-3.3-3.3L2 12l5.1-1.6a5 5 0 0 0 3.3-3.3L12 2Z"/>,
    target: <><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="4"/><path d="m15 9 6-6M17 3h4v4"/></>,
    calendar: <><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 10h18M9 15l2 2 4-5"/></>,
    clock: <><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></>,
    focus: <><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="4"/><circle cx="12" cy="12" r="1"/></>,
    difficulty: <><path d="M4 19V9M10 19V5M16 19v-7M22 19H2"/><path d="m16 8 3-3 3 3"/></>,
  };
  return <svg aria-hidden="true" fill="none" height={size} viewBox="0 0 24 24" width={size}>{paths[name]}</svg>;
}

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
  const [availableMinutes, setAvailableMinutes] = useState("360");
  const [focusMode, setFocusMode] = useState<"Deep work" | "Meetings" | "Study" | "Recovery">("Deep work");
  const [difficulty, setDifficulty] = useState<"low" | "medium" | "high">("medium");
  const [notes, setNotes] = useState("");
  const [cycleDay, setCycleDay] = useState("");
  const [cycleNotes, setCycleNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [coachingBusy, setCoachingBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  async function loadCheckIn() {
    try {
      const existing = await api.getTodayCheckIn();
      setSaved(existing);
      setEnergy(existing.energy_level);
      setMood(existing.mood_level);
      setSleepHours(String(existing.sleep_hours));
      setAvailableMinutes(availableTimeBucket(existing.available_minutes ?? 360));
      setFocusMode(existing.focus_mode ?? "Deep work");
      setDifficulty((existing.stress_level ?? 3) >= 4 ? "high" : (existing.stress_level ?? 3) <= 2 ? "low" : "medium");
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

  useEffect(() => {
    loadCheckIn();
    return subscribeToCheckInUpdates(today, loadCheckIn);
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
      stress_level: difficulty === "high" ? 4 : difficulty === "low" ? 2 : 3,
      available_minutes: Number(availableMinutes),
      focus_mode: focusMode,
      notes: notes.trim() || null,
      cycle_day: cycleDay ? Number(cycleDay) : null,
      cycle_notes: cycleNotes.trim() || null,
    };

    try {
      const result = saved
        ? await api.updateCheckIn(today, payload)
        : await api.createCheckIn({ check_in_date: today, ...payload });
      setSaved(result);
      announceCheckInUpdate(today);
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
    <section className="page phase-page condition-page">
      <header className="page-header condition-header">
        <div>
          <p className="eyebrow">Daily condition</p>
          <h1>Check in before you plan</h1>
          <p className="muted">Describe your condition in human terms. These signals adjust capacity; they are not a score of your worth or effort.</p>
        </div>
        <span className="date-pill"><ConditionIcon name="calendar" size={17} /> {today}</span>
      </header>

      {error ? <div className="error">{error}</div> : null}
      {message ? <div className="success">{message}</div> : null}

      <div className="grid phase-layout condition-layout">
        <form className="card form phase-form condition-form" onSubmit={saveCheckIn}>
          <section className="condition-section">
            <div className="condition-question"><p><ConditionIcon name="energized" size={18} /> Energy</p><h2>What capacity do you have?</h2></div>
            <div className="choice-grid energy-choices">
              {energyOptions.map((option) => (
                <button className={`choice-button condition-energy-choice ${option.tone} ${energy === option.value ? "selected" : ""}`} key={option.value} onClick={() => setEnergy(option.value)} type="button">
                  <span className="condition-choice-icon"><ConditionIcon name={option.icon} size={28} /></span>
                  <strong>{option.label}</strong>
                  <small>{option.hint}</small>
                  {energy === option.value ? <i className="choice-selected-mark">✓</i> : null}
                </button>
              ))}
            </div>
          </section>

          <section className="condition-section mood-section">
            <div className="condition-question"><p><ConditionIcon name="smile" size={18} /> Mood</p><h2>How does today feel?</h2></div>
            <div className="choice-grid mood-choices">
              {moodOptions.map((option) => (
                <button className={`choice-button compact condition-mood-choice ${option.tone} ${mood === option.value ? "selected" : ""}`} key={option.value} onClick={() => setMood(option.value)} type="button">
                  <ConditionIcon name={option.icon} size={23} /><span>{option.label}</span>
                  {mood === option.value ? <i className="choice-selected-mark">✓</i> : null}
                </button>
              ))}
            </div>
          </section>

          <section className="condition-section">
            <div className="condition-question"><p><ConditionIcon name="clock" size={18} /> Available Time Today</p><h2>How much time can you protect?</h2></div>
            <div className="choice-grid condition-preference-grid available-time-choices">
              {AVAILABLE_TIME_OPTIONS.map((option) => <button className={`choice-button condition-preference-choice ${availableMinutes === option.value ? "selected" : ""}`} key={option.value} onClick={() => setAvailableMinutes(option.value)} type="button"><ConditionIcon name="clock" size={23} /><strong>{option.label}</strong><small>{option.hint}</small>{availableMinutes === option.value ? <i className="choice-selected-mark">✓</i> : null}</button>)}
            </div>
          </section>

          <section className="condition-section">
            <div className="condition-question"><p><ConditionIcon name="focus" size={18} /> Today’s Focus</p><h2>What kind of work matters today?</h2></div>
            <div className="choice-grid condition-preference-grid focus-mode-choices">
              {focusOptions.map((option) => <button className={`choice-button condition-preference-choice ${focusMode === option ? "selected" : ""}`} key={option} onClick={() => setFocusMode(option)} type="button"><ConditionIcon name="focus" size={23} /><strong>{option}</strong>{focusMode === option ? <i className="choice-selected-mark">✓</i> : null}</button>)}
            </div>
          </section>

          <section className="condition-section">
            <div className="condition-question"><p><ConditionIcon name="difficulty" size={18} /> Difficulty</p><h2>How demanding should today be?</h2></div>
            <div className="choice-grid condition-preference-grid difficulty-choices">
              {difficultyOptions.map((option) => <button className={`choice-button condition-preference-choice ${difficulty === option.value ? "selected" : ""}`} key={option.value} onClick={() => setDifficulty(option.value)} type="button"><ConditionIcon name="difficulty" size={23} /><strong>{option.label}</strong><small>{option.hint}</small>{difficulty === option.value ? <i className="choice-selected-mark">✓</i> : null}</button>)}
            </div>
          </section>

          <label className="field condition-sleep-field"><span>Sleep hours</span><input className="input" max="12" min="3" onChange={(event) => setSleepHours(event.target.value)} required step="0.5" type="number" value={sleepHours} /></label>

          <label className="field condition-notes"><span>Anything affecting today?</span><textarea className="input" onChange={(event) => setNotes(event.target.value)} placeholder="Optional context for your coach" rows={3} value={notes} /></label>

          <details className="optional-panel condition-optional"><summary>Optional cycle context</summary><div className="grid two"><label className="field"><span>Cycle day</span><input className="input" min="1" onChange={(event) => setCycleDay(event.target.value)} type="number" value={cycleDay} /></label><label className="field"><span>Cycle notes</span><input className="input" onChange={(event) => setCycleNotes(event.target.value)} value={cycleNotes} /></label></div></details>

          <button className="button primary condition-save" disabled={busy} type="submit">{busy ? "Saving…" : saved ? "Update today’s check-in" : "Save today’s check-in"}</button>
        </form>

        <aside className="phase-stack condition-stack">
          <article className="card coaching-card condition-coach-card">
            <p className="condition-card-label"><ConditionIcon name="spark" size={22} /> AI Coach</p>
            <div className="condition-coach-message"><ConditionIcon name="spark" size={25} /><p>{coaching?.summary ?? "Save today’s check-in, then generate a recommendation matched to your capacity."}</p></div>
            <button className="button secondary condition-coach-action" disabled={!saved || coachingBusy || Boolean(coaching)} onClick={generateCoaching} type="button"><ConditionIcon name="spark" size={18} /> {coachingBusy ? "Generating…" : coaching ? "Recommendation saved" : "Generate today’s coaching"}</button>
          </article>

          <article className="card next-step-card condition-next-card">
            <p className="condition-card-label"><ConditionIcon name="target" size={21} /> Next step</p>
            <h2>Turn capacity into a realistic plan</h2>
            <p className="muted">Daily planning uses the deterministic workload adjustment calculated from this check-in and recent execution history.</p>
            <Link className="button primary" href="/today"><ConditionIcon name="calendar" size={18} /> Open today’s plan</Link>
          </article>
        </aside>
      </div>
    </section>
  );
}
