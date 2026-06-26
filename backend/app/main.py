from fastapi import FastAPI

from app.api import (
    weekly_goals,
    daily_tasks,
    study_sessions,
    dashboard,
    reviews,
    notion,
)

app = FastAPI(title="AI Life Execution System MVP")

app.include_router(weekly_goals.router, prefix="/weekly-goals", tags=["Weekly Goals"])
app.include_router(daily_tasks.router, prefix="/daily-tasks", tags=["Daily Tasks"])
app.include_router(study_sessions.router, prefix="/study-sessions", tags=["Study Sessions"])
app.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])
app.include_router(reviews.router, prefix="/reviews", tags=["Reviews"])
app.include_router(notion.router, prefix="/notion", tags=["Notion"])


@app.get("/")
def root():
    return {"message": "AI Life Execution System MVP API"}
