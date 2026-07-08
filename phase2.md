# Next Phase: Phase 2 — AI Coaching

Your project specification defines Phase 2 as:

* Daily check-ins
* Energy, mood, and sleep tracking
* Optional menstrual-cycle tracking
* Personalized recommendations
* AI-generated weekly summaries
* Adaptive planning based on the user’s condition 

Do not start with LangGraph, pgvector, reminders, or automatic scheduling yet. Those belong mainly to Phases 3 and 4. Phase 2 should first create this pipeline:

```text
Daily check-in
      ↓
Collect recent behavior and progress
      ↓
Calculate workload adjustment
      ↓
Ask cloud Ollama for coaching advice
      ↓
Save recommendation
      ↓
Use adjustment when generating the daily plan
      ↓
Generate weekly review
```

---

# Recommended Phase 2 backend structure

```text
backend/
├── alembic/
│   └── versions/
│       └── xxxx_add_phase_2_coaching_tables.py
│
├── app/
│   ├── api/
│   │   ├── check_ins.py
│   │   ├── coaching.py
│   │   └── weekly_reviews.py
│   │
│   ├── models/
│   │   ├── daily_check_in.py
│   │   ├── coaching_recommendation.py
│   │   └── weekly_review.py
│   │
│   ├── schemas/
│   │   ├── daily_check_in.py
│   │   ├── coaching.py
│   │   └── weekly_review.py
│   │
│   ├── services/
│   │   ├── check_in_service.py
│   │   ├── coaching_context_service.py
│   │   ├── workload_adjustment_service.py
│   │   ├── coaching_service.py
│   │   └── weekly_review_service.py
│   │
│   ├── prompts/
│   │   ├── coaching_prompt.py
│   │   └── weekly_review_prompt.py
│   │
│   ├── config.py
│   ├── main.py
│   └── models.py or models/__init__.py
│
└── tests/
    ├── test_check_ins.py
    ├── test_workload_adjustment.py
    ├── test_coaching.py
    └── test_weekly_reviews.py
```

You can keep your current project structure. The important point is separating:

```text
Router → Service → Database / LLM
```

---

# Step 1 — Define the DailyCheckIn database model

Create:

```text
app/models/daily_check_in.py
```

Recommended fields:

```python
from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DailyCheckIn(Base):
    __tablename__ = "daily_check_ins"

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "check_in_date",
            name="uq_daily_check_ins_user_date",
        ),
        CheckConstraint(
            "energy_level BETWEEN 1 AND 5",
            name="ck_daily_check_ins_energy",
        ),
        CheckConstraint(
            "mood_level BETWEEN 1 AND 5",
            name="ck_daily_check_ins_mood",
        ),
        CheckConstraint(
            "sleep_hours >= 0 AND sleep_hours <= 24",
            name="ck_daily_check_ins_sleep",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )

    check_in_date: Mapped[date] = mapped_column(Date, index=True)

    energy_level: Mapped[int]
    mood_level: Mapped[int]
    sleep_hours: Mapped[float]

    stress_level: Mapped[int | None]
    notes: Mapped[str | None] = mapped_column(Text)

    cycle_day: Mapped[int | None]
    cycle_notes: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)

    user: Mapped["User"] = relationship(back_populates="daily_check_ins")
```

Add the relationship to `User`:

```python
daily_check_ins: Mapped[list["DailyCheckIn"]] = relationship(
    back_populates="user",
    cascade="all, delete-orphan",
)
```

## Important decision

Cycle-related fields should be:

* Optional
* Nullable
* Excluded from the prompt when no value is provided
* Never required for generating a plan

Phase 2 coaching must still work without them.

## Completion condition

This step is complete when:

* One user can have multiple check-ins.
* One user can only have one check-in per date.
* Invalid energy, mood, or sleep values are rejected by the database.

---

# Step 2 — Create the check-in schemas

Create:

```text
app/schemas/daily_check_in.py
```

