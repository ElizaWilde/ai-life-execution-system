"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import {
  api,
  MilestoneStatus,
  PhaseMilestone,
  PhasePlan,
  PhaseStatus,
  Priority,
  WeekDashboard,
  WeeklyGoal,
  WeeklyPlanPreview,
} from "../../lib/api";

type PlanIconName = "spark" | "calendar" | "chart" | "check" | "trash" | "arrow" | "plus" | "target" | "flag" | "clock" | "people" | "edit" | "more" | "grip";

function PlanIcon({ name, size = 17 }: { name: PlanIconName; size?: number }) {
  const paths: Record<PlanIconName, React.ReactNode> = {
    spark: <path d="m12 2 1.6 5.1a5 5 0 0 0 3.3 3.3L22 12l-5.1 1.6a5 5 0 0 0-3.3 3.3L12 22l-1.6-5.1a5 5 0 0 0-3.3-3.3L2 12l5.1-1.6a5 5 0 0 0 3.3-3.3L12 2Z" />,
    calendar: <><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M16 3v4M8 3v4M3 10h18" /></>,
    chart: <><path d="M4 19V9M10 19V5M16 19v-7M22 19H2" /></>,
    check: <><circle cx="12" cy="12" r="9" /><path d="m8 12 2.5 2.5L16 9" /></>,
    trash: <><path d="M4 7h16M9 7V4h6v3M7 7l1 14h8l1-14M10 11v6M14 11v6" /></>,
    arrow: <path d="M5 12h14M15 8l4 4-4 4" />,
    plus: <path d="M12 5v14M5 12h14" />,
    target: <><circle cx="12" cy="12" r="9" /><circle cx="12" cy="12" r="4" /><path d="M12 8V5" /></>,
    flag: <><path d="M5 21V4" /><path d="M5 5h11l-2 4 2 4H5" /></>,
    clock: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
    people: <><path d="M16 20v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" /><path d="M22 20v-2a4 4 0 0 0-3-3.7M16 3.3a4 4 0 0 1 0 7.4" /></>,
    edit: <><path d="M12 20h9" /><path d="m16.5 3.5 4 4L8 20H4v-4Z" /></>,
    more: <><circle cx="5" cy="12" r="1" fill="currentColor" stroke="none" /><circle cx="12" cy="12" r="1" fill="currentColor" stroke="none" /><circle cx="19" cy="12" r="1" fill="currentColor" stroke="none" /></>,
    grip: <><circle cx="8" cy="6" r="1" fill="currentColor" stroke="none" /><circle cx="16" cy="6" r="1" fill="currentColor" stroke="none" /><circle cx="8" cy="12" r="1" fill="currentColor" stroke="none" /><circle cx="16" cy="12" r="1" fill="currentColor" stroke="none" /><circle cx="8" cy="18" r="1" fill="currentColor" stroke="none" /><circle cx="16" cy="18" r="1" fill="currentColor" stroke="none" /></>,
  };
  return <svg aria-hidden="true" className="plan-icon" fill="none" height={size} viewBox="0 0 24 24" width={size}>{paths[name]}</svg>;
}

function localToday() {
  const now = new Date();
  return new Date(now.getTime() - now.getTimezoneOffset() * 60_000).toISOString().slice(0, 10);
}

// Keep all week-scoped requests anchored to the week selected in the UI.
function dateAt(value: string) {
  return new Date(`${value}T00:00:00`);
}

