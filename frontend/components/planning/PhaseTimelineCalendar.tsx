"use client";

import { useEffect, useMemo, useState } from "react";
import type { CSSProperties } from "react";
import type { PhasePlan } from "../../lib/api";

type CalendarMode = "month" | "year";
type DisplayStatus = "completed" | "active" | "at-risk" | "overdue" | "planned";

const statusLabels: Array<{ status: DisplayStatus; label: string }> = [
  { status: "completed", label: "Completed" },
  { status: "active", label: "Active" },
  { status: "at-risk", label: "At risk" },
  { status: "overdue", label: "Overdue" },
  { status: "planned", label: "Planned" },
];

function dateAt(value: string) { return new Date(`${value}T00:00:00`); }
function dateKey(value: Date) { return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, "0")}-${String(value.getDate()).padStart(2, "0")}`; }
function addMonths(value: Date, amount: number) { return new Date(value.getFullYear(), value.getMonth() + amount, 1); }
function daysBetween(start: Date, end: Date) { return Math.round((end.getTime() - start.getTime()) / 86_400_000); }
function clamp(value: number, minimum: number, maximum: number) { return Math.min(maximum, Math.max(minimum, value)); }

function phaseRange(phase: PhasePlan, includeYear = false) {
  const options: Intl.DateTimeFormatOptions = { month: "short", day: "numeric", year: includeYear ? "numeric" : undefined };
  return `${dateAt(phase.start_date).toLocaleDateString("en", options)} – ${dateAt(phase.end_date).toLocaleDateString("en", options)}`;
}

function displayStatus(phase: PhasePlan, today: Date): DisplayStatus {
  if (phase.status === "completed") return "completed";
  if (phase.status === "planning" || phase.status === "archived") return "planned";
  const start = dateAt(phase.start_date);
  const end = dateAt(phase.end_date);
  if (end < today) return "overdue";
  if (start > today) return "planned";
  const totalDays = Math.max(1, daysBetween(start, end) + 1);
  const elapsedDays = clamp(daysBetween(start, today) + 1, 0, totalDays);
  const expectedProgress = elapsedDays / totalDays * 100;
  const daysRemaining = daysBetween(today, end);
  return phase.progress + 15 < expectedProgress || (daysRemaining <= 14 && phase.progress < 75) ? "at-risk" : "active";
}

function statusSymbol(status: DisplayStatus) {
  if (status === "completed") return "✓";
  if (status === "at-risk") return "△";
  if (status === "overdue") return "!";
  return "○";
}

function monthBarStyle(phase: PhasePlan, anchor: Date) {
  const monthStart = new Date(anchor.getFullYear(), anchor.getMonth(), 1);
  const monthEnd = new Date(anchor.getFullYear(), anchor.getMonth() + 1, 0);
  const visibleStart = dateAt(phase.start_date) < monthStart ? monthStart : dateAt(phase.start_date);
  const visibleEnd = dateAt(phase.end_date) > monthEnd ? monthEnd : dateAt(phase.end_date);
  const daysInMonth = monthEnd.getDate();
  return { left: `${(visibleStart.getDate() - 1) / daysInMonth * 100}%`, width: `${Math.max(1.5, (visibleEnd.getDate() - visibleStart.getDate() + 1) / daysInMonth * 100)}%` };
}

function yearBarStyle(phase: PhasePlan, year: number) {
  const yearStart = new Date(year, 0, 1);
  const yearEnd = new Date(year, 11, 31);
  const visibleStart = dateAt(phase.start_date) < yearStart ? yearStart : dateAt(phase.start_date);
  const visibleEnd = dateAt(phase.end_date) > yearEnd ? yearEnd : dateAt(phase.end_date);
  const totalDays = daysBetween(yearStart, yearEnd) + 1;
  return { left: `${daysBetween(yearStart, visibleStart) / totalDays * 100}%`, width: `${Math.max(1.5, (daysBetween(visibleStart, visibleEnd) + 1) / totalDays * 100)}%` };
}

export default function PhaseTimelineCalendar({ phases, selectedPhaseId, onSelectPhase }: { phases: PhasePlan[]; selectedPhaseId: number | null; onSelectPhase: (phaseId: number) => void }) {
  const [mode, setMode] = useState<CalendarMode>("month");
  const [anchor, setAnchor] = useState(() => new Date());
  const today = useMemo(() => { const value = new Date(); return new Date(value.getFullYear(), value.getMonth(), value.getDate()); }, []);

  useEffect(() => {
    if (phases.length === 0) return;
    setAnchor((current) => {
      const periodStart = mode === "month" ? new Date(current.getFullYear(), current.getMonth(), 1) : new Date(current.getFullYear(), 0, 1);
      const periodEnd = mode === "month" ? new Date(current.getFullYear(), current.getMonth() + 1, 0) : new Date(current.getFullYear(), 11, 31);
      return phases.some((phase) => dateAt(phase.start_date) <= periodEnd && dateAt(phase.end_date) >= periodStart) ? current : dateAt(phases[0].start_date);
    });
  }, [mode, phases]);

  const periodStart = mode === "month" ? new Date(anchor.getFullYear(), anchor.getMonth(), 1) : new Date(anchor.getFullYear(), 0, 1);
  const periodEnd = mode === "month" ? new Date(anchor.getFullYear(), anchor.getMonth() + 1, 0) : new Date(anchor.getFullYear(), 11, 31);
  const visiblePhases = phases.filter((phase) => dateAt(phase.start_date) <= periodEnd && dateAt(phase.end_date) >= periodStart);
  const monthDays = useMemo(() => Array.from({ length: new Date(anchor.getFullYear(), anchor.getMonth() + 1, 0).getDate() }, (_, index) => new Date(anchor.getFullYear(), anchor.getMonth(), index + 1)), [anchor]);
  const todayPosition = mode === "month" && today.getFullYear() === anchor.getFullYear() && today.getMonth() === anchor.getMonth() ? (today.getDate() - .5) / monthDays.length * 100 : null;
  const periodTitle = mode === "month" ? anchor.toLocaleDateString("en", { month: "long", year: "numeric" }) : String(anchor.getFullYear());

  function move(amount: number) { setAnchor((current) => mode === "month" ? addMonths(current, amount) : new Date(current.getFullYear() + amount, current.getMonth(), 1)); }

  return <section className="phase-gantt" aria-label={`${periodTitle} phase display`}>
    <header className="phase-gantt-heading">
      <div><h2>Phase display</h2><p>Visualize project phases over time. Toggle between monthly and yearly views.</p></div>
      <div className="phase-gantt-navigation"><button onClick={() => setAnchor(new Date())} type="button">Today</button><button aria-label={`Previous ${mode}`} onClick={() => move(-1)} type="button">‹</button><button aria-label={`Next ${mode}`} onClick={() => move(1)} type="button">›</button></div>
    </header>
    <div className="phase-gantt-mode" role="group" aria-label="Phase display view"><button aria-pressed={mode === "month"} className={mode === "month" ? "active" : ""} onClick={() => setMode("month")} type="button">Monthly</button><button aria-pressed={mode === "year"} className={mode === "year" ? "active" : ""} onClick={() => setMode("year")} type="button">Yearly</button></div>
    <div className="phase-gantt-board">
      <div className="phase-gantt-period"><span>Phase</span><strong>{periodTitle}</strong></div>
      {mode === "month" ? <>
        <div className="phase-gantt-days" style={{ gridTemplateColumns: `repeat(${monthDays.length}, minmax(29px, 1fr))` }}>{monthDays.map((day) => <span className={dateKey(day) === dateKey(today) ? "today" : ""} key={dateKey(day)}><b>{day.getDate()}</b><small>{day.toLocaleDateString("en", { weekday: "narrow" })}</small></span>)}</div>
        <div className="phase-gantt-rows">{visiblePhases.map((phase) => { const status = displayStatus(phase, today); return <div className={`phase-gantt-row ${selectedPhaseId === phase.id ? "selected" : ""}`} key={phase.id}><button className="phase-gantt-label" onClick={() => onSelectPhase(phase.id)} type="button"><i className={status} /><span><strong>{phase.title}</strong><small>{phaseRange(phase)}</small></span><b>›</b></button><div className="phase-gantt-track" style={{ "--phase-columns": monthDays.length } as CSSProperties}>{todayPosition !== null ? <i className="phase-today-line" style={{ left: `${todayPosition}%` }}><b>{today.getDate()}</b></i> : null}<button className={`phase-gantt-bar ${status}`} onClick={() => onSelectPhase(phase.id)} style={monthBarStyle(phase, anchor)} title={`${phase.title}: ${phaseRange(phase, true)}`} type="button"><span>{statusSymbol(status)}</span><strong>{phase.title}</strong><i>{statusSymbol(status)}</i></button></div></div>; })}</div>
      </> : <>
        <div className="phase-gantt-months">{Array.from({ length: 12 }, (_, month) => <span key={month}>{new Date(anchor.getFullYear(), month, 1).toLocaleDateString("en", { month: "short" })}</span>)}</div>
        <div className="phase-gantt-rows phase-gantt-year-rows">{visiblePhases.map((phase) => { const status = displayStatus(phase, today); return <div className={`phase-gantt-row ${selectedPhaseId === phase.id ? "selected" : ""}`} key={phase.id}><button className="phase-gantt-label" onClick={() => onSelectPhase(phase.id)} type="button"><i className={status} /><span><strong>{phase.title}</strong><small>{phaseRange(phase)}</small></span></button><div className="phase-gantt-track year"><button className={`phase-gantt-bar ${status}`} onClick={() => onSelectPhase(phase.id)} style={yearBarStyle(phase, anchor.getFullYear())} title={`${phase.title}: ${phaseRange(phase, true)}`} type="button"><strong>{phase.title}</strong><i>{statusSymbol(status)}</i></button></div></div>; })}</div>
      </>}
      {visiblePhases.length === 0 ? <p className="phase-gantt-empty">No phases overlap {periodTitle}. Use the arrows to view another period.</p> : null}
    </div>
    <div className="phase-gantt-legend"><strong>Status legend</strong><div>{statusLabels.map(({ status, label }) => <span className={status} key={status}><i />{label}</span>)}</div></div>
    {mode === "year" ? <p className="phase-year-note">Yearly view shows phase duration across months.</p> : null}
  </section>;
}