```python
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class DailyCheckInCreate(BaseModel):
    check_in_date: date | None = None

    energy_level: int = Field(ge=1, le=5)
    mood_level: int = Field(ge=1, le=5)
    sleep_hours: float = Field(ge=0, le=24)

    stress_level: int | None = Field(default=None, ge=1, le=5)
    notes: str | None = Field(default=None, max_length=2000)

    cycle_day: int | None = Field(default=None, ge=1, le=100)
    cycle_notes: str | None = Field(default=None, max_length=1000)


class DailyCheckInUpdate(BaseModel):
    energy_level: int | None = Field(default=None, ge=1, le=5)
    mood_level: int | None = Field(default=None, ge=1, le=5)
    sleep_hours: float | None = Field(default=None, ge=0, le=24)

    stress_level: int | None = Field(default=None, ge=1, le=5)
    notes: str | None = Field(default=None, max_length=2000)

    cycle_day: int | None = Field(default=None, ge=1, le=100)
    cycle_notes: str | None = Field(default=None, max_length=1000)


class DailyCheckInRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    check_in_date: date
    energy_level: int
    mood_level: int
    sleep_hours: float
    stress_level: int | None
    notes: str | None
    cycle_day: int | None
    cycle_notes: str | None
    created_at: datetime
    updated_at: datetime
```

## Completion condition

Pydantic must reject requests such as:

```json
{
  "energy_level": 9,
  "mood_level": 0,
  "sleep_hours": -2
}
```

---

# Step 3 — Implement Daily Check-in CRUD

Create:

```text
app/services/check_in_service.py
app/api/check_ins.py
```

Required endpoints:

```text
POST   /check-ins
GET    /check-ins/today
GET    /check-ins/{check_in_date}
PATCH  /check-ins/{check_in_date}
GET    /check-ins?start_date=...&end_date=...
```

Recommended behavior for `POST /check-ins`:

```text
1. Get the authenticated user.
2. Use payload.check_in_date or today.
3. Check whether the user already has a check-in for that date.
4. Create the check-in.
5. Commit and refresh.
6. Return the saved record.
```

Service method examples:

```python
class CheckInService:
    def create_check_in(
        self,
        db: Session,
        user_id: int,
        payload: DailyCheckInCreate,
    ) -> DailyCheckIn:
        ...

    def get_check_in(
        self,
        db: Session,
        user_id: int,
        check_in_date: date,
    ) -> DailyCheckIn | None:
        ...

    def list_check_ins(
        self,
        db: Session,
        user_id: int,
        start_date: date,
        end_date: date,
    ) -> list[DailyCheckIn]:
        ...

    def update_check_in(
        self,
        db: Session,
        user_id: int,
        check_in_date: date,
        payload: DailyCheckInUpdate,
    ) -> DailyCheckIn:
        ...
```

Register the router in `main.py`:

```python
app.include_router(
    check_ins.router,
    prefix="/check-ins",
    tags=["check-ins"],
)
```

## Completion condition

The authenticated user can:

* Create today’s check-in.
* Read it.
* Update it.
* List recent check-ins.
* Never access another user’s check-ins.

---

# Step 4 — Create the CoachingRecommendation model

Create:

```text
app/models/coaching_recommendation.py
```

This stores the output from the coaching system.

Recommended fields:

```python
class CoachingRecommendation(Base):
    __tablename__ = "coaching_recommendations"

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )

    recommendation_date: Mapped[date] = mapped_column(Date, index=True)

    readiness_score: Mapped[float]
    workload_multiplier: Mapped[float]

    summary: Mapped[str] = mapped_column(Text)
    recommendations_json: Mapped[dict] = mapped_column(JSON)

    model_name: Mapped[str | None]
    prompt_version: Mapped[str | None]

    created_at: Mapped[datetime]
```

Example `recommendations_json`:

```json
{
  "workload": "reduced",
  "suggestions": [
    "Complete one high-priority task first.",
    "Use two 25-minute focus sessions.",
    "Move optional tasks to tomorrow."
  ],
  "risk_factors": [
    "low sleep",
    "high stress"
  ]
}
```

## Why save recommendations?

Without storing them:

* You cannot inspect previous recommendations.
* You cannot evaluate whether coaching helped.
* You cannot generate accurate weekly reviews.
* The same request may produce different advice every time.

## Completion condition

Each generated recommendation is associated with:

* One user
* One date
* The calculated workload adjustment
* The cloud Ollama model used
* The generated advice

---

# Step 5 — Build the coaching context service

Create:

```text
app/services/coaching_context_service.py
```

This service should collect all data needed for coaching.

It should not call the LLM. It only gathers structured data.

```python
class CoachingContextService:
    def build_daily_context(
        self,
        db: Session,
        user_id: int,
        target_date: date,
    ) -> CoachingContext:
        ...
```

Collect:

