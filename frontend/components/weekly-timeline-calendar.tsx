"use client";

import { CSSProperties, FormEvent, PointerEvent as ReactPointerEvent, useEffect, useMemo, useRef, useState } from "react";
import { DailyTask, Priority, TaskStatus } from "../lib/api";

const DAY_START = 7 * 60;
const DAY_END = 22 * 60;
const SCALE = 0.7;
const SNAP = 15;

type Position = { date: string; start: number; duration: number };
type Interaction = Position & {
  task: DailyTask;
  mode: "move" | "resize";
  pointerStartY: number;
  originalStart: number;
  originalDuration: number;
  moved: boolean;
};

type EditorState = {
  mode: "add" | "edit";
  task: DailyTask | null;
  date: string;
  title: string;
  start: string;
  duration: string;
  priority: Priority;
  status: TaskStatus;
};

type TimelineProps = {
  busy: boolean;
  dates: string[];
  tasksByDate: Record<string, DailyTask[]>;
  onCreate: (values: { title: string; task_date: string; scheduled_start_minutes: number; estimated_minutes: number; priority: Priority }) => Promise<void>;
  onDelete: (task: DailyTask) => Promise<boolean>;
  onUpdate: (task: DailyTask, values: Partial<DailyTask>) => Promise<void>;
};

function clamp(value: number, minimum: number, maximum: number) {
  return Math.min(Math.max(value, minimum), maximum);
}

function snap(value: number) {
  return Math.round(value / SNAP) * SNAP;
}

function formatClock(minutes: number) {
  const hour = Math.floor(minutes / 60);
  const minute = minutes % 60;
  const suffix = hour >= 12 ? "PM" : "AM";
  return `${hour % 12 || 12}${minute ? `:${String(minute).padStart(2, "0")}` : ""} ${suffix}`;
}

function timeInput(minutes: number) {
  return `${String(Math.floor(minutes / 60)).padStart(2, "0")}:${String(minutes % 60).padStart(2, "0")}`;
}

function inputMinutes(value: string) {
  const [hours, minutes] = value.split(":").map(Number);
  return hours * 60 + minutes;
}

function buildPositions(dates: string[], tasksByDate: Record<string, DailyTask[]>) {
  const positions: Record<number, Position> = {};
  for (const date of dates) {
    let cursor = 8 * 60;
    const tasks = (tasksByDate[date] ?? []).filter((task) => task.status !== "cancelled");
    for (const task of tasks) {
      const duration = Math.max(SNAP, task.estimated_minutes ?? 30);
      const requested = task.scheduled_start_minutes ?? cursor;
      const start = clamp(requested, DAY_START, Math.max(DAY_START, DAY_END - duration));
      positions[task.id] = { date, start, duration };
      if (task.scheduled_start_minutes === null) cursor = Math.min(start + duration + SNAP, DAY_END - SNAP);
    }
  }
  return positions;
}

