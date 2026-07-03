from fastapi import FastAPI

from app.api import coordinator

app = FastAPI(title="AI Life Execution System MVP")

app.include_router(coordinator.router, prefix="/coordinator", tags=["Coordinator Agent"])


@app.get("/")
def root():
    return {"message": "AI Life Execution System MVP API"}


@app.get("/health")
def health():
    return {"status": "ok"}