```text
Today:
- Energy
- Mood
- Sleep
- Stress
- User notes

Recent behavior:
- Last 7 days of check-ins
- Last 7 days of study sessions
- Recent focus minutes
- Task completion rate
- Number of unfinished tasks

Planning:
- Current weekly goals
- Today’s tasks
- Available minutes
- Deadlines
```

Create an internal schema:

```text
app/schemas/coaching.py
```

```python
class CoachingContext(BaseModel):
    target_date: date

    energy_level: int | None
    mood_level: int | None
    sleep_hours: float | None
    stress_level: int | None

    planned_tasks: int
    completed_tasks: int
    unfinished_tasks: int

    recent_focus_minutes: int
    recent_completion_rate: float

    available_minutes: int | None
    high_priority_tasks: list[str]
    user_notes: str | None
```

## Completion condition

Given a `user_id` and date, this service returns one complete structured context object without invoking Ollama.

---

# Step 6 — Implement deterministic workload adjustment

Create:

```text
app/services/workload_adjustment_service.py
```

Do not let the LLM independently decide all workload values. Calculate the main adjustment in Python.

Example output:

```python
class WorkloadAdjustment(BaseModel):
    readiness_score: float
    workload_multiplier: float
    workload_level: str
    reasons: list[str]
```

Example rules:

```python
class WorkloadAdjustmentService:
    def calculate(
        self,
        context: CoachingContext,
    ) -> WorkloadAdjustment:
        score = 100.0
        reasons: list[str] = []

        if context.sleep_hours is not None:
            if context.sleep_hours < 5:
                score -= 30
                reasons.append("Very low sleep")
            elif context.sleep_hours < 7:
                score -= 15
                reasons.append("Insufficient sleep")

        if context.energy_level is not None:
            if context.energy_level <= 2:
                score -= 25
                reasons.append("Low energy")
            elif context.energy_level == 3:
                score -= 10
                reasons.append("Moderate energy")

        if context.stress_level is not None and context.stress_level >= 4:
            score -= 15
            reasons.append("High stress")

        if context.recent_completion_rate < 0.5:
            score -= 10
            reasons.append("Low recent completion rate")

        score = max(0.0, min(score, 100.0))

        if score >= 75:
            multiplier = 1.0
            level = "normal"
        elif score >= 50:
            multiplier = 0.8
            level = "reduced"
        else:
            multiplier = 0.6
            level = "light"

        return WorkloadAdjustment(
            readiness_score=score,
            workload_multiplier=multiplier,
            workload_level=level,
            reasons=reasons,
        )
```

This is only a starting rule set. It can later be calibrated using actual user history.

## Why separate this from the LLM?

The Python service provides:

* Repeatable decisions
* Testable logic
* Predictable workload limits
* Protection against malformed LLM advice

Ollama should explain and personalize the result, not silently control every numerical decision.

## Completion condition

The adjustment calculation works without internet access or an LLM.

---

# Step 7 — Create the coaching prompt

Create:

```text
app/prompts/coaching_prompt.py
```

Keep the system prompt versioned.

```python
COACHING_PROMPT_VERSION = "phase2-v1"

COACHING_SYSTEM_PROMPT = """
You are a personal execution coach.

Use the supplied behavioral and planning data to provide practical,
specific, and concise recommendations.

Rules:
1. Do not provide medical diagnoses.
2. Do not invent facts that are not present in the context.
3. Respect the calculated workload level.
4. Prioritize important tasks over optional tasks.
5. Return valid JSON only.

Required JSON structure:
{
  "summary": "string",
  "suggestions": ["string"],
  "risk_factors": ["string"],
  "planning_changes": ["string"]
}
"""
```

User prompt:

```python
def build_coaching_user_prompt(
    context: CoachingContext,
    adjustment: WorkloadAdjustment,
) -> str:
    return f"""
User context:
{context.model_dump_json(indent=2)}

Calculated workload adjustment:
{adjustment.model_dump_json(indent=2)}

Generate today's personalized coaching recommendation.
"""
```

## Completion condition

The prompt:

* Includes structured context.
* Includes the deterministic adjustment.
* Requests JSON.
* Does not require the LLM to calculate database statistics.

---

# Step 8 — Extend the cloud Ollama service

Reuse your existing:

```text
app/services/llm_service.py
```

Do not create a second HTTP implementation specifically for coaching.

Add a method similar to:

```python
async def generate_json(
    self,
    system_prompt: str,
    user_prompt: str,
) -> dict:
    ...
```

Expected responsibilities:

