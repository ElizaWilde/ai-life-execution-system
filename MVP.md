For this project, **MVP should not be “full AI life operating system.”**
MVP should be:

> **A working personal execution tracker that turns a weekly plan into daily tasks, lets the user track study sessions, and shows whether the user is on track.**

Your source plan already defines Phase 1 MVP as: **authentication, Notion integration, weekly planning, daily planning, study timer, study session recording, dashboard, and basic statistics**. 

## 1. MVP Core Loop

Build only this loop first:

```text
User writes weekly goals
        ↓
System generates today's plan
        ↓
User starts/stops study timer
        ↓
System records study sessions
        ↓
Dashboard shows progress
        ↓
User adjusts tomorrow
```

This matches your project’s execution-loop idea: weekly plan → daily plan → execution → tracking → analysis → update. 

## 2. MVP Features: Keep / Cut

### Must build

| Feature           | MVP version                                               |
| ----------------- | --------------------------------------------------------- |
| Weekly plan       | User creates weekly goals manually or imports from Notion |
| Daily plan        | AI generates today’s tasks from weekly goals              |
| Study timer       | Start / pause / stop                                      |
| Session recording | Store subject, task, start time, end time, duration       |
| Dashboard         | Show today focus time, weekly progress, unfinished tasks  |
| Basic AI          | Generate daily plan + short evening summary               |

### Cut for MVP

Do **not** build these yet:

```text
Mobile app
Full multi-agent system
Menstrual cycle tracking
Long-term memory
pgvector
Redis
Google Calendar sync
Notification system
Forecast probability
Wearable integration
Complex autonomous rescheduling
```

Those belong to later phases, not MVP.

## 3. Minimal Architecture

Use a simple architecture first:

```text
Next.js frontend
        ↓
FastAPI backend
        ↓
PostgreSQL
        ↓
Notion API
        ↓
LLM API
```

Although your full plan includes Coordinator Agent, Planner Agent, Study Agent, Coach Agent, and Analytics Agent, the MVP should combine them into **one backend service** first. Your file describes these agents as separate layers, but separating them too early will slow you down. 

MVP backend structure:

```text
backend/
  app/
    main.py
    api/
      plans.py
      tasks.py
      sessions.py
      dashboard.py
      ai.py
    services/
      notion_service.py
      planning_service.py
      stats_service.py
      llm_service.py
    models/
      user.py
      goal.py
      task.py
      session.py
```

Frontend:

```text
frontend/
  app/
    dashboard/
    weekly-plan/
    today/
    timer/
    review/
```

## 4. Database Design

Use only these tables first.

### users

```sql
id
email
name
created_at
```

### weekly_goals

```sql
id
user_id
title
description
week_start
week_end
status
created_at
```

Example:

```text
Goal: Finish TOEFL writing practice
Target: 7 essays this week
Week: 2026-06-22 to 2026-06-28
```

### daily_tasks

```sql
id
user_id
weekly_goal_id
title
description
date
estimated_minutes
status
priority
created_at
```

Example:

```text
Task: Write one TOEFL academic discussion response
Estimated: 40 minutes
Status: pending
```

### study_sessions

```sql
id
user_id
task_id
title
subject
start_time
end_time
duration_minutes
note
created_at
```

### daily_reviews

```sql
id
user_id
date
summary
completed_minutes
planned_minutes
completion_rate
ai_feedback
created_at
```

This is enough for MVP.

## 5. Pages You Need

### Page 1: Weekly Plan

User can:

```text
Create weekly goal
Edit weekly goal
Mark weekly goal complete
Import from Notion later
```

Do Notion integration after manual weekly planning works.

### Page 2: Today

Shows:

```text
Today's tasks
Estimated time
Priority
Start button
Complete button
```

Example UI:

```text
Today — June 26

1. TOEFL writing practice — 40 min — Start
2. Read RAG paper — 60 min — Start
3. Transformer coding practice — 45 min — Start
```

### Page 3: Timer

Simple timer:

```text
Task: TOEFL writing practice
00:24:31

[Pause] [Finish]
```

When finished, save a `study_session`.

### Page 4: Dashboard

Show:

```text
Today focus time: 2h 10m
Weekly focus time: 11h 30m
Tasks completed: 8 / 14
Goal progress: 57%
Most studied subject: TOEFL
```