export default function WeeklyTimelineCalendar({ busy, dates, tasksByDate, onCreate, onDelete, onUpdate }: TimelineProps) {
  const defaults = useMemo(() => buildPositions(dates, tasksByDate), [dates, tasksByDate]);
  const [drafts, setDrafts] = useState<Record<number, Position>>({});
  const [editor, setEditor] = useState<EditorState | null>(null);
  const [now, setNow] = useState<Date | null>(null);
  const daysRef = useRef<HTMLDivElement | null>(null);
  const interaction = useRef<Interaction | null>(null);
  const suppressClickTask = useRef<number | null>(null);
  const height = (DAY_END - DAY_START) * SCALE;
  const hours = Array.from({ length: (DAY_END - DAY_START) / 60 + 1 }, (_, index) => DAY_START + index * 60);

  useEffect(() => {
    setNow(new Date());
    const timer = window.setInterval(() => setNow(new Date()), 60_000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    function handleMove(event: PointerEvent) {
      const current = interaction.current;
      if (!current) return;
      const minuteDelta = snap((event.clientY - current.pointerStartY) / SCALE);
      if (Math.abs(minuteDelta) >= SNAP || Math.abs(event.movementX) > 1) current.moved = true;
      if (current.mode === "resize") {
        current.duration = clamp(current.originalDuration + minuteDelta, SNAP, DAY_END - current.originalStart);
      } else {
        current.start = clamp(current.originalStart + minuteDelta, DAY_START, DAY_END - current.originalDuration);
        const bounds = daysRef.current?.getBoundingClientRect();
        if (bounds && dates.length) {
          const index = clamp(Math.floor(((event.clientX - bounds.left) / bounds.width) * dates.length), 0, dates.length - 1);
          current.date = dates[index];
        }
      }
      setDrafts((values) => ({ ...values, [current.task.id]: { date: current.date, start: current.start, duration: current.duration } }));
    }

    async function handleUp() {
      const current = interaction.current;
      if (!current) return;
      interaction.current = null;
      if (current.moved) {
        suppressClickTask.current = current.task.id;
        await onUpdate(current.task, {
          task_date: current.date,
          scheduled_start_minutes: current.start,
          estimated_minutes: current.duration,
        });
      }
      setDrafts((values) => {
        const next = { ...values };
        delete next[current.task.id];
        return next;
      });
    }

    window.addEventListener("pointermove", handleMove);
    window.addEventListener("pointerup", handleUp);
    window.addEventListener("pointercancel", handleUp);
    return () => {
      window.removeEventListener("pointermove", handleMove);
      window.removeEventListener("pointerup", handleUp);
      window.removeEventListener("pointercancel", handleUp);
    };
  }, [dates, onUpdate]);

  function nextStart(date: string) {
    return Object.values(defaults)
      .filter((position) => position.date === date)
      .reduce((latest, position) => Math.max(latest, position.start + position.duration), 9 * 60);
  }

  function openAdd(date: string) {
    const start = clamp(Math.ceil(nextStart(date) / SNAP) * SNAP, DAY_START, DAY_END - 60);
    setEditor({ mode: "add", task: null, date, title: "", start: timeInput(start), duration: "60", priority: "medium", status: "pending" });
  }

  function openEdit(task: DailyTask) {
    const position = drafts[task.id] ?? defaults[task.id];
    setEditor({
      mode: "edit",
      task,
      date: task.task_date,
      title: task.title,
      start: timeInput(position?.start ?? 9 * 60),
      duration: String(position?.duration ?? task.estimated_minutes ?? 30),
      priority: task.priority,
      status: task.status,
    });
  }

  function beginInteraction(event: ReactPointerEvent<HTMLElement>, task: DailyTask, mode: "move" | "resize") {
    if (busy) return;
    event.preventDefault();
    event.stopPropagation();
    const position = drafts[task.id] ?? defaults[task.id];
    interaction.current = {
      task,
      mode,
      pointerStartY: event.clientY,
      originalStart: position.start,
      originalDuration: position.duration,
      moved: false,
      ...position,
    };
  }

  async function saveEditor(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editor) return;
    const start = inputMinutes(editor.start);
    const duration = Math.max(SNAP, Number(editor.duration));
    if (start + duration > DAY_END) return;
    if (editor.mode === "add") {
      await onCreate({ title: editor.title.trim(), task_date: editor.date, scheduled_start_minutes: start, estimated_minutes: duration, priority: editor.priority });
    } else if (editor.task) {
      await onUpdate(editor.task, { title: editor.title.trim(), task_date: editor.date, scheduled_start_minutes: start, estimated_minutes: duration, priority: editor.priority, status: editor.status });
    }
    setEditor(null);
  }

  const currentDate = now ? `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}` : null;
  const currentMinutes = now ? now.getHours() * 60 + now.getMinutes() : -1;

  return <section className="weekly-timeline" aria-label="Interactive weekly timeline">
    <div className="weekly-timeline-help"><span>Drag a task to move it across days or time.</span><span>Drag its bottom edge to change duration.</span></div>
    <div className="weekly-timeline-scroll">
      <div className="weekly-timeline-canvas" style={{ minWidth: `${Math.max(900, dates.length * 170 + 62)}px` }}>
        <div className="weekly-timeline-header" style={{ gridTemplateColumns: `62px repeat(${dates.length}, minmax(170px, 1fr))` }}>
          <span>Time</span>
          {dates.map((date) => <header key={date}><div><strong>{new Date(`${date}T00:00:00`).toLocaleDateString("en", { weekday: "short" })}</strong><time>{new Date(`${date}T00:00:00`).toLocaleDateString("en", { month: "short", day: "numeric" })}</time></div><button aria-label={`Add task on ${date}`} disabled={busy} onClick={() => openAdd(date)} type="button">+</button></header>)}
        </div>
        <div className="weekly-timeline-body">
          <div className="weekly-timeline-hours" style={{ height: `${height}px` }}>{hours.map((minute) => <div key={minute} style={{ top: `${(minute - DAY_START) * SCALE}px` }}><time>{formatClock(minute)}</time><i /></div>)}</div>
          <div className="weekly-timeline-days" ref={daysRef} style={{ gridTemplateColumns: `repeat(${dates.length}, minmax(170px, 1fr))`, height: `${height}px` }}>
            {dates.map((date) => <div className={`weekly-timeline-day ${date === currentDate ? "today" : ""}`} key={date}>
              {Object.values(tasksByDate).flat().filter((task) => task.status !== "cancelled").map((task) => {
                const position = drafts[task.id] ?? defaults[task.id];
                if (!position || position.date !== date) return null;
                return <article
                  aria-label={`${task.title}, ${formatClock(position.start)} to ${formatClock(position.start + position.duration)}`}
                  className={`weekly-timeline-task ${task.priority} ${task.status === "completed" ? "completed" : ""}`}
                  key={task.id}
                  onClick={() => {
                    if (suppressClickTask.current === task.id) { suppressClickTask.current = null; return; }
                    openEdit(task);
                  }}
                  onPointerDown={(event) => beginInteraction(event, task, "move")}
                  style={{ height: `${Math.max(28, position.duration * SCALE)}px`, top: `${(position.start - DAY_START) * SCALE}px` } as CSSProperties}
                ><strong>{task.title}</strong><span>{formatClock(position.start)}–{formatClock(position.start + position.duration)}</span><button aria-label={`Resize ${task.title}`} onPointerDown={(event) => beginInteraction(event, task, "resize")} tabIndex={-1} type="button" /></article>;
              })}
              {date === currentDate && currentMinutes >= DAY_START && currentMinutes <= DAY_END ? <i className="weekly-timeline-now" style={{ top: `${(currentMinutes - DAY_START) * SCALE}px` }} /> : null}
            </div>)}
          </div>
        </div>
      </div>
    </div>
    {editor ? <div className="weekly-timeline-editor-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setEditor(null); }}><form className="weekly-timeline-editor" onSubmit={saveEditor}>
      <header><div><strong>{editor.mode === "add" ? "Add timeline task" : "Edit timeline task"}</strong><span>{editor.mode === "add" ? "Choose a day and time." : "Changes sync to every calendar."}</span></div><button aria-label="Close task editor" onClick={() => setEditor(null)} type="button">×</button></header>
      <label><span>Task title</span><input autoFocus maxLength={255} onChange={(event) => setEditor({ ...editor, title: event.target.value })} required value={editor.title} /></label>
      <div><label><span>Date</span><select onChange={(event) => setEditor({ ...editor, date: event.target.value })} value={editor.date}>{dates.map((date) => <option key={date} value={date}>{new Date(`${date}T00:00:00`).toLocaleDateString("en", { weekday: "short", month: "short", day: "numeric" })}</option>)}</select></label><label><span>Start</span><input onChange={(event) => setEditor({ ...editor, start: event.target.value })} required step="900" type="time" value={editor.start} /></label></div>
      <div><label><span>Duration (minutes)</span><input min="15" onChange={(event) => setEditor({ ...editor, duration: event.target.value })} required step="15" type="number" value={editor.duration} /></label><label><span>Priority</span><select onChange={(event) => setEditor({ ...editor, priority: event.target.value as Priority })} value={editor.priority}><option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option><option value="urgent">Urgent</option></select></label></div>
      {editor.mode === "edit" ? <label><span>Status</span><select onChange={(event) => setEditor({ ...editor, status: event.target.value as TaskStatus })} value={editor.status}><option value="pending">Pending</option><option value="in_progress">In progress</option><option value="completed">Completed</option><option value="cancelled">Cancelled</option></select></label> : null}
      <output>{formatClock(inputMinutes(editor.start))}–{formatClock(inputMinutes(editor.start) + Number(editor.duration))}</output>
      <footer>{editor.mode === "edit" && editor.task ? <button className="delete" disabled={busy} onClick={async () => { if (await onDelete(editor.task!)) setEditor(null); }} type="button">Delete</button> : null}<button onClick={() => setEditor(null)} type="button">Cancel</button><button disabled={busy || !editor.title.trim() || inputMinutes(editor.start) + Number(editor.duration) > DAY_END} type="submit">{editor.mode === "add" ? "Add task" : "Save changes"}</button></footer>
    </form></div> : null}
  </section>;
}
