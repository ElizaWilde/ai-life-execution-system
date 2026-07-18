"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { api, DailyTask, StudySession } from "../../lib/api";
import {
  AppSettings,
  defaultSettings,
  loadAppSettings,
  saveAppSettings,
  useAppSettings,
} from "../../lib/settings";

type TimerPreferenceKey = "focusMinutes" | "shortBreak" | "longBreak" | "cycleCount";

function TimerIcon({ name }: { name: "clock" | "cycles" }) {
  return (
    <svg aria-hidden="true" fill="none" height="18" viewBox="0 0 24 24" width="18">
      {name === "clock" ? (
        <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>
      ) : (
        <><path d="M20 7h-5V2" /><path d="M19 5a8 8 0 0 0-13.6 2M4 17h5v5" /><path d="M5 19a8 8 0 0 0 13.6-2" /></>
      )}
    </svg>
  );
}

export default function TimerPage() {
  const settings = useAppSettings();
  const targetMinutes = Math.max(1, Number(settings.focusMinutes) || 25);
  const targetSeconds = targetMinutes * 60;
  const [tasks, setTasks] = useState<DailyTask[]>([]);
  const [sessions, setSessions] = useState<StudySession[]>([]);
  const [selectedTaskId, setSelectedTaskId] = useState("");
  const [subject, setSubject] = useState("");
  const [notes, setNotes] = useState("");
  const [running, setRunning] = useState<StudySession | null>(null);
  const [now, setNow] = useState(Date.now());
  const [error, setError] = useState("");
  const [preferenceMessage, setPreferenceMessage] = useState("");
  const settingsSyncQueue = useRef<Promise<void>>(Promise.resolve());

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

  function syncTimerPreferences() {
    settingsSyncQueue.current = settingsSyncQueue.current
      .catch(() => undefined)
      .then(async () => {
        try {
          const latest = loadAppSettings();
          const remote = await api.getAppSettings();
          const { id, user_id, created_at, updated_at, ...payload } = remote;
          await api.updateAppSettings({
            ...payload,
            focus_minutes: Number(latest.focusMinutes) as 25 | 45 | 60,
            short_break_minutes: Number(latest.shortBreak) as 5 | 10,
            long_break_minutes: Number(latest.longBreak) as 15 | 30,
            cycle_count: Math.min(12, Math.max(1, Number(latest.cycleCount) || 4)),
          });
          setPreferenceMessage("Timer preferences saved.");
        } catch {
          setPreferenceMessage("Saved on this device. Cloud sync is currently unavailable.");
        }
      });
  }

  function updateTimerPreference(key: TimerPreferenceKey, value: string) {
    const next: AppSettings = { ...loadAppSettings(), [key]: value };
    saveAppSettings(next);
    setPreferenceMessage("Saving timer preferences…");
    syncTimerPreferences();
  }

  function resetTimerPreferences() {
    const next: AppSettings = {
      ...loadAppSettings(),
      focusMinutes: defaultSettings.focusMinutes,
      shortBreak: defaultSettings.shortBreak,
      longBreak: defaultSettings.longBreak,
      cycleCount: defaultSettings.cycleCount,
    };
    saveAppSettings(next);
    setPreferenceMessage("Restoring default timer preferences…");
    syncTimerPreferences();
  }

  async function startSession() {
    setError("");
    try {
      const selectedTask = tasks.find((task) => String(task.id) === selectedTaskId);
      const session = await api.startSession({
        daily_task_id: selectedTaskId ? Number(selectedTaskId) : null,
        subject: subject.trim() || selectedTask?.title || "Focus session",
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
      await api.finishSession({ session_id: running.id, notes: notes || null });
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
    <section className="page timer-workspace-page">
      <header className="page-header timer-workspace-header">
        <div>
          <p className="eyebrow">Timer</p>
          <h1>Study session</h1>
          <p className="muted">Start a {targetMinutes}-minute focus session. Paired to a daily task.</p>
          <p className="muted">Breaks: {settings.shortBreak} min short · {settings.longBreak} min long</p>
        </div>
      </header>

      {error ? <div className="error">{error}</div> : null}

      <div className="timer-workspace-grid">
        <div className="timer-workspace-left">
          <article className="card timer-session-card">
            <h2>{running ? "Running session" : "Start session"}</h2>
            <p className="stat">{String(minutes).padStart(2, "0")}:{String(seconds).padStart(2, "0")}</p>
            <p className="muted timer-session-meta">Timer · {targetMinutes}:00 · {selectedTaskId ? tasks.find((task) => String(task.id) === selectedTaskId)?.title : "No task set"}</p>
            <div className="form timer-session-form">
              <label className="field"><span>Task</span><select className="input" disabled={Boolean(running)} value={selectedTaskId} onChange={(event) => setSelectedTaskId(event.target.value)}><option value="">No task set</option>{tasks.map((task) => <option key={task.id} value={task.id}>{task.title}</option>)}</select></label>
              <label className="field"><span>Subject</span><input className="input" disabled={Boolean(running)} placeholder="Optional subject" value={subject} onChange={(event) => setSubject(event.target.value)} /></label>
              {running ? <label className="field"><span>Finish notes</span><textarea className="input" rows={3} value={notes} onChange={(event) => setNotes(event.target.value)} /></label> : null}
            </div>
            <div className="actions timer-session-actions">{!running ? <button className="button primary" onClick={startSession}>Start {targetMinutes} min session</button> : <button className="button danger" onClick={finishSession}>Finish session</button>}</div>
            {running && elapsedSeconds >= targetSeconds ? <p className="success">Focus target reached. Finish when you are ready.</p> : null}
          </article>

          <article className="card timer-preferences-card">
            <h2>Timer preferences</h2>
            <div className="timer-preference-grid">
              <label><span>Default focus session</span><i><TimerIcon name="clock" /><select disabled={Boolean(running)} value={settings.focusMinutes} onChange={(event) => updateTimerPreference("focusMinutes", event.target.value)}><option value="25">25 min</option><option value="45">45 min</option><option value="60">60 min</option></select></i></label>
              <label><span>Short break</span><i><TimerIcon name="clock" /><select disabled={Boolean(running)} value={settings.shortBreak} onChange={(event) => updateTimerPreference("shortBreak", event.target.value)}><option value="5">5 min</option><option value="10">10 min</option></select></i></label>
              <label><span>Long break</span><i><TimerIcon name="clock" /><select disabled={Boolean(running)} value={settings.longBreak} onChange={(event) => updateTimerPreference("longBreak", event.target.value)}><option value="15">15 min</option><option value="30">30 min</option></select></i></label>
              <label><span>Number of cycles</span><i><TimerIcon name="cycles" /><select disabled={Boolean(running)} value={settings.cycleCount} onChange={(event) => updateTimerPreference("cycleCount", event.target.value)}>{Array.from({ length: 12 }, (_, index) => index + 1).map((cycles) => <option key={cycles} value={cycles}>{cycles} {cycles === 1 ? "cycle" : "cycles"}</option>)}</select></i></label>
            </div>
            <footer><span>These settings will be used for new sessions.{preferenceMessage ? ` ${preferenceMessage}` : ""}</span><button disabled={Boolean(running)} onClick={resetTimerPreferences} type="button">Reset to defaults</button></footer>
          </article>
        </div>

        <article className="card timer-sessions-card">
          <h2>Today’s sessions</h2>
          <div className="list">
            {sessions.length === 0 ? <p className="muted">No sessions today.</p> : null}
            {sessions.map((session) => <article className="item" key={session.id}><div className="item-row"><strong>{session.subject}</strong><span className={`badge ${session.status === "completed" ? "done" : ""}`}>{session.status}</span></div><p className="muted">{session.duration_minutes ?? 0} min{session.notes ? ` · ${session.notes}` : ""}</p></article>)}
          </div>
        </article>
      </div>
    </section>
  );
}