```text
1. Send request to your cloud Ollama endpoint.
2. Set the configured cloud model.
3. Request JSON-formatted output where supported.
4. Apply a timeout.
5. Detect non-200 responses.
6. Parse the returned JSON.
7. Raise a controlled application exception for invalid JSON.
```

Your environment configuration remains centralized:

```text
app/config.py
.env
docker-compose.yml
```

For example:

```env
OLLAMA_BASE_URL=https://ollama.com
OLLAMA_MODEL=qwen3.5:cloud
OLLAMA_API_KEY=...
OLLAMA_TIMEOUT_SECONDS=60
```

The exact authentication fields should match your already working cloud Ollama implementation.

## Completion condition

The existing LLM service can return a validated Python dictionary instead of unstructured text only.

---

# Step 9 — Implement CoachingService

Create:

```text
app/services/coaching_service.py
```

This is the main orchestration service for Phase 2.

```python
class CoachingService:
    async def generate_daily_recommendation(
        self,
        db: Session,
        user_id: int,
        target_date: date,
    ) -> CoachingRecommendationRead:
        ...
```

Internal flow:

```text
1. Load the daily coaching context.
2. Calculate deterministic workload adjustment.
3. Build the coaching prompt.
4. Call cloud Ollama.
5. Validate the LLM response.
6. Save CoachingRecommendation.
7. Commit.
8. Return the response.
```

Pseudo-code:

```python
async def generate_daily_recommendation(
    self,
    db: Session,
    user_id: int,
    target_date: date,
) -> CoachingRecommendationRead:
    context = coaching_context_service.build_daily_context(
        db=db,
        user_id=user_id,
        target_date=target_date,
    )

    adjustment = workload_adjustment_service.calculate(context)

    llm_result = await llm_service.generate_json(
        system_prompt=COACHING_SYSTEM_PROMPT,
        user_prompt=build_coaching_user_prompt(
            context=context,
            adjustment=adjustment,
        ),
    )

    recommendation = CoachingRecommendation(
        user_id=user_id,
        recommendation_date=target_date,
        readiness_score=adjustment.readiness_score,
        workload_multiplier=adjustment.workload_multiplier,
        summary=llm_result["summary"],
        recommendations_json=llm_result,
        model_name=settings.ollama_model,
        prompt_version=COACHING_PROMPT_VERSION,
    )

    db.add(recommendation)
    db.commit()
    db.refresh(recommendation)

    return CoachingRecommendationRead.model_validate(recommendation)
```

## Important transaction rule

Do not keep the database transaction open while waiting for the cloud LLM longer than necessary.

Prefer:

```text
Read context
→ Call LLM
→ Open short write transaction
→ Save result
```

## Completion condition

A single service call produces and stores a complete recommendation.

---

# Step 10 — Add coaching APIs

Create:

```text
app/api/coaching.py
```

Endpoints:

```text
POST /coaching/daily/generate
GET  /coaching/daily
GET  /coaching/history
```

Example request:

```json
{
  "target_date": "2026-07-08"
}
```

Example response:

```json
{
  "recommendation_date": "2026-07-08",
  "readiness_score": 62,
  "workload_multiplier": 0.8,
  "workload_level": "reduced",
  "summary": "Use a reduced workload today and focus on one important task.",
  "suggestions": [
    "Complete the database migration first.",
    "Use two focused work blocks.",
    "Move optional documentation work to tomorrow."
  ],
  "risk_factors": [
    "insufficient sleep",
    "low recent completion rate"
  ]
}
```

Register in `main.py`:

```python
app.include_router(
    coaching.router,
    prefix="/coaching",
    tags=["coaching"],
)
```

## Completion condition

A logged-in user can generate and retrieve their own coaching recommendation.

---

# Step 11 — Connect coaching to daily plan generation

Modify your existing:

```text
app/services/planning_service.py
```

Currently, your method is approximately:

```python
async def generate_daily_plan(
    db: Session,
    user_id: int,
    available_minutes: int,
    task_date: date,
) -> DailyPlanResponse:
    ...
```

Add coaching adjustment before selecting tasks:

```python
adjustment = workload_adjustment_service.calculate(context)

adjusted_minutes = int(
    available_minutes * adjustment.workload_multiplier
)
```

Example:

```text
User available time: 240 minutes
Workload multiplier: 0.8
Adjusted planning capacity: 192 minutes
```

Then generate tasks using `adjusted_minutes`.

The daily-plan response should include:

```python
class DailyPlanResponse(BaseModel):
    task_date: date
    original_available_minutes: int
    adjusted_available_minutes: int
    workload_level: str
    readiness_score: float
    tasks: list[DailyTaskRead]
```

## Important rule

Do not automatically delete existing tasks when workload is reduced.

Instead:

```text
Keep mandatory/high-priority tasks
Reduce optional tasks
Move overflow tasks to an unplanned or deferred state
Explain what changed
```

## Completion condition

The same weekly goals produce different daily workloads depending on the user’s current condition.

That is the main Phase 2 adaptation feature.

---

# Step 12 — Implement weekly review generation

Create:

```text
app/models/weekly_review.py
app/schemas/weekly_review.py
app/services/weekly_review_service.py
app/prompts/weekly_review_prompt.py
app/api/weekly_reviews.py
```

If your existing `DailyReview` model can support this, keep daily and weekly reviews separate because their data ranges and semantics differ.

Recommended weekly review fields:

```python
class WeeklyReview(Base):
    __tablename__ = "weekly_reviews"

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )

    week_start: Mapped[date] = mapped_column(Date, index=True)
    week_end: Mapped[date] = mapped_column(Date)

    planned_tasks: Mapped[int]
    completed_tasks: Mapped[int]
    completion_rate: Mapped[float]
    focus_minutes: Mapped[int]

    average_energy: Mapped[float | None]
    average_mood: Mapped[float | None]
    average_sleep_hours: Mapped[float | None]

    summary: Mapped[str] = mapped_column(Text)
    achievements_json: Mapped[list] = mapped_column(JSON)
    obstacles_json: Mapped[list] = mapped_column(JSON)
    next_week_actions_json: Mapped[list] = mapped_column(JSON)

    model_name: Mapped[str | None]
    prompt_version: Mapped[str | None]
```

Weekly service flow:

```text
1. Determine week start and week end.
2. Query tasks completed during the week.
3. Query study sessions.
4. Query daily check-ins.
5. Calculate statistics in Python.
6. Send calculated statistics to Ollama.
7. Generate achievements, obstacles, and adjustments.
8. Save the review.
```

Endpoints:

```text
POST /weekly-reviews/generate
GET  /weekly-reviews/current
GET  /weekly-reviews/{week_start}
GET  /weekly-reviews
```

For Phase 2, generate the review manually through an API. Automatic Sunday generation belongs to Phase 3 because that requires proactive scheduling.

## Completion condition

The system can generate a review based on actual stored behavior instead of asking the LLM to guess what happened.

---

# Step 13 — Create the Alembic migration

After importing all new models into the Alembic metadata, run:

```bash
docker compose exec backend alembic revision --autogenerate -m "add phase 2 coaching models"
```

Inspect the migration before applying it.

Then run:

```bash
docker compose exec backend alembic upgrade head
```

The migration should create:

```text
daily_check_ins
coaching_recommendations
weekly_reviews
```

It should also create:

* Foreign keys
* User/date indexes
* Unique constraints
* Check constraints

Verify:

```bash
docker compose exec backend alembic current
docker compose exec backend alembic history
```

## Completion condition

A completely empty PostgreSQL database can be upgraded from the first migration to `head` without manual SQL.

---

# Step 14 — Add tests in implementation order

## `tests/test_check_ins.py`

Test:

```text
Create check-in
Reject invalid values
Reject duplicate date
Read own check-in
Cannot read another user’s check-in
Update check-in
List date range
```

## `tests/test_workload_adjustment.py`

Test deterministic cases:

```text
Normal sleep + high energy → normal workload
Low sleep → reduced workload
Low energy + high stress → light workload
Score never below zero
Score never above 100
```

This service should have the strongest unit-test coverage because it controls actual workload.

## `tests/test_coaching.py`

Mock the cloud Ollama response.

Test:

```text
Context is collected correctly
Valid LLM JSON is saved
Invalid JSON produces controlled error
Ollama timeout produces controlled error
Recommendation belongs to current user
```

Do not make real cloud API calls in normal tests.

## `tests/test_weekly_reviews.py`

Test:

```text
Statistics are calculated correctly
Empty week is handled
Missing check-ins are allowed
Review is saved
Review cannot access another user’s data
```

## Completion condition

Run:

```bash
docker compose exec backend pytest
```

All MVP and Phase 2 tests must pass.

---

# Step 15 — Add failure handling

Create application-specific exceptions, for example:

```text
app/exceptions.py
```