Use simple cards first. Charts later.

### Page 5: Review

Evening review:

```text
What did you finish today?
What was not finished?
Why?
What should tomorrow change?
```

AI generates a short summary.

## 6. AI Feature for MVP

Do not build a complex agent first. Use one function:

```text
generate_daily_plan(weekly_goals, unfinished_tasks, available_hours)
```

Prompt shape:

```text
You are a planning assistant.

Given the user's weekly goals, unfinished tasks, and available study time,
generate a realistic daily plan.

Rules:
- Do not overload the user.
- Prefer unfinished urgent tasks.
- Split large goals into small tasks.
- Each task should have an estimated duration.
- Output JSON only.
```

Example output:

```json
[
  {
    "title": "Write one TOEFL academic discussion response",
    "goal": "Improve TOEFL writing",
    "estimated_minutes": 40,
    "priority": "high"
  },
  {
    "title": "Review grammar mistakes from previous essay",
    "goal": "Improve TOEFL writing",
    "estimated_minutes": 25,
    "priority": "medium"
  }
]
```

This gives you “AI planning” without overengineering.

## 7. API Endpoints

Build these first:

```text
POST /weekly-goals
GET  /weekly-goals/current

POST /daily-plan/generate
GET  /daily-tasks/today
PATCH /daily-tasks/{id}

POST /sessions/start
POST /sessions/finish
GET  /sessions/today

GET  /dashboard/today
GET  /dashboard/week

POST /review/generate
```

Do not add natural-language command API yet.

## 8. MVP Development Order

### Step 1 — Local full-stack skeleton

Build:

```text
Next.js frontend
FastAPI backend
PostgreSQL
Docker Compose
```

Do not touch AI yet.

### Step 2 — Weekly goals CRUD

User can create/edit/delete weekly goals.

Success condition:

```text
I can create this week’s goals and see them on the page.
```

### Step 3 — Daily task system

User can manually create today’s tasks.

Success condition:

```text
I can create today’s task and mark it completed.
```

### Step 4 — Timer + session recording

Start/stop timer and write session to DB.

Success condition:

```text
I can study for 25 minutes and the system records it.
```

### Step 5 — Dashboard

Show basic statistics.

Success condition:

```text
I can see today’s focus time, weekly focus time, and task completion rate.
```

### Step 6 — AI daily plan

Add LLM-generated task creation from weekly goals.

Success condition:

```text
I click “Generate Today’s Plan” and get realistic tasks.
```

### Step 7 — Notion integration

Sync weekly goals from Notion or push weekly review to Notion.

Success condition:

```text
The system can read my Notion weekly plan or write a weekly review page.
```

## 9. MVP Acceptance Criteria

Your MVP is done when this works:

```text
1. User logs in.
2. User creates weekly goals.
3. User clicks "Generate Today’s Plan."
4. System creates 3–5 tasks.
5. User starts a task timer.
6. User stops the timer.
7. System records the study session.
8. Dashboard updates focus time and completion rate.
9. AI generates a short daily review.
```

That is enough to prove the product.

## 10. One Good MVP Demo Scenario

Use yourself as the first user.

Example:

```text
Weekly goals:
- TOEFL writing: write 5 practice responses
- Transformer learning: understand self-attention
- Research project: read 2 RAG security papers

Today available time:
3 hours

AI daily plan:
1. Write one TOEFL response — 40 min
2. Review grammar mistakes — 30 min
3. Code self-attention visualization — 60 min
4. Read one RAG paper section — 50 min

Then:
- Start timer
- Finish sessions
- Dashboard shows progress
- Evening review explains what changed tomorrow
```

## 11. Best MVP Name

For the MVP, do not call it “AI Life Execution System” in the UI. Too large.

Use something narrower:

```text
Execution Tracker
Daily Execution Coach
Study Execution Agent
Goal-to-Day Planner
```

My recommendation:

> **Daily Execution Coach**

It sounds realistic and matches the MVP scope.

## 12. Final MVP Definition

Your MVP should be:

> **A web app that reads or creates weekly goals, uses AI to generate a realistic daily plan, tracks study sessions with a timer, stores execution data, and shows basic progress statistics.**

