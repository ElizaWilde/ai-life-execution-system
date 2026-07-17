'''
    FastAPI officially describes `APIRouter` as a way to organize related path operations in separate modules and then include them in the main application.
    e.g. `main.py` creates the complete FastAPI application.`daily_tasks.py` defines the daily-task routes.
'''
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    automation_preferences,
    check_ins,
    coaching,
    coordinator,
    daily_tasks,
    dashboard,
    notion,
    notifications,
    reviews,
    study_sessions,
    users,
    user_app_settings,
    weekly_goals,
    weekly_reviews,
)

# This creates the main web application.
app = FastAPI(title="AI Life Execution System MVP")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(coordinator.router, prefix="/coordinator", tags=["Coordinator Agent"])
app.include_router(
    automation_preferences.router,
    prefix="/automation-preferences",
    tags=["Automation Preferences"],
)
app.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])
app.include_router(check_ins.router, prefix="/check-ins", tags=["Check-ins"])
app.include_router(coaching.router, prefix="/coaching", tags=["Coaching"])
app.include_router(reviews.router, prefix="/reviews", tags=["Reviews"])
app.include_router(notion.router, prefix="/notion", tags=["Notion"])
app.include_router(notifications.router, prefix="/notifications", tags=["Notifications"])
app.include_router(users.router, prefix="/users", tags=["Users"])
app.include_router(user_app_settings.router, prefix="/app-settings", tags=["App Settings"])
app.include_router(weekly_goals.router, prefix="/weekly-goals", tags=["Weekly Goals"])
app.include_router(
    weekly_reviews.router,
    prefix="/weekly-reviews",
    tags=["Weekly Reviews"],
)

# adds all routes from daily_tasks.router into app
app.include_router(daily_tasks.router, prefix="/daily-tasks", tags=["Daily Tasks"])
app.include_router(
    study_sessions.router,
    prefix="/study-sessions",
    tags=["Study Sessions"],
)


@app.get("/")
def root():
    return {"message": "AI Life Execution System MVP API"}


@app.get("/health")
def health():
    return {"status": "ok"}