```python
class LLMServiceError(Exception):
    pass


class LLMTimeoutError(LLMServiceError):
    pass


class LLMInvalidResponseError(LLMServiceError):
    pass
```

Recommended API behavior:

```text
Cloud Ollama timeout       → 503 Service Unavailable
Invalid LLM JSON           → 502 Bad Gateway
Missing daily check-in     → either 400 or use neutral defaults
Duplicate check-in         → 409 Conflict
Requested review not found → 404 Not Found
```

The application should still provide a deterministic adjustment when Ollama fails.

Example fallback:

```python
{
    "summary": "The AI coaching service is temporarily unavailable.",
    "suggestions": adjustment.reasons,
    "planning_changes": [
        f"Use the {adjustment.workload_level} workload setting."
    ]
}
```

This prevents the entire daily planning system from failing because of the cloud model.

---

# Step 16 — Update the dashboard API

Modify your existing dashboard response.

Possible schema:

```python
class TodayDashboardResponse(BaseModel):
    date: date
    tasks: list[DailyTaskRead]
    statistics: TodayStatistics

    check_in: DailyCheckInRead | None
    coaching: CoachingRecommendationRead | None

    readiness_score: float | None
    workload_level: str | None
```

The dashboard should answer:

```text
How do I feel today?
What should I do today?
Why is today’s workload higher or lower?
What recommendation did the AI provide?
```

Do not make the dashboard endpoint call Ollama automatically. It should read existing data. Generation should happen through explicit generation endpoints.

---

# Step 17 — Add a minimal frontend flow

The Phase 2 frontend only needs four new areas.

## Daily check-in form

Fields:

```text
Energy: 1–5
Mood: 1–5
Sleep hours
Stress: 1–5
Optional notes
Optional cycle information
```

## Coaching card

Display:

```text
Readiness score
Workload level
Summary
Suggestions
Planning changes
```

## Adjusted daily plan

Display:

```text
Original available time
Adjusted available time
Tasks kept
Tasks deferred
Reason for adjustment
```

## Weekly review page

Display:

```text
Completion rate
Total focus time
Average energy
Average sleep
Achievements
Obstacles
Next-week adjustments
```

Do not build advanced charts until these data flows work correctly.

---

# Correct implementation order

Follow this order exactly:

```text
1. DailyCheckIn model
2. DailyCheckIn schemas
3. Alembic migration
4. Check-in CRUD service and API
5. Check-in tests
6. Coaching context service
7. Deterministic workload adjustment
8. Workload adjustment tests
9. CoachingRecommendation model
10. Coaching prompts
11. Extend existing cloud Ollama service
12. CoachingService
13. Coaching APIs
14. Coaching tests with mocked Ollama
15. Integrate adjustment into PlanningService
16. WeeklyReview model
17. Weekly review statistics service
18. Weekly review LLM generation
19. Weekly review APIs and tests
20. Dashboard integration
21. Minimal frontend
```

---

# Features that should not be implemented in Phase 2

Keep these for later phases:

```text
APScheduler reminders
Telegram notifications
Automatic task rescheduling without user action
Procrastination detection
Completion-probability prediction
Natural-language command routing
LangGraph multi-agent orchestration
pgvector semantic memory
Google Calendar synchronization
Wearable integration
```

Adding these now would mix Phase 2 with Phases 3 and 4 and make debugging much harder.

---

# Phase 2 final acceptance checklist

Phase 2 is finished when this complete workflow works:

```text
1. User logs in.
2. User submits a daily check-in.
3. Backend stores energy, mood, sleep, stress, and optional notes.
4. Backend gathers recent tasks and study history.
5. Python calculates readiness and workload multiplier.
6. Cloud Ollama generates personalized coaching text.
7. Backend validates and stores the recommendation.
8. Daily planning uses the workload multiplier.
9. Dashboard displays the check-in, adjusted plan, and recommendation.
10. User generates a weekly review.
11. Weekly statistics are calculated from PostgreSQL.
12. Cloud Ollama explains patterns and proposes next-week adjustments.
13. All functions enforce user ownership.
14. All database changes are reproducible through Alembic.
15. Tests use mocked Ollama responses and pass inside Docker.
```

The central Phase 2 deliverable is not simply an LLM chat endpoint. It is this closed loop:

```text
User condition
→ behavioral evidence
→ deterministic adjustment
→ AI explanation
→ changed daily plan
→ stored outcome
→ weekly analysis
```
