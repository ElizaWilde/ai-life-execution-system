import { getStoredUserId } from "./auth";

declare const process: {
  env: {
    NEXT_PUBLIC_API_BASE_URL?: string;
  };
};

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export type Priority = "low" | "medium" | "high";
export type TaskStatus = "pending" | "in_progress" | "completed" | "cancelled";
export type EnergyLevel = "depleted" | "low" | "steady" | "high" | "energized";
export type MoodLevel = "struggling" | "low" | "neutral" | "good" | "great";
export type WorkloadLevel = "light" | "reduced" | "normal";

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
  time_allocation: TimeAllocationPoint[];
  check_in: DailyCheckIn | null;
  coaching: CoachingRecommendation | null;
  readiness_score: number | null;
  workload_multiplier: number | null;
  workload_level: WorkloadLevel | null;
  adjustment_reasons: string[];
};

export type DailyCheckIn = {
  id: number;
  user_id: number;
  check_in_date: string;
  energy_level: EnergyLevel;
  mood_level: MoodLevel;
  sleep_hours: number;
  stress_level: number | null;
  notes: string | null;
  cycle_day: number | null;
  cycle_notes: string | null;
  created_at: string;
  updated_at: string;
};

export type CoachingRecommendation = {
  recommendation_date: string;
  readiness_score: number;
  workload_multiplier: number;
  workload_level: WorkloadLevel;
  summary: string;
  suggestions: string[];
  risk_factors: string[];
  planning_changes: string[];
};

export type AdaptiveDailyPlan = {
  task_date: string;
  original_available_minutes: number;
  adjusted_available_minutes: number;
  workload_level: WorkloadLevel;
  readiness_score: number;
  tasks: DailyTask[];
  total_estimated_minutes: number;
};

export type TimeAllocationPoint = {
  label: string;
  planned_minutes: number;
  focus_minutes: number;
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
  daily_focus: {
    date: string;
    focus_minutes: number;
    planned_minutes: number;
  }[];
  time_allocation: TimeAllocationPoint[];
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

export type WeeklyReview = {
  id: number;
  user_id: number;
  week_start: string;
  week_end: string;
  planned_tasks: number;
  completed_tasks: number;
  completion_rate: number;
  focus_minutes: number;
  check_in_days: number;
  average_sleep_hours: number | null;
  energy_distribution_json: Record<string, number>;
  mood_distribution_json: Record<string, number>;
  summary: string;
  achievements_json: string[];
  obstacles_json: string[];
  next_week_actions_json: string[];
  context_json: Record<string, unknown>;
  model_name: string | null;
  prompt_version: string | null;
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
    request<AdaptiveDailyPlan>(
      "/daily-tasks/generate",
      { method: "POST", body },
    ),

  getTodayCheckIn: () => request<DailyCheckIn>("/check-ins/today"),
  createCheckIn: (body: {
    check_in_date?: string;
    energy_level: EnergyLevel;
    mood_level: MoodLevel;
    sleep_hours: number;
    stress_level?: number | null;
    notes?: string | null;
    cycle_day?: number | null;
    cycle_notes?: string | null;
  }) => request<DailyCheckIn>("/check-ins", { method: "POST", body }),
  updateCheckIn: (
    date: string,
    body: Partial<Omit<DailyCheckIn, "id" | "user_id" | "check_in_date" | "created_at" | "updated_at">>,
  ) => request<DailyCheckIn>(`/check-ins/${date}`, { method: "PATCH", body }),

  generateCoaching: (body: { target_date: string }) =>
    request<CoachingRecommendation>("/coaching/daily/generate", {
      method: "POST",
      body,
    }),
  getCoaching: (date: string) =>
    request<CoachingRecommendation>(`/coaching/daily?date=${date}`),

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
  getDayDashboard: (date: string) =>
    request<TodayDashboard>(`/dashboard/today?date=${date}`),
  getWeekDashboard: () => request<WeekDashboard>("/dashboard/week"),

  generateReview: (body: { review_date?: string }) =>
    request<DailyReview>("/reviews/generate", { method: "POST", body }),
  getReview: (date: string) => request<DailyReview>(`/reviews/daily?date=${date}`),

  generateWeeklyReview: (body: { week_start?: string }) =>
    request<WeeklyReview>("/weekly-reviews/generate", { method: "POST", body }),
  getCurrentWeeklyReview: () =>
    request<WeeklyReview>("/weekly-reviews/current"),
  getWeeklyReview: (weekStart: string) =>
    request<WeeklyReview>(`/weekly-reviews/${weekStart}`),
};