Build that first. Everything else is Phase 2.

# MVP file catalog
ai-life-execution-system/
│
├── README.md
├── .gitignore
├── .env.example
├── docker-compose.yml
├── Makefile
│
├── frontend/
│   ├── package.json
│   ├── next.config.js
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   ├── postcss.config.js
│   ├── .env.local.example
│   │
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx
│   │   │
│   │   ├── dashboard/
│   │   │   └── page.tsx
│   │   │
│   │   ├── weekly-plan/
│   │   │   └── page.tsx
│   │   │
│   │   ├── today/
│   │   │   └── page.tsx
│   │   │
│   │   ├── timer/
│   │   │   └── page.tsx
│   │   │
│   │   ├── review/
│   │   │   └── page.tsx
│   │   │
│   │   └── login/
│   │       └── page.tsx
│   │
│   ├── components/
│   │   ├── layout/
│   │   │   ├── Navbar.tsx
│   │   │   ├── Sidebar.tsx
│   │   │   └── PageHeader.tsx
│   │   │
│   │   ├── dashboard/
│   │   │   ├── StatCard.tsx
│   │   │   ├── TodayProgress.tsx
│   │   │   ├── WeeklyProgress.tsx
│   │   │   └── FocusTimeChart.tsx
│   │   │
│   │   ├── planning/
│   │   │   ├── WeeklyGoalCard.tsx
│   │   │   ├── WeeklyGoalForm.tsx
│   │   │   ├── DailyTaskCard.tsx
│   │   │   └── GeneratePlanButton.tsx
│   │   │
│   │   ├── timer/
│   │   │   ├── StudyTimer.tsx
│   │   │   └── SessionSummary.tsx
│   │   │
│   │   └── common/
│   │       ├── Button.tsx
│   │       ├── Input.tsx
│   │       ├── Modal.tsx
│   │       └── Loading.tsx
│   │
│   ├── lib/
│   │   ├── api.ts
│   │   ├── auth.ts
│   │   ├── date.ts
│   │   └── utils.ts
│   │
│   ├── types/
│   │   ├── goal.ts
│   │   ├── task.ts
│   │   ├── session.ts
│   │   └── dashboard.ts
│   │
│   └── styles/
│       └── globals.css
│
├── backend/
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── alembic.ini
│   ├── .env.example
│   │
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── dependencies.py
│   │   │
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py
│   │   │   ├── weekly_goals.py
│   │   │   ├── daily_tasks.py
│   │   │   ├── study_sessions.py
│   │   │   ├── dashboard.py
│   │   │   ├── reviews.py
│   │   │   └── notion.py
│   │   │
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── user.py
│   │   │   ├── weekly_goal.py
│   │   │   ├── daily_task.py
│   │   │   ├── study_session.py
│   │   │   └── daily_review.py
│   │   │
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   ├── user.py
│   │   │   ├── weekly_goal.py
│   │   │   ├── daily_task.py
│   │   │   ├── study_session.py
│   │   │   ├── dashboard.py
│   │   │   └── review.py
│   │   │
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── auth_service.py
│   │   │   ├── planning_service.py
│   │   │   ├── timer_service.py
│   │   │   ├── stats_service.py
│   │   │   ├── review_service.py
│   │   │   ├── notion_service.py
│   │   │   └── llm_service.py
│   │   │
│   │   ├── prompts/
│   │   │   ├── daily_plan_prompt.txt
│   │   │   └── daily_review_prompt.txt
│   │   │
│   │   └── utils/
│   │       ├── date_utils.py
│   │       ├── errors.py
│   │       └── response.py
│   │
│   ├── migrations/
│   │   ├── env.py
│   │   └── versions/
│   │       └── 001_init_mvp_tables.py
│   │
│   └── tests/
│       ├── test_weekly_goals.py
│       ├── test_daily_tasks.py
│       ├── test_study_sessions.py
│       └── test_dashboard.py
│
├── docs/
│   ├── MVP_SCOPE.md
│   ├── API.md
│   ├── DATABASE_SCHEMA.md
│   ├── NOTION_INTEGRATION.md
│   └── PROMPTS.md
│
└── scripts/
    ├── init_db.py
    ├── seed_demo_data.py
    └── reset_db.py