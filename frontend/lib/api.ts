import { getStoredUserId } from "./auth";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export type Priority = "low" | "medium" | "high";
export type TaskStatus = "pending" | "in_progress" | "completed" | "cancelled";

export type WeeklyGoal = {
  id: number;
  user_id: number;
  title: string;
  description: string | null;
  week_start: string;
  week_end: string;
  priority: Priority;
  status: "active" | "completed" | "cancelled";
  target_minutes: number | null;
  notion_page_id: string | null;
  created_at: string;
  updated_at: string;
};

export type DailyTask = {
  id: number;
  user_id: number;
  title: string;
  description: string | null;
  task_date: string;
  estimated_minutes: number | null;
  priority: Priority;
  weekly_goal_id: number | null;
  status: TaskStatus;
  source: "manual" | "ai" | "notion";
  completed_at: string | null;
  created_at: string;
  updated_at: string;
};

export type StudySession = {
  id: number;
  user_id: number;
  daily_task_id: number | null;
  subject: string;
  started_at: string;
  ended_at: string | null;
  duration_minutes: number | null;
  status: "running" | "paused" | "completed" | "cancelled";
  notes: string | null;
  created_at: string;
};

export type TodayDashboard = {
  date: string;
  focus_minutes: number;
  planned_tasks: number;
  completed_tasks: number;
  completion_rate: number;
  unfinished_tasks: DailyTask[];
};

export type WeekDashboard = {
  week_start: string;
  week_end: string;
  focus_minutes: number;
  planned_tasks: number;
  completed_tasks: number;
  completion_rate: number;
  active_goals: number;
  completed_goals: number;
  daily_focus: { date: string; focus_minutes: number }[];
};

export type DailyReview = {
  id: number;
  user_id: number;
  review_date: string;
  summary: string;
  tomorrow_adjustment: string | null;
  planned_tasks: number;
  completed_tasks: number;
  focus_minutes: number;
  source: "manual" | "ai";
  created_at: string;
  updated_at: string;
};

type RequestOptions = {
  method?: string;
  body?: unknown;
};

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: options.method || "GET",
    headers: {
      "Content-Type": "application/json",
      "X-User-ID": getStoredUserId(),
    },
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
    cache: "no-store",
  });

  if (!response.ok) {
    let detail = `Request failed with ${response.status}`;
    try {
      const data = await response.json();
      detail = data.detail || detail;
    } catch {
      // Keep default detail.
    }
    throw new Error(detail);
  }

  return response.json() as Promise<T>;
}

export const api = {
  getCurrentGoals: () => request<WeeklyGoal[]>("/weekly-goals/current"),
  createGoal: (body: {
    title: string;
    description?: string | null;
    week_start: string;
    week_end: string;
    priority: Priority;
    target_minutes?: number | null;
  }) => request<WeeklyGoal>("/weekly-goals", { method: "POST", body }),
  updateGoal: (id: number, body: Partial<WeeklyGoal>) =>
    request<WeeklyGoal>(`/weekly-goals/${id}`, { method: "PATCH", body }),

  getTodayTasks: () => request<DailyTask[]>("/daily-tasks/today"),
  createTask: (body: {
    title: string;
    description?: string | null;
    task_date: string;
    estimated_minutes?: number | null;
    priority?: Priority;
    weekly_goal_id?: number | null;
    source?: "manual";
  }) => request<DailyTask>("/daily-tasks", { method: "POST", body }),
  updateTask: (id: number, body: Partial<DailyTask>) =>
    request<DailyTask>(`/daily-tasks/${id}`, { method: "PATCH", body }),
  generatePlan: (body: { available_minutes: number; task_date?: string }) =>
    request<{ task_date: string; tasks: DailyTask[]; total_estimated_minutes: number }>(
      "/daily-tasks/generate",
      { method: "POST", body },
    ),

  startSession: (body: {
    daily_task_id?: number | null;
    subject: string;
    started_at?: string;
  }) => request<StudySession>("/study-sessions/start", { method: "POST", body }),
  finishSession: (body: {
    session_id: number;
    ended_at?: string;
    notes?: string | null;
  }) => request<StudySession>("/study-sessions/finish", { method: "POST", body }),
  getTodaySessions: () => request<StudySession[]>("/study-sessions/today"),

  getTodayDashboard: () => request<TodayDashboard>("/dashboard/today"),
  getWeekDashboard: () => request<WeekDashboard>("/dashboard/week"),

  generateReview: (body: { review_date?: string }) =>
    request<DailyReview>("/reviews/generate", { method: "POST", body }),
  getReview: (date: string) => request<DailyReview>(`/reviews/daily?date=${date}`),
};
