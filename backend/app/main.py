'''
    FastAPI officially describes `APIRouter` as a way to organize related path operations in separate modules and then include them in the main application.
    e.g. `main.py` creates the complete FastAPI application.`daily_tasks.py` defines the daily-task routes.
'''
from fastapi import FastAPI

from app.api import coordinator, daily_tasks, dashboard, study_sessions, weekly_goals

# This creates the main web application.
app = FastAPI(title="AI Life Execution System MVP")

app.include_router(coordinator.router, prefix="/coordinator", tags=["Coordinator Agent"])
app.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])
app.include_router(weekly_goals.router, prefix="/weekly-goals", tags=["Weekly Goals"])

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