function addDays(value: string, days: number) {
  const [year, month, day] = value.split("-").map(Number);
  const date = new Date(Date.UTC(year, month - 1, day));
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

function formatHours(minutes: number) {
  const hours = minutes / 60;
  return `${hours % 1 === 0 ? hours.toFixed(0) : hours.toFixed(1)}h`;
}

function weekStartOf(value: string) {
  const date = dateAt(value);
  const offset = (date.getDay() + 6) % 7;
  return addDays(value, -offset);
}

function weeklyPriorityWeight(goal: WeeklyGoal) {
  const priorityMultiplier = { high: 3, medium: 2, low: 1 }[goal.priority];
  const estimatedMinutes = goal.target_minutes && goal.target_minutes > 0 ? goal.target_minutes : 60;
  return estimatedMinutes * priorityMultiplier;
}

function isoWeek(value: string) {
  const date = dateAt(value);
  const utc = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
  utc.setUTCDate(utc.getUTCDate() + 4 - (utc.getUTCDay() || 7));
  const yearStart = new Date(Date.UTC(utc.getUTCFullYear(), 0, 1));
  return Math.ceil((((utc.getTime() - yearStart.getTime()) / 86_400_000) + 1) / 7);
}

function formatPhaseDate(value: string) {
  return dateAt(value).toLocaleDateString("en", { month: "short", day: "numeric", year: "numeric" });
}

function formatPhaseRange(phase: PhasePlan) {
  const start = dateAt(phase.start_date);
  const end = dateAt(phase.end_date);
  const sameYear = start.getFullYear() === end.getFullYear();
  return `${start.toLocaleDateString("en", { month: "short", day: "numeric", year: sameYear ? undefined : "numeric" })} – ${end.toLocaleDateString("en", { month: "short", day: "numeric", year: "numeric" })}`;
}

function phaseStatusLabel(status: PhaseStatus) {
  return status === "active" ? "On Track" : status[0].toUpperCase() + status.slice(1);
}

function milestoneStatusLabel(status: MilestoneStatus) {
  return status.split("_").map((word) => word[0].toUpperCase() + word.slice(1)).join(" ");
}

type PhaseDraft = {
  title: string;
  description: string;
  start_date: string;
  end_date: string;
  status: PhaseStatus;
  progress: string;
  estimated_focus_hours: string;
  notes: string;
};

type MilestoneDraft = {
  title: string;
  description: string;
  due_date: string;
  status: MilestoneStatus;
  progress: string;
};

function emptyPhaseDraft(): PhaseDraft {
  const today = localToday();
  return {
    title: "",
    description: "",
    start_date: today,
    end_date: addDays(today, 90),
    status: "planning",
    progress: "0",
    estimated_focus_hours: "0",
    notes: "",
  };
}

function emptyMilestoneDraft(): MilestoneDraft {
  return {
    title: "",
    description: "",
    due_date: "",
    status: "not_started",
    progress: "0",
  };
}

export default function WeeklyPlanPage() {
  const [weekAnchor, setWeekAnchor] = useState(localToday());
  const [goals, setGoals] = useState<WeeklyGoal[]>([]);
  const [week, setWeek] = useState<WeekDashboard | null>(null);
  const [weeklyPreview, setWeeklyPreview] = useState<WeeklyPlanPreview | null>(null);
  const [intendedHours, setIntendedHours] = useState("20");
  const [activeTab, setActiveTab] = useState<"weekly" | "phase">("weekly");
  const [showTaskForm, setShowTaskForm] = useState(false);
  const [editingTaskId, setEditingTaskId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [phaseFilter, setPhaseFilter] = useState<"active" | "all">("active");
  const [phases, setPhases] = useState<PhasePlan[]>([]);
  const [selectedPhaseId, setSelectedPhaseId] = useState<number | null>(null);
  const [phaseDetailTab, setPhaseDetailTab] = useState<"milestones" | "tasks" | "focus" | "notes">("milestones");
  const [phaseLoading, setPhaseLoading] = useState(false);
  const [phaseBusy, setPhaseBusy] = useState(false);
  const [showPhaseForm, setShowPhaseForm] = useState(false);
  const [editingPhaseId, setEditingPhaseId] = useState<number | null>(null);
  const [phaseDraft, setPhaseDraft] = useState<PhaseDraft>(emptyPhaseDraft);
  const [showMilestoneForm, setShowMilestoneForm] = useState(false);
  const [editingMilestoneId, setEditingMilestoneId] = useState<number | null>(null);
  const [milestoneDraft, setMilestoneDraft] = useState<MilestoneDraft>(emptyMilestoneDraft);
  const [notesDraft, setNotesDraft] = useState("");
  const [focusHoursDraft, setFocusHoursDraft] = useState("0");

  const [taskTitle, setTaskTitle] = useState("");
  const [taskHours, setTaskHours] = useState("1");
  const [taskPriority, setTaskPriority] = useState<Priority>("high");

  async function loadPlan(anchor: string) {
    setLoading(true);
    setError("");
    try {
      const selectedWeekStart = weekStartOf(anchor);
      const [goalData, weekData, previewData] = await Promise.all([
        api.getGoalsForWeek(anchor),
        api.getWeekDashboard(anchor),
        api.getLatestWeeklyPlanPreview(selectedWeekStart),
      ]);
      setGoals(goalData);
      setWeek(weekData);
      setWeeklyPreview(previewData);
      if (previewData) setIntendedHours(String(previewData.intended_minutes / 60));
      else if (goalData.some((goal) => goal.target_minutes)) {
        setIntendedHours(String(goalData.reduce((sum, goal) => sum + (goal.target_minutes ?? 0), 0) / 60));
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Failed to load weekly plan");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadPlan(weekAnchor);
  }, []);

  useEffect(() => {
    if (activeTab === "phase") void loadPhases();
  }, [activeTab]);

  useEffect(() => {
    const selected = phases.find((phase) => phase.id === selectedPhaseId);
    if (selected) {
      setNotesDraft(selected.notes ?? "");
      setFocusHoursDraft(String(selected.estimated_focus_minutes / 60));
    }
  }, [phases, selectedPhaseId]);

  const priorities = [...goals].sort((left, right) =>
    Number(left.status === "completed") - Number(right.status === "completed") ||
    ({ high: 3, medium: 2, low: 1 }[right.priority] - { high: 3, medium: 2, low: 1 }[left.priority]) ||
    left.id - right.id,
  );
  const highPriorityCount = priorities.filter((goal) => goal.priority === "high" && goal.status !== "completed").length;
  const plannedMinutes = goals.reduce((sum, goal) => sum + (goal.target_minutes ?? 0), 0);
  const targetMinutes = goals.reduce((sum, goal) => sum + (goal.target_minutes ?? 0), 0);
  const completedPriorities = goals.filter((goal) => goal.status === "completed").length;
  const totalPriorityWeight = goals.reduce((sum, goal) => sum + weeklyPriorityWeight(goal), 0);
  const completedPriorityWeight = goals
    .filter((goal) => goal.status === "completed")
    .reduce((sum, goal) => sum + weeklyPriorityWeight(goal), 0);
  const completion = totalPriorityWeight ? Math.round((completedPriorityWeight / totalPriorityWeight) * 100) : 0;
  const planVsGoal = targetMinutes ? Math.round((plannedMinutes / targetMinutes) * 100) : 0;
  const weekLabel = week
    ? `${dateAt(week.week_start).toLocaleDateString("en", { month: "short", day: "numeric" })} – ${dateAt(week.week_end).toLocaleDateString("en", { month: "short", day: "numeric", year: "numeric" })} (Week ${isoWeek(week.week_start)})`
    : "Loading week…";
  const suggestion = highPriorityCount > 3
    ? `You have ${highPriorityCount} high-impact priorities. Complete the first ${Math.min(3, highPriorityCount)} before adding more work.`
    : plannedMinutes > targetMinutes && targetMinutes > 0
      ? `This plan is ${formatHours(plannedMinutes - targetMinutes)} above your weekly goal. Move one lower-impact item into the buffer.`
      : "The week has room for focused work. Protect your strongest mornings for the first priorities.";
  const selectedPhase = phases.find((phase) => phase.id === selectedPhaseId) ?? null;
  const visiblePhases = phaseFilter === "active"
    ? phases.filter((phase) => phase.status === "active")
    : phases;

  async function loadPhases(preferredId?: number) {
    setPhaseLoading(true);
    setError("");
    try {
      const data = await api.getPhases();
      setPhases(data);
      setSelectedPhaseId((current) => {
        const nextId = preferredId ?? current;
        return data.some((phase) => phase.id === nextId) ? nextId : (data[0]?.id ?? null);
      });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Failed to load phases");
    } finally {
      setPhaseLoading(false);
    }
  }

  function openNewPhase() {
    setEditingPhaseId(null);
    setPhaseDraft(emptyPhaseDraft());
    setShowPhaseForm(true);
  }

  function openEditPhase(phase: PhasePlan) {
    setEditingPhaseId(phase.id);
    setPhaseDraft({
      title: phase.title,
      description: phase.description ?? "",
      start_date: phase.start_date,
      end_date: phase.end_date,
      status: phase.status,
      progress: String(phase.progress),
      estimated_focus_hours: String(phase.estimated_focus_minutes / 60),
      notes: phase.notes ?? "",
    });
    setShowPhaseForm(true);
  }

  async function savePhase(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPhaseBusy(true);
    setError("");
    try {
      const payload = {
        title: phaseDraft.title.trim(),
        description: phaseDraft.description.trim() || null,
        start_date: phaseDraft.start_date,
        end_date: phaseDraft.end_date,
        status: phaseDraft.status,
        progress: Number(phaseDraft.progress),
        estimated_focus_minutes: Math.round(Number(phaseDraft.estimated_focus_hours) * 60),
        notes: phaseDraft.notes.trim() || null,
      };
      const saved = editingPhaseId
        ? await api.updatePhase(editingPhaseId, payload)
        : await api.createPhase(payload);
      setShowPhaseForm(false);
      setPhaseFilter(saved.status === "active" ? "active" : "all");
      setMessage(editingPhaseId ? "Phase updated." : "Phase created.");
      await loadPhases(saved.id);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Failed to save phase");
    } finally {
      setPhaseBusy(false);
    }
  }

  async function deleteSelectedPhase() {
    if (!selectedPhase || !window.confirm(`Delete "${selectedPhase.title}" and all of its milestones?`)) return;
    setPhaseBusy(true);
    try {
      await api.deletePhase(selectedPhase.id);
      setMessage("Phase deleted.");
      await loadPhases();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Failed to delete phase");
    } finally {
      setPhaseBusy(false);
    }
  }

  function openNewMilestone() {
    setEditingMilestoneId(null);
    setMilestoneDraft(emptyMilestoneDraft());
    setShowMilestoneForm(true);
  }

  function openEditMilestone(milestone: PhaseMilestone) {
    setEditingMilestoneId(milestone.id);
    setMilestoneDraft({
      title: milestone.title,
      description: milestone.description ?? "",
      due_date: milestone.due_date ?? "",
      status: milestone.status,
      progress: String(milestone.progress),
    });
    setShowMilestoneForm(true);
  }

  async function saveMilestone(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedPhase) return;
    setPhaseBusy(true);
    setError("");
    try {
      const payload = {
        title: milestoneDraft.title.trim(),
        description: milestoneDraft.description.trim() || null,
        due_date: milestoneDraft.due_date || null,
        status: milestoneDraft.status,
        progress: Number(milestoneDraft.progress),
      };
      if (editingMilestoneId) {
        await api.updateMilestone(selectedPhase.id, editingMilestoneId, payload);
      } else {
        await api.createMilestone(selectedPhase.id, payload);
      }
      setShowMilestoneForm(false);
      setMessage(editingMilestoneId ? "Milestone updated." : "Milestone added.");
      await loadPhases(selectedPhase.id);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Failed to save milestone");
    } finally {
      setPhaseBusy(false);
    }
  }

  async function deleteMilestone(milestone: PhaseMilestone) {
    if (!selectedPhase || !window.confirm(`Delete "${milestone.title}"?`)) return;
    setPhaseBusy(true);
    try {
      await api.deleteMilestone(selectedPhase.id, milestone.id);
      setMessage("Milestone deleted.");
      await loadPhases(selectedPhase.id);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Failed to delete milestone");
    } finally {
      setPhaseBusy(false);
    }
  }

  async function setMilestoneStatus(milestone: PhaseMilestone, status: MilestoneStatus) {
    if (!selectedPhase) return;
    setPhaseBusy(true);
    try {
      await api.updateMilestone(selectedPhase.id, milestone.id, { status });
      await loadPhases(selectedPhase.id);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Failed to update milestone");
    } finally {
      setPhaseBusy(false);
    }
  }

  async function savePhaseNotes() {
    if (!selectedPhase) return;
    setPhaseBusy(true);
    try {
      await api.updatePhase(selectedPhase.id, { notes: notesDraft.trim() || null });
      setMessage("Phase notes saved.");
      await loadPhases(selectedPhase.id);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Failed to save notes");
    } finally {
      setPhaseBusy(false);
    }
  }

  async function saveFocusEstimate() {
    if (!selectedPhase) return;
    setPhaseBusy(true);
    try {
      await api.updatePhase(selectedPhase.id, {
        estimated_focus_minutes: Math.round(Number(focusHoursDraft) * 60),
      });
      setMessage("Focus-time estimate saved.");
      await loadPhases(selectedPhase.id);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Failed to save focus time");
    } finally {
      setPhaseBusy(false);
    }
  }

  async function selectWeek(anchor: string) {
    setMessage("");
    setWeekAnchor(anchor);
    await loadPlan(anchor);
  }

  async function moveWeek(offset: number) {
    await selectWeek(addDays(week?.week_start ?? weekAnchor, offset * 7));
  }

  async function createTask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!week) return;
    setBusy(true);
    setError("");
    try {
      const goalData = {
        title: taskTitle,
        target_minutes: taskHours ? Math.round(Number(taskHours) * 60) : null,
        priority: taskPriority,
      };
      if (editingTaskId) {
        await api.updateGoal(editingTaskId, goalData);
      } else {
        await api.createGoal({
          ...goalData,
          week_start: week.week_start,
          week_end: week.week_end,
        });
      }
      setTaskTitle("");
      setTaskHours("1");
      setTaskPriority("high");
      setEditingTaskId(null);
      setShowTaskForm(false);
      setMessage(editingTaskId ? "Priority updated." : "Priority added to the weekly plan.");
      await loadPlan(weekAnchor);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Failed to save priority");
    } finally {
      setBusy(false);
    }
  }

  function editTask(goal: WeeklyGoal) {
    setEditingTaskId(goal.id);
    setTaskTitle(goal.title);
    setTaskHours(goal.target_minutes ? String(goal.target_minutes / 60) : "1");
    setTaskPriority(goal.priority);
    setShowTaskForm(true);
  }

  function cancelTaskForm() {
    setEditingTaskId(null);
    setTaskTitle("");
    setTaskHours("1");
    setTaskPriority("high");
    setShowTaskForm(false);
  }

  async function toggleTaskCompleted(goal: WeeklyGoal) {
    setBusy(true);
    try {
      const completing = goal.status !== "completed";
      await api.updateGoal(goal.id, { status: completing ? "completed" : "active" });
      setMessage(completing ? `Completed: ${goal.title}` : `Reopened: ${goal.title}`);
      await loadPlan(weekAnchor);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Failed to update priority");
    } finally {
      setBusy(false);
    }
  }

  async function toggleSelectedPhaseCompleted() {
    if (!selectedPhase) return;
    const completing = selectedPhase.status !== "completed";
    setPhaseBusy(true);
    setError("");
    try {
      await api.updatePhase(selectedPhase.id, {
        status: completing ? "completed" : "active",
        ...(completing ? { progress: 100 } : {}),
      });
      setMessage(completing ? `Completed: ${selectedPhase.title}` : `Reopened: ${selectedPhase.title}`);
      if (completing) setPhaseFilter("all");
      await loadPhases(selectedPhase.id);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Failed to update phase");
    } finally {
      setPhaseBusy(false);
    }
  }

  async function deleteTask(goal: WeeklyGoal) {
    if (!window.confirm(`Delete "${goal.title}" from this weekly plan?`)) return;
    setBusy(true);
    setError("");
    try {
      await api.updateGoal(goal.id, { status: "cancelled" });
      setMessage(`Deleted: ${goal.title}`);
      await loadPlan(weekAnchor);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Failed to delete priority");
    } finally {
      setBusy(false);
    }
  }

  async function generateWeeklyPreview() {
    if (!week) return;
    setBusy(true);
    setError("");
    try {
      const preview = await api.createWeeklyPlanPreview({
        week_start: week.week_start,
        intended_minutes: Math.round(Number(intendedHours) * 60),
      });
      setWeeklyPreview(preview);
      setMessage(`Adaptive weekly preview created for ${formatHours(preview.recommended_minutes)}. Confirm it to update priority estimates.`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Failed to generate adaptive weekly plan");
    } finally {
      setBusy(false);
    }
  }

  async function confirmWeeklyPreview() {
    if (!weeklyPreview) return;
    setBusy(true);
    setError("");
    try {
      await api.confirmWeeklyPlanPreview(weeklyPreview.id);
      setMessage("Adaptive weekly plan confirmed and priority estimates updated.");
      await loadPlan(weekAnchor);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Failed to confirm weekly plan");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="plans-page weekly-reference-page">
      <header className="plans-header">
        <div>
          <h1>{activeTab === "phase" ? "Phase Plan" : "Weekly Plan"}</h1>
          <p>{activeTab === "phase" ? "Break down long-term goals into phases and milestones." : "Stay aligned with your goals. Adjust on the day, guided by AI."}</p>
        </div>
        <div className="plans-header-actions">
          <Link aria-label="Open calendar" href="/today"><PlanIcon name="calendar" size={20} /></Link>
          <Link className="plans-coach-button" href="/check-in"><PlanIcon name="spark" /> Ask my coach <span>⌄</span></Link>
        </div>
      </header>

      <div className="plans-tabs" role="tablist">
        <button aria-selected={activeTab === "weekly"} className={activeTab === "weekly" ? "active" : ""} onClick={() => setActiveTab("weekly")} role="tab" type="button">Weekly Plan</button>
        <button aria-selected={activeTab === "phase"} className={activeTab === "phase" ? "active" : ""} onClick={() => setActiveTab("phase")} role="tab" type="button">Phase Plan</button>
      </div>

      {error ? <div className="error plans-feedback">{error}</div> : null}
      {message ? <div className="success plans-feedback">{message}</div> : null}

      {activeTab === "phase" ? (
        <main className="phase-plan-content">
          <div className="phase-toolbar">
            <div className="phase-filter" role="group" aria-label="Filter phases">
              <button className={phaseFilter === "active" ? "active" : ""} onClick={() => setPhaseFilter("active")} type="button">Active Phases</button>
              <button className={phaseFilter === "all" ? "active" : ""} onClick={() => setPhaseFilter("all")} type="button">All Phases</button>
            </div>
            <button className="new-phase-button" onClick={openNewPhase} type="button"><PlanIcon name="plus" size={14} /> New Phase</button>
          </div>

          <section className="phase-card-grid" aria-label="Phase summaries">
            {phaseLoading && phases.length === 0 ? <p className="phase-loading-message">Loading phases…</p> : null}
            {!phaseLoading && visiblePhases.length === 0 ? (
              <div className="phase-zero-state">
                <PlanIcon name="flag" size={24} />
                <strong>{phaseFilter === "active" && phases.length ? "No active phases" : "Create your first phase"}</strong>
                <p>Turn a long-term goal into a dated plan with measurable milestones.</p>
                <button onClick={openNewPhase} type="button"><PlanIcon name="plus" size={14} /> New Phase</button>
              </div>
            ) : null}
            {visiblePhases.map((phase) => (
              <button className={`phase-summary-card ${selectedPhaseId === phase.id ? "selected" : ""} ${phase.status === "completed" ? "completed" : ""}`} key={phase.id} onClick={() => setSelectedPhaseId(phase.id)} type="button">
                <div className="phase-card-title"><i /><strong>{phase.title}</strong></div>
                <div className="phase-card-meta"><span>{formatPhaseRange(phase)}</span><b className={phase.status === "active" ? "on-track" : "planning"}>{phaseStatusLabel(phase.status)}</b></div>
                <div className="phase-progress"><span><i style={{ width: `${phase.progress}%` }} /></span><strong>{phase.progress}%</strong></div>
                <div className="phase-card-stats">
                  <span><PlanIcon name="flag" size={14} /> Milestones <b><PlanIcon name="people" size={13} /> {phase.milestones.filter((milestone) => milestone.status === "completed").length} / {phase.milestones.length}</b></span>
                  <span><PlanIcon name="clock" size={14} /> Est. Focus Time <b><PlanIcon name="clock" size={13} /> {formatHours(phase.estimated_focus_minutes)}</b></span>
                </div>
              </button>
            ))}
          </section>

          {selectedPhase ? <section className="phase-detail-card">
            <header className="phase-detail-header">
              <div className="phase-detail-title">
                <button aria-label={selectedPhase.status === "completed" ? `Reopen ${selectedPhase.title}` : `Complete ${selectedPhase.title}`} className={`plan-completion-toggle ${selectedPhase.status === "completed" ? "completed" : ""}`} disabled={phaseBusy} onClick={toggleSelectedPhaseCompleted} title={selectedPhase.status === "completed" ? "Reopen phase" : "Mark phase complete"} type="button">{selectedPhase.status === "completed" ? <PlanIcon name="check" size={12} /> : null}</button>
                <h2>{selectedPhase.title}</h2>
                <button aria-label="Edit phase" onClick={() => openEditPhase(selectedPhase)} type="button"><PlanIcon name="edit" size={16} /></button>
                <span>{formatPhaseRange(selectedPhase)}</span>
                <b className={selectedPhase.status === "active" ? "on-track" : "planning"}>{phaseStatusLabel(selectedPhase.status)}</b>
              </div>
              <div className="phase-detail-progress">
                <span>Progress</span>
                <div><i style={{ width: `${selectedPhase.progress}%` }} /></div>
                <strong>{selectedPhase.progress}%</strong>
              </div>
              <button aria-label="Delete phase" className="phase-more-button" disabled={phaseBusy} onClick={deleteSelectedPhase} title="Delete phase" type="button"><PlanIcon name="trash" size={16} /></button>
            </header>

            <div className="phase-detail-tabs" role="tablist">
              {([
                ["milestones", "Milestones"],
                ["tasks", "Tasks Overview"],
                ["focus", "Focus Time"],
                ["notes", "Notes"],
              ] as const).map(([tab, label]) => (
                <button aria-selected={phaseDetailTab === tab} className={phaseDetailTab === tab ? "active" : ""} key={tab} onClick={() => setPhaseDetailTab(tab)} role="tab" type="button">{label}</button>
              ))}
            </div>

            {phaseDetailTab === "milestones" ? (
              <div className="milestone-table-wrap">
                <div className="milestone-table-head">
                  <span>Milestone</span><span>Due Date</span><span>Progress</span><span>Status</span>
                </div>
                <div className="milestone-list">
                  {selectedPhase.milestones.length === 0 ? <p className="milestone-empty">No milestones yet. Add the first outcome for this phase.</p> : null}
                  {selectedPhase.milestones.map((milestone) => (
                    <div className={`milestone-row ${milestone.status === "completed" ? "completed" : ""}`} key={milestone.id}>
                      <button aria-label={milestone.status === "completed" ? `Reopen ${milestone.title}` : `Complete ${milestone.title}`} className={`plan-completion-toggle milestone-completion-toggle ${milestone.status === "completed" ? "completed" : ""}`} disabled={phaseBusy} onClick={() => setMilestoneStatus(milestone, milestone.status === "completed" ? "in_progress" : "completed")} title={milestone.status === "completed" ? "Reopen milestone" : "Mark milestone complete"} type="button">{milestone.status === "completed" ? <PlanIcon name="check" size={12} /> : null}</button>
                      <div className="milestone-name"><strong>{milestone.title}</strong><small>{milestone.description || "No description"}</small></div>
                      <time>{milestone.due_date ? formatPhaseDate(milestone.due_date) : "Not scheduled"}</time>
                      <div className="milestone-progress"><span><i style={{ width: `${milestone.progress}%` }} /></span><b>{milestone.progress}%</b></div>
                      <div className="milestone-status-cell">
                        <span className={`milestone-status ${milestone.status.replaceAll("_", "-")}`}>{milestoneStatusLabel(milestone.status)}</span>
                        <button aria-label={`Edit ${milestone.title}`} disabled={phaseBusy} onClick={() => openEditMilestone(milestone)} title="Edit milestone" type="button"><PlanIcon name="edit" size={14} /></button>
                        <button aria-label={`Delete ${milestone.title}`} disabled={phaseBusy} onClick={() => deleteMilestone(milestone)} title="Delete milestone" type="button"><PlanIcon name="trash" size={14} /></button>
                      </div>
                    </div>
                  ))}
                </div>
                <button className="add-milestone-button" onClick={openNewMilestone} type="button"><PlanIcon name="plus" size={14} /> Add Milestone</button>
              </div>
            ) : phaseDetailTab === "tasks" ? (
              <div className="phase-functional-panel">
                <div className="phase-panel-heading"><div><h3>Milestone execution</h3><p>Update each outcome as work moves forward.</p></div><button onClick={openNewMilestone} type="button"><PlanIcon name="plus" size={14} /> Add task</button></div>
                <div className="phase-task-list">
                  {selectedPhase.milestones.map((milestone) => (
                    <div className="phase-task-row" key={milestone.id}>
                      <button aria-label={`Mark ${milestone.title} complete`} className={milestone.status === "completed" ? "complete" : ""} disabled={phaseBusy} onClick={() => setMilestoneStatus(milestone, milestone.status === "completed" ? "in_progress" : "completed")} type="button"><PlanIcon name="check" size={15} /></button>
                      <span><strong>{milestone.title}</strong><small>{milestone.due_date ? `Due ${formatPhaseDate(milestone.due_date)}` : "No due date"}</small></span>
                      <select aria-label={`Status for ${milestone.title}`} disabled={phaseBusy} onChange={(event) => setMilestoneStatus(milestone, event.target.value as MilestoneStatus)} value={milestone.status}>
                        <option value="not_started">Not Started</option>
                        <option value="in_progress">In Progress</option>
                        <option value="completed">Completed</option>
                      </select>
                    </div>
                  ))}
                  {selectedPhase.milestones.length === 0 ? <p className="milestone-empty">Add a milestone to start tracking execution.</p> : null}
                </div>
              </div>
            ) : phaseDetailTab === "focus" ? (
              <div className="phase-functional-panel">
                <div className="phase-panel-heading"><div><h3>Focus-time estimate</h3><p>Set the total deep-work time you expect this phase to need.</p></div></div>
                <div className="phase-focus-editor">
                  <label><span>Estimated hours</span><input min="0" onChange={(event) => setFocusHoursDraft(event.target.value)} step="0.5" type="number" value={focusHoursDraft} /></label>
                  <div><strong>{formatHours(selectedPhase.estimated_focus_minutes)}</strong><span>currently planned</span></div>
                  <button disabled={phaseBusy} onClick={saveFocusEstimate} type="button">Save estimate</button>
                </div>
              </div>
            ) : (
              <div className="phase-functional-panel">
                <div className="phase-panel-heading"><div><h3>Phase notes</h3><p>Capture decisions, context, and reminders for this phase.</p></div></div>
                <textarea aria-label="Phase notes" onChange={(event) => setNotesDraft(event.target.value)} placeholder="Add notes for this phase…" rows={7} value={notesDraft} />
                <button className="phase-save-button" disabled={phaseBusy} onClick={savePhaseNotes} type="button">Save notes</button>
              </div>
            )}
          </section> : null}

          {showPhaseForm ? (
            <div aria-modal="true" className="phase-dialog-backdrop" role="dialog">
              <form className="phase-dialog" onSubmit={savePhase}>
                <header><div><h2>{editingPhaseId ? "Edit Phase" : "New Phase"}</h2><p>Define the outcome, dates, and expected investment.</p></div><button aria-label="Close phase form" onClick={() => setShowPhaseForm(false)} type="button">×</button></header>
                <div className="phase-dialog-fields">
                  <label className="wide"><span>Phase name</span><input autoFocus maxLength={255} onChange={(event) => setPhaseDraft({ ...phaseDraft, title: event.target.value })} required value={phaseDraft.title} /></label>
                  <label className="wide"><span>Description</span><textarea onChange={(event) => setPhaseDraft({ ...phaseDraft, description: event.target.value })} rows={3} value={phaseDraft.description} /></label>
                  <label><span>Start date</span><input onChange={(event) => setPhaseDraft({ ...phaseDraft, start_date: event.target.value })} required type="date" value={phaseDraft.start_date} /></label>
                  <label><span>End date</span><input min={phaseDraft.start_date} onChange={(event) => setPhaseDraft({ ...phaseDraft, end_date: event.target.value })} required type="date" value={phaseDraft.end_date} /></label>
                  <label><span>Status</span><select onChange={(event) => setPhaseDraft({ ...phaseDraft, status: event.target.value as PhaseStatus })} value={phaseDraft.status}><option value="planning">Planning</option><option value="active">Active</option><option value="completed">Completed</option><option value="archived">Archived</option></select></label>
                  <label><span>Progress (%)</span><input max="100" min="0" onChange={(event) => setPhaseDraft({ ...phaseDraft, progress: event.target.value })} required type="number" value={phaseDraft.progress} /></label>
                  <label className="wide"><span>Estimated focus hours</span><input min="0" onChange={(event) => setPhaseDraft({ ...phaseDraft, estimated_focus_hours: event.target.value })} required step="0.5" type="number" value={phaseDraft.estimated_focus_hours} /></label>
                </div>
                <footer><button onClick={() => setShowPhaseForm(false)} type="button">Cancel</button><button disabled={phaseBusy} type="submit">{phaseBusy ? "Saving…" : editingPhaseId ? "Save changes" : "Create phase"}</button></footer>
              </form>
            </div>
          ) : null}

          {showMilestoneForm ? (
            <div aria-modal="true" className="phase-dialog-backdrop" role="dialog">
              <form className="phase-dialog milestone-dialog" onSubmit={saveMilestone}>
                <header><div><h2>{editingMilestoneId ? "Edit Milestone" : "Add Milestone"}</h2><p>Define a measurable outcome inside {selectedPhase?.title}.</p></div><button aria-label="Close milestone form" onClick={() => setShowMilestoneForm(false)} type="button">×</button></header>
                <div className="phase-dialog-fields">
                  <label className="wide"><span>Milestone name</span><input autoFocus maxLength={255} onChange={(event) => setMilestoneDraft({ ...milestoneDraft, title: event.target.value })} required value={milestoneDraft.title} /></label>
                  <label className="wide"><span>Description</span><textarea onChange={(event) => setMilestoneDraft({ ...milestoneDraft, description: event.target.value })} rows={3} value={milestoneDraft.description} /></label>
                  <label><span>Due date</span><input onChange={(event) => setMilestoneDraft({ ...milestoneDraft, due_date: event.target.value })} type="date" value={milestoneDraft.due_date} /></label>
                  <label><span>Status</span><select onChange={(event) => setMilestoneDraft({ ...milestoneDraft, status: event.target.value as MilestoneStatus })} value={milestoneDraft.status}><option value="not_started">Not Started</option><option value="in_progress">In Progress</option><option value="completed">Completed</option></select></label>
                  <label className="wide"><span>Progress (%)</span><input max="100" min="0" onChange={(event) => setMilestoneDraft({ ...milestoneDraft, progress: event.target.value })} required type="number" value={milestoneDraft.progress} /></label>
                </div>
                <footer><button onClick={() => setShowMilestoneForm(false)} type="button">Cancel</button><button disabled={phaseBusy} type="submit">{phaseBusy ? "Saving…" : editingMilestoneId ? "Save changes" : "Add milestone"}</button></footer>
              </form>
            </div>
          ) : null}
        </main>
      ) : (
        <main className="weekly-reference-content">
          <nav aria-label="Select week" className="week-selector">
            <div>
              <button aria-label="Previous week" disabled={loading} onClick={() => moveWeek(-1)} type="button">‹</button>
              <button aria-label="Next week" disabled={loading} onClick={() => moveWeek(1)} type="button">›</button>
              <PlanIcon name="calendar" size={15} />
              <strong>{weekLabel}</strong>
              <button aria-label="Go to current week" disabled={loading || weekAnchor === localToday()} onClick={() => selectWeek(localToday())} type="button">Today</button>
            </div>
            <Link className="outline-purple" href="/weekly-review"><PlanIcon name="chart" /> This Week&apos;s Review</Link>
          </nav>

          <section className="plan-card week-overview-card">
            <h2>This Week Overview</h2>
            <div className="week-overview-grid">
              <div><span>Weekly Goal</span><strong>{targetMinutes ? formatHours(targetMinutes) : "—"}</strong><small>Focus time</small></div>
              <div><span>Planned Focus</span><strong>{formatHours(plannedMinutes)}</strong><small>{targetMinutes ? `${planVsGoal}% of goal` : "Set a goal below"}</small></div>
              <div><span>Tasks</span><strong>{goals.length}</strong><small>Weekly priorities</small></div>
              <div><span>Priority Tasks</span><strong>{highPriorityCount}</strong><small>High impact</small></div>
              <div className="overview-progress">
                <i style={{ background: `conic-gradient(#24a84b ${completion * 3.6}deg, #e7eee8 0deg)` }}><b>{completion}%</b></i>
                <span><strong>Overall Progress</strong><small>{completedPriorities} of {goals.length} completed · weighted by priority and hours</small></span>
              </div>
            </div>
          </section>

          <section className="plan-card adaptive-week-card">
            <div className="adaptive-week-heading">
              <div><h2><PlanIcon name="spark" /> Adaptive Weekly Planning</h2><p>Balance your intended time against recent focus sessions and completion patterns.</p></div>
              <label><span>Time you intend to dedicate</span><i><input min="0.5" onChange={(event) => setIntendedHours(event.target.value)} step="0.5" type="number" value={intendedHours} /> hours</i></label>
              <button disabled={busy || Number(intendedHours) <= 0} onClick={generateWeeklyPreview} type="button">{weeklyPreview ? "Recalculate" : "Build preview"}</button>
            </div>
            {weeklyPreview ? <div className="adaptive-week-preview">
              <div className="adaptive-week-summary">
                <span><small>Recommended plan</small><strong>{formatHours(weeklyPreview.recommended_minutes)}</strong></span>
                <span><small>Recent weekly focus</small><strong>{formatHours(weeklyPreview.historical_weekly_focus_minutes)}</strong></span>
                <span><small>Completion pattern</small><strong>{Math.round(weeklyPreview.historical_completion_rate * 100)}%</strong></span>
                <span><small>Estimate calibration</small><strong>{weeklyPreview.calibration.factor.toFixed(2)}×</strong></span>
              </div>
              <div className="adaptive-goal-allocations">{weeklyPreview.goal_allocations.map((allocation) => <div key={allocation.weekly_goal_id}><span>{allocation.title}</span><small>{formatHours(allocation.current_minutes)} → <b>{formatHours(allocation.recommended_minutes)}</b></small></div>)}</div>
              <p>{weeklyPreview.rationale.join(" ")}</p>
              {weeklyPreview.status === "pending" ? <button className="confirm-adaptive-week" disabled={busy} onClick={confirmWeeklyPreview} type="button"><PlanIcon name="check" size={14} /> Confirm weekly plan</button> : <span className="adaptive-week-confirmed"><PlanIcon name="check" size={14} /> Confirmed</span>}
            </div> : <div className="adaptive-week-empty"><PlanIcon name="chart" size={18} /><span><strong>Start with your available time</strong><small>The preview will not modify your weekly priorities until you confirm it.</small></span></div>}
          </section>

          <section className="plan-card key-priorities-card">
            <div className="priority-section-heading">
              <div><h2><PlanIcon name="target" /> Key Priorities This Week</h2><p>Focus on what matters most. Check items off as you finish.</p></div>
            </div>
            <div className="priority-content-grid">
              <div className="reference-priority-list">
                {loading ? <p>Loading priorities…</p> : null}
                {!loading && priorities.length === 0 ? <p>No priorities yet. Add the first meaningful task for this week.</p> : null}
                {priorities.map((task) => (
                  <div className={`${task.status === "completed" ? "completed" : ""} ${task.is_overdue ? "overdue" : ""}`} key={task.id}>
                    <button aria-label={task.status === "completed" ? `Reopen ${task.title}` : `Complete ${task.title}`} className={`plan-completion-toggle ${task.status === "completed" ? "completed" : ""}`} disabled={busy} onClick={() => toggleTaskCompleted(task)} title={task.status === "completed" ? "Reopen priority" : "Mark priority complete"} type="button">{task.status === "completed" ? <PlanIcon name="check" size={12} /> : null}</button>
                    <span className="priority-title">{task.title}{task.is_overdue ? <em className="task-overdue-badge">Overdue</em> : null}</span>
                    <b className={task.priority}>{task.priority}</b>
                    <small>{task.target_minutes ? `Est. ${formatHours(task.target_minutes)}` : "Flexible"}</small>
                    <div className="priority-row-actions">
                      <button aria-label={`Edit ${task.title}`} className="priority-edit-button" disabled={busy} onClick={() => editTask(task)} title="Edit priority" type="button"><PlanIcon name="edit" size={17} /></button>
                      <button aria-label={`Delete ${task.title}`} className="priority-delete-button" disabled={busy} onClick={() => deleteTask(task)} title="Delete priority" type="button"><PlanIcon name="trash" size={17} /></button>
                    </div>
                  </div>
                ))}
                {!showTaskForm ? <button className="add-priority-button" onClick={() => { setEditingTaskId(null); setShowTaskForm(true); }} type="button"><PlanIcon name="plus" size={14} /> Add Priority</button> : null}
                {showTaskForm ? <form className="reference-task-form" onSubmit={createTask}>
                  <input maxLength={255} placeholder="Priority title" required value={taskTitle} onChange={(event) => setTaskTitle(event.target.value)} />
                  <input aria-label="Estimated hours" min="0.25" placeholder="Hours" step="0.25" type="number" value={taskHours} onChange={(event) => setTaskHours(event.target.value)} />
                  <select aria-label="Priority level" value={taskPriority} onChange={(event) => setTaskPriority(event.target.value as Priority)}><option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option></select>
                  <button disabled={busy} type="submit">{editingTaskId ? "Save changes" : "Save priority"}</button>
                  <button onClick={cancelTaskForm} type="button">Cancel</button>
                </form> : null}
              </div>
              <aside className="weekly-ai-suggestion">
                <h3><PlanIcon name="spark" /> AI Suggestion</h3>
                <p>{suggestion}</p>
                <Link href="/check-in">View Details <PlanIcon name="arrow" size={14} /></Link>
              </aside>
            </div>

          </section>
        </main>
      )}
    </section>
  );
}
