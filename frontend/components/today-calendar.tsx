"use client";

import { CSSProperties, PointerEvent as ReactPointerEvent, useEffect, useMemo, useRef, useState } from "react";
import { DailyTask } from "../lib/api";

const DAY_START = 7 * 60;
const DAY_END = 22 * 60;
const PIXELS_PER_MINUTE = 0.8;
const SNAP_MINUTES = 15;

type TaskPosition = { start: number; duration: number };
type CalendarInteraction = TaskPosition & {
  task: DailyTask;
  mode: "move" | "resize";
  pointerStart: number;
  originalStart: number;
  originalDuration: number;
};

type TodayCalendarProps = {
  busy: boolean;
  date: string;
  tasks: DailyTask[];
  onScheduleChange: (task: DailyTask, values: { scheduled_start_minutes: number; estimated_minutes: number }) => Promise<void>;
};

function clamp(value: number, minimum: number, maximum: number) {
  return Math.min(Math.max(value, minimum), maximum);
}

function snap(value: number) {
  return Math.round(value / SNAP_MINUTES) * SNAP_MINUTES;
}

function formatClock(minutes: number) {
  const hour = Math.floor(minutes / 60);
  const minute = minutes % 60;
  const suffix = hour >= 12 ? "PM" : "AM";
  const displayHour = hour % 12 || 12;
  return `${displayHour}${minute ? `:${String(minute).padStart(2, "0")}` : ""} ${suffix}`;
}

function buildDefaultPositions(tasks: DailyTask[]) {
  let cursor = 8 * 60;
  return Object.fromEntries(tasks.map((task) => {
    const duration = Math.max(task.estimated_minutes ?? 30, SNAP_MINUTES);
    const requestedStart = task.scheduled_start_minutes ?? cursor;
    const start = clamp(requestedStart, DAY_START, Math.max(DAY_START, DAY_END - duration));
    if (task.scheduled_start_minutes === null) cursor = Math.min(start + duration + SNAP_MINUTES, DAY_END - SNAP_MINUTES);
    return [task.id, { start, duration }] as const;
  }));
}

export default function TodayCalendar({ busy, date, tasks, onScheduleChange }: TodayCalendarProps) {
  const activeTasks = useMemo(() => tasks.filter((task) => task.status !== "cancelled"), [tasks]);
  const defaults = useMemo(() => buildDefaultPositions(activeTasks), [activeTasks]);
  const [drafts, setDrafts] = useState<Record<number, TaskPosition>>({});
  const [activeTaskId, setActiveTaskId] = useState<number | null>(null);
  const [now, setNow] = useState<Date | null>(null);
  const interaction = useRef<CalendarInteraction | null>(null);

  useEffect(() => {
    setNow(new Date());
    const timer = window.setInterval(() => setNow(new Date()), 60_000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    function handlePointerMove(event: PointerEvent) {
      const current = interaction.current;
      if (!current) return;
      const minuteDelta = snap((event.clientY - current.pointerStart) / PIXELS_PER_MINUTE);
      if (current.mode === "move") {
        current.start = clamp(current.originalStart + minuteDelta, DAY_START, DAY_END - current.originalDuration);
      } else {
        current.duration = clamp(current.originalDuration + minuteDelta, SNAP_MINUTES, DAY_END - current.originalStart);
      }
      setDrafts((values) => ({ ...values, [current.task.id]: { start: current.start, duration: current.duration } }));
    }

    async function handlePointerUp() {
      const current = interaction.current;
      if (!current) return;
      interaction.current = null;
      setActiveTaskId(null);
      await onScheduleChange(current.task, {
        scheduled_start_minutes: current.start,
        estimated_minutes: current.duration,
      });
    }

    window.addEventListener("pointermove", handlePointerMove);
    window.addEventListener("pointerup", handlePointerUp);
    window.addEventListener("pointercancel", handlePointerUp);
    return () => {
      window.removeEventListener("pointermove", handlePointerMove);
      window.removeEventListener("pointerup", handlePointerUp);
      window.removeEventListener("pointercancel", handlePointerUp);
    };
  }, [onScheduleChange]);

  function beginInteraction(event: ReactPointerEvent<HTMLElement>, task: DailyTask, mode: "move" | "resize") {
    if (busy) return;
    event.preventDefault();
    event.stopPropagation();
    const position = drafts[task.id] ?? defaults[task.id];
    interaction.current = {
      task,
      mode,
      pointerStart: event.clientY,
      originalStart: position.start,
      originalDuration: position.duration,
      ...position,
    };
    setActiveTaskId(task.id);
  }

  const selectedDate = new Date(`${date}T00:00:00`);
  const isToday = Boolean(now) && date === `${now!.getFullYear()}-${String(now!.getMonth() + 1).padStart(2, "0")}-${String(now!.getDate()).padStart(2, "0")}`;
  const currentMinutes = now ? now.getHours() * 60 + now.getMinutes() : -1;
  const showCurrentTime = isToday && currentMinutes >= DAY_START && currentMinutes <= DAY_END;
  const calendarHeight = (DAY_END - DAY_START) * PIXELS_PER_MINUTE;
  const hourMarkers = Array.from({ length: (DAY_END - DAY_START) / 60 + 1 }, (_, index) => DAY_START + index * 60);

  return (
    <section className="today-card today-calendar-card" aria-label="Today calendar">
      <header className="today-calendar-heading">
        <div><h2>Calendar</h2><p>Drag tasks to move them. Pull the bottom edge to resize.</p></div>
        <time dateTime={date}><span>{selectedDate.toLocaleDateString("en", { weekday: "short" }).toUpperCase()}</span><strong>{selectedDate.getDate()}</strong></time>
      </header>
      <div className="today-calendar-scroll">
        <div className="today-calendar-grid" style={{ height: `${calendarHeight}px` }}>
          {hourMarkers.map((minutes) => <div className="today-calendar-hour" key={minutes} style={{ top: `${(minutes - DAY_START) * PIXELS_PER_MINUTE}px` }}><time>{formatClock(minutes)}</time><i /></div>)}
          {activeTasks.map((task) => {
            const position = drafts[task.id] ?? defaults[task.id];
            const blockStyle = {
              height: `${Math.max(position.duration * PIXELS_PER_MINUTE, 26)}px`,
              top: `${(position.start - DAY_START) * PIXELS_PER_MINUTE}px`,
            } as CSSProperties;
            return <article
              aria-label={`${task.title}, ${formatClock(position.start)} to ${formatClock(position.start + position.duration)}`}
              className={`today-calendar-task ${task.priority} ${task.status === "completed" ? "completed" : ""} ${activeTaskId === task.id ? "interacting" : ""}`}
              key={task.id}
              onPointerDown={(event) => beginInteraction(event, task, "move")}
              style={blockStyle}
              title="Drag to change time"
            >
              <strong>{task.title}</strong>
              <span>{formatClock(position.start)} – {formatClock(position.start + position.duration)}</span>
              <button aria-label={`Resize ${task.title}`} onPointerDown={(event) => beginInteraction(event, task, "resize")} tabIndex={-1} type="button" />
            </article>;
          })}
          {showCurrentTime ? <div aria-label={`Current time ${formatClock(currentMinutes)}`} className="today-current-time" style={{ top: `${(currentMinutes - DAY_START) * PIXELS_PER_MINUTE}px` }}><span>{formatClock(currentMinutes)}</span><i /></div> : null}
          {!activeTasks.length ? <p className="today-calendar-empty">Tasks added in Weekly Plan for today will appear here.</p> : null}
        </div>
      </div>
    </section>
  );
}
