"use client";

import { CSSProperties, useMemo } from "react";
import { DailyTask, TodayDashboard } from "../lib/api";

function formatMinutes(minutes: number) {
  if (minutes < 60) return `${minutes}m`;
  const hours = minutes / 60;
  return `${hours % 1 === 0 ? hours.toFixed(0) : hours.toFixed(1)}h`;
}

function formatReviewDate(value: string) {
  return new Date(`${value}T00:00:00`).toLocaleDateString("en", {
    weekday: "long",
    month: "long",
    day: "numeric",
  });
}

const TIME_COLORS = ["#6c43e8", "#37b46b", "#f0a136", "#4c8ee8", "#ec6582", "#27a8a1"];

type DailyReviewModuleProps = {
  date: string;
  dashboard: TodayDashboard | null;
  tasks: DailyTask[];
};

export default function DailyReviewModule({
  date,
  dashboard,
  tasks,
}: DailyReviewModuleProps) {
  const activeTasks = useMemo(
    () => tasks.filter((task) => task.status !== "cancelled"),
    [tasks],
  );
  const plannedMinutes = activeTasks.reduce(
    (total, task) => total + (task.estimated_minutes ?? 0),
    0,
  );
  const focusMinutes = dashboard?.focus_minutes ?? 0;
  const allocation = useMemo(
    () => (dashboard?.time_allocation ?? []).filter((item) => item.focus_minutes > 0),
    [dashboard?.time_allocation],
  );
  const focusedByTitle = useMemo(
    () => new Map(allocation.map((item) => [item.label, item.focus_minutes])),
    [allocation],
  );
  const workedOn = useMemo(
    () => activeTasks.filter(
      (task) => task.status === "completed" || (focusedByTitle.get(task.title) ?? 0) > 0,
    ),
    [activeTasks, focusedByTitle],
  );
  const didNotGetTo = useMemo(
    () => activeTasks.filter(
      (task) => task.status !== "completed" && (focusedByTitle.get(task.title) ?? 0) === 0,
    ),
    [activeTasks, focusedByTitle],
  );
  const uncategorized = allocation.filter(
    (item) => !activeTasks.some((task) => task.title === item.label),
  );
  const chartTotal = allocation.reduce((total, item) => total + item.focus_minutes, 0);
  let chartCursor = 0;
  const chartStops = allocation.map((item, index) => {
    const start = chartCursor;
    chartCursor += chartTotal ? (item.focus_minutes / chartTotal) * 100 : 0;
    return `${TIME_COLORS[index % TIME_COLORS.length]} ${start}% ${chartCursor}%`;
  });
  const donutStyle = {
    "--time-review-chart": chartStops.length
      ? `conic-gradient(${chartStops.join(", ")})`
      : "conic-gradient(#e6e7eb 0 100%)",
  } as CSSProperties;
  const scaleMinutes = Math.max(plannedMinutes, focusMinutes, 8 * 60);
  const actualWidth = Math.min((focusMinutes / scaleMinutes) * 100, 100);
  const plannedWidth = Math.min((plannedMinutes / scaleMinutes) * 100, 100);
  const actualMarker = Math.max(8, Math.min(actualWidth, 92));
  const plannedMarker = Math.max(8, Math.min(plannedWidth, 92));
  const firstScaleMark = scaleMinutes === 8 * 60
    ? 6 * 60
    : Math.round(scaleMinutes * 0.75);

  function taskRow(task: DailyTask, kind: "worked" | "missed") {
    const actual = focusedByTitle.get(task.title) ?? 0;
    return (
      <li key={task.id}>
        <span className={`review-task-indicator ${kind}`} />
        <div>
          <strong>{task.title}</strong>
          <small>
            {kind === "worked"
              ? `${formatMinutes(actual)} focused${task.estimated_minutes ? ` · ${formatMinutes(task.estimated_minutes)} planned` : ""}`
              : `${task.estimated_minutes ? `${formatMinutes(task.estimated_minutes)} planned` : "Flexible duration"} · ${task.priority} priority`}
          </small>
        </div>
        {task.status === "completed"
          ? <b className="review-task-status completed">Done</b>
          : kind === "worked"
            ? <b className="review-task-status active">Worked on</b>
            : <b className="review-task-status missed">Not started</b>}
      </li>
    );
  }

  return (
    <section className="today-card today-review-module time-review-module">
      <header className="time-review-heading">
        <div>
          <h2>Today’s Review</h2>
          <p>How you spent your time on {formatReviewDate(date)}.</p>
        </div>
        <span>{formatMinutes(focusMinutes)} focused</span>
      </header>

      <div className="time-review-overview">
        <article className="time-total-card">
          <span className="time-review-eyebrow">Total time</span>
          <div aria-label={`${formatMinutes(focusMinutes)} focused of ${formatMinutes(plannedMinutes)} planned`} className="time-total-scale">
            <span className="actual" style={{ width: `${actualWidth}%` }} />
            <i className="time-badge actual" style={{ left: `${actualMarker}%` }}>{formatMinutes(focusMinutes)}</i>
            <i className="time-pointer actual" style={{ left: `${actualMarker}%` }} />
            <i className="time-badge planned" style={{ left: `${plannedMarker}%` }}>{formatMinutes(plannedMinutes)}<small>planned</small></i>
            <i className="time-pointer planned" style={{ left: `${plannedMarker}%` }} />
            <span className="time-scale-mark first" style={{ left: `${(firstScaleMark / scaleMinutes) * 100}%` }}>{formatMinutes(firstScaleMark)}</span>
            <span className="time-scale-mark last">{formatMinutes(scaleMinutes)}</span>
          </div>
        </article>

        <article className="time-distribution-card">
          <span className="time-review-eyebrow">How you spent your time</span>
          <div className="time-donut" style={donutStyle} title={allocation.map((item) => `${item.label}: ${formatMinutes(item.focus_minutes)}`).join("\n") || "No focused time recorded"}>
            <span><strong>{formatMinutes(chartTotal)}</strong><small>total</small></span>
          </div>
          <ul className="time-distribution-legend">
            {allocation.length
              ? allocation.map((item, index) => <li key={item.label} title={`${item.label}: ${formatMinutes(item.focus_minutes)}`}><i style={{ background: TIME_COLORS[index % TIME_COLORS.length] }} /><span>{item.label}</span><strong>{formatMinutes(item.focus_minutes)}</strong></li>)
              : <li className="empty"><i /><span>Uncategorized</span><strong>0m</strong></li>}
          </ul>
        </article>
      </div>

      <div className="time-review-task-lists">
        <article>
          <header><div><span className="review-list-icon worked">✓</span><h3>Worked on</h3></div><b>{workedOn.length + uncategorized.length}</b></header>
          {workedOn.length || uncategorized.length
            ? <ul>
              {workedOn.map((task) => taskRow(task, "worked"))}
              {uncategorized.map((item) => <li key={`uncategorized-${item.label}`}><span className="review-task-indicator worked" /><div><strong>{item.label}</strong><small>{formatMinutes(item.focus_minutes)} focused · Not linked to a task</small></div><b className="review-task-status active">Worked on</b></li>)}
            </ul>
            : <p className="time-review-empty">Start a focus session to record what you worked on.</p>}
        </article>

        <article>
          <header><div><span className="review-list-icon missed">–</span><h3>Didn’t get to</h3></div><b>{didNotGetTo.length}</b></header>
          {didNotGetTo.length
            ? <ul>{didNotGetTo.map((task) => taskRow(task, "missed"))}</ul>
            : <p className="time-review-empty">Every planned task received attention today.</p>}
        </article>
      </div>
    </section>
  );
}
