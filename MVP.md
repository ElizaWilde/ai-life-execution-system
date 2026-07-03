AI Life Execution System MVP 
> A working personal execution tracker that turns a weekly plan into daily tasks, lets the user track study sessions, and shows whether the user is on track.
The  MVP product:
weekly planning
daily planning
study timer
study session recording
dashboard
basic statistics
basic AI daily planning and daily review

```
1. MVP Core Loop
Build only this loop first:
```text
User writes weekly goals
        ↓
System generates today's plan through Ollama Cloud
        ↓
User starts/stops study timer
        ↓
System records study sessions
        ↓
Dashboard shows progress
        ↓
User adjusts tomorrow
```
2. MVP Features: Keep / Cut
Must build
Feature	MVP version
Weekly plan	User creates weekly goals manually or imports from Notion
Daily plan	AI generates today’s tasks from weekly goals through Ollama Cloud
Study timer	Start / pause / stop
Session recording	Store subject, task, start time, end time, duration
Dashboard	Show today focus time, weekly progress, unfinished tasks
Basic AI	Generate daily plan + short evening summary using Ollama Cloud
Cut for MVP
Do not build these yet:
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
3. Minimal Architecture
Use this MVP architecture:
```text
Next.js frontend
        ↓
FastAPI backend in Docker
        ↓
PostgreSQL in Docker
        ↓
Notion API
        ↓
Ollama Cloud API
```
Important:
```text
Do not install Ollama inside the backend container.
Do not run local Ollama on the host machine.
Do not use http://host.docker.internal:11434.
Use https://ollama.com as the Ollama Cloud host.
```
Backend AI flow:
```text
frontend/app/today/page.tsx
        ↓
POST /daily-tasks/generate
        ↓
backend/app/services/planning_service.py
        ↓
backend/app/services/llm_service.py
        ↓
https://ollama.com/api/chat
        ↓
Ollama Cloud model
```
4. Required Ollama Cloud Setup
Before coding, prepare:
```text
1. Ollama account
2. Ollama API key
3. Cloud model access / subscription if the selected model requires it
4. Model ID, for example qwen3.5:cloud
```
If the API returns:
```text
403: this model requires a subscription
```
then the code is probably connecting correctly, but the account does not have access to that cloud model.
5. Environment Variables
Root `.env.example`
Use:
```env
DATABASE_URL=postgresql://postgres:postgres@postgres:5432/life_execution

OLLAMA_BASE_URL=https://ollama.com
OLLAMA_API_KEY=your_ollama_api_key
OLLAMA_MODEL=qwen3.5:cloud

NOTION_API_KEY=your_notion_api_key
NOTION_DATABASE_ID=your_notion_database_id
JWT_SECRET=your_jwt_secret
```
Backend `backend/.env.example`
Use:
```env
DATABASE_URL=postgresql://postgres:postgres@postgres:5432/life_execution

OLLAMA_BASE_URL=https://ollama.com
OLLAMA_API_KEY=your_ollama_api_key
OLLAMA_MODEL=qwen3.5:cloud

NOTION_API_KEY=your_notion_api_key
NOTION_DATABASE_ID=your_notion_database_id
JWT_SECRET=your_jwt_secret
```
Frontend `frontend/.env.local.example`
Use:
```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```
Important Rule
Commit these:
```text
.env.example
backend/.env.example
frontend/.env.local.example
```
Do not commit these:
```text
.env
backend/.env
frontend/.env.local
```
6. Docker Compose
Use Docker for backend, frontend, and PostgreSQL only.
```yaml
services:
  postgres:
    image: postgres:16
    container_name: life_execution_postgres
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: life_execution
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  backend:
    build: ./backend
    container_name: life_execution_backend
    env_file:
      - ./backend/.env
    ports:
      - "8000:8000"
    depends_on:
      - postgres

  frontend:
    build: ./frontend
    container_name: life_execution_frontend
    env_file:
      - ./frontend/.env.local
    ports:
      - "3000:3000"
    depends_on:
      - backend

volumes:
  postgres_data:
```
Do not add this for Ollama Cloud:
```yaml
extra_hosts:
  - "host.docker.internal:host-gateway"
```
That line is only needed when the backend container must reach a host-machine service such as local Ollama.
7. Backend Requirements
In `backend/requirements.txt`, use:
```txt
fastapi
uvicorn[standard]
sqlalchemy
alembic
psycopg2-binary
pydantic
pydantic-settings
python-dotenv
httpx
notion-client
pytest
```
Do not include:
```txt
openai
ollama
```
For this MVP, `httpx` is enough because the backend calls Ollama Cloud directly through HTTP.
8. Backend Config
Replace `backend/app/config.py` with:
```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str

    ollama_base_url: str = "https://ollama.com"
    ollama_api_key: str
    ollama_model: str = "qwen3.5:cloud"

    notion_api_key: str | None = None
    notion_database_id: str | None = None
    jwt_secret: str = "dev-secret"

    class Config:
        env_file = ".env"


settings = Settings()
```
9. Ollama Cloud LLM Service
Replace `backend/app/services/llm_service.py` with:
```python
import json
import httpx

from app.config import settings


class LLMService:
    def __init__(self):
        self.base_url = settings.ollama_base_url.rstrip("/")
        self.model = settings.ollama_model
        self.api_key = settings.ollama_api_key

    async def chat(self, system_prompt: str, user_prompt: str) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],
            "stream": False,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                f"{self.base_url}/api/chat",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()

        data = response.json()
        return data["message"]["content"]

    async def generate_daily_plan(
        self,
        weekly_goals: list[dict],
        unfinished_tasks: list[dict],
        available_minutes: int,
    ) -> list[dict]:
        system_prompt = """
You are a planning assistant.

Generate a realistic daily execution plan from weekly goals.

Rules:
- Do not overload the user.
- Prefer urgent unfinished tasks.
- Split large goals into small tasks.
- Each task must have title, estimated_minutes, and priority.
- Output JSON only.
"""

        user_prompt = f"""
Weekly goals:
{json.dumps(weekly_goals, ensure_ascii=False, indent=2)}

Unfinished tasks:
{json.dumps(unfinished_tasks, ensure_ascii=False, indent=2)}

Available minutes today:
{available_minutes}

Return JSON array only.
"""

        raw = await self.chat(system_prompt, user_prompt)

        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return [
                {
                    "title": "Review generated plan manually",
                    "estimated_minutes": 30,
                    "priority": "medium",
                    "raw_model_output": raw,
                }
            ]

    async def generate_daily_review(
        self,
        planned_tasks: list[dict],
        completed_tasks: list[dict],
        study_sessions: list[dict],
    ) -> str:
        system_prompt = """
You are a daily review assistant.

Write a short practical daily review.
Do not give generic motivation.
Focus on execution, unfinished work, and tomorrow's adjustment.
"""

        user_prompt = f"""
Planned tasks:
{json.dumps(planned_tasks, ensure_ascii=False, indent=2)}

Completed tasks:
{json.dumps(completed_tasks, ensure_ascii=False, indent=2)}

Study sessions:
{json.dumps(study_sessions, ensure_ascii=False, indent=2)}
"""

        return await self.chat(system_prompt, user_prompt)


llm_service = LLMService()
```
10. Test Ollama Cloud From Backend Container
Start Docker:
```bash
docker compose up --build
```
Enter backend container:
```bash
docker exec -it life_execution_backend bash
```
Run:
```bash
python - << "EOF"
import os
import httpx

api_key = os.environ["OLLAMA_API_KEY"]
model = os.environ.get("OLLAMA_MODEL", "qwen3.5:cloud")
base_url = os.environ.get("OLLAMA_BASE_URL", "https://ollama.com").rstrip("/")

response = httpx.post(
    f"{base_url}/api/chat",
    headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    },
    json={
        "model": model,
        "messages": [
            {"role": "user", "content": "Say OK only"}
        ],
        "stream": False,
    },
    timeout=120,
)

print(response.status_code)
print(response.text)
EOF
```
Expected success:
```text
200
...
OK
...
```
Possible errors:
Error	Meaning	Fix
`401 Unauthorized`	API key missing or invalid	Check `OLLAMA_API_KEY`
`403 subscription required`	Model requires paid cloud access	Upgrade/change model
`404 model not found`	Wrong model ID	Check model name from Ollama model library
timeout	Network or model issue	Retry or use smaller/faster cloud model
11. AI Feature for MVP
Use one function first:
```text
generate_daily_plan(weekly_goals, unfinished_tasks, available_minutes)
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
The backend should call:
```text
POST https://ollama.com/api/chat
Authorization: Bearer $OLLAMA_API_KEY
```
12. API Endpoints
Build these first:
```text
POST /weekly-goals
GET  /weekly-goals/current

POST /daily-tasks/generate
GET  /daily-tasks/today
PATCH /daily-tasks/{id}

POST /study-sessions/start
POST /study-sessions/finish
GET  /study-sessions/today

GET  /dashboard/today
GET  /dashboard/week

POST /reviews/generate
GET  /reviews/today
```
Do not add natural-language command API yet.
13. MVP Development Order
Step 1 — Docker full-stack skeleton
Build:
```text
Next.js frontend
FastAPI backend
PostgreSQL
Docker Compose
```
Do not touch AI yet.
Step 2 — Weekly goals CRUD
Success condition:
```text
I can create this week’s goals and see them on the page.
```
Step 3 — Daily task system
Success condition:
```text
I can create today’s task and mark it completed.
```
Step 4 — Timer + session recording
Success condition:
```text
I can study for 25 minutes and the system records it.
```
Step 5 — Dashboard
Success condition:
```text
I can see today’s focus time, weekly focus time, and task completion rate.
```
Step 6 — Ollama Cloud connection test
Success condition:
```text
The backend container can call https://ollama.com/api/chat and receive a model response.
```
Step 7 — AI daily plan
Success condition:
```text
I click “Generate Today’s Plan” and get realistic tasks from Ollama Cloud.
```
Step 8 — AI daily review
Success condition:
```text
I click “Generate Review” and get a short practical review from Ollama Cloud.
```
Step 9 — Notion integration
Success condition:
```text
The system can read my Notion weekly plan or write a weekly review page.
```
14. MVP Acceptance Criteria
Your MVP is done when this works:
```text
1. User logs in.
2. User creates weekly goals.
3. User clicks "Generate Today’s Plan."
4. Backend container calls Ollama Cloud.
5. System creates 3–5 tasks.
6. User starts a task timer.
7. User stops the timer.
8. System records the study session.
9. Dashboard updates focus time and completion rate.
10. AI generates a short daily review through Ollama Cloud.
```
15. MVP File Catalog
```text
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
│   │   ├── dashboard/page.tsx
│   │   ├── weekly-plan/page.tsx
│   │   ├── today/page.tsx
│   │   ├── timer/page.tsx
│   │   ├── review/page.tsx
│   │   └── login/page.tsx
│   │
│   ├── components/
│   ├── lib/
│   ├── types/
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
│   │   ├── api/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── services/
│   │   │   └── llm_service.py
│   │   ├── prompts/
│   │   └── utils/
│   │
│   ├── migrations/
│   └── tests/
│
├── docs/
│   ├── MVP_SCOPE.md
│   ├── API.md
│   ├── DATABASE_SCHEMA.md
│   ├── NOTION_INTEGRATION.md
│   ├── PROMPTS.md
│   └── OLLAMA_CLOUD_DOCKER.md
│
└── scripts/
    ├── init_db.py
    ├── seed_demo_data.py
    └── reset_db.py
```
16. Add This Extra Docs File
Create:
```text
docs/OLLAMA_CLOUD_DOCKER.md
```
Content:
```markdown
# Ollama Cloud + Docker Setup

The backend runs in Docker and calls Ollama Cloud directly.

## Environment

backend/.env:

```env
OLLAMA_BASE_URL=https://ollama.com
OLLAMA_API_KEY=your_ollama_api_key
OLLAMA_MODEL=qwen3.5:cloud
```
Important
Do not use:
```env
OLLAMA_BASE_URL=http://host.docker.internal:11434
```
That value is only for local Ollama running on the host machine.
Test
```bash
docker exec -it life_execution_backend bash
python - << "EOF"
import os, httpx

response = httpx.post(
    "https://ollama.com/api/chat",
    headers={"Authorization": "Bearer " + os.environ["OLLAMA_API_KEY"]},
    json={
        "model": os.environ["OLLAMA_MODEL"],
        "messages": [{"role": "user", "content": "Say OK only"}],
        "stream": False,
    },
    timeout=120,
)

print(response.status_code)
print(response.text)
EOF
```
```

## 17. Final MVP Definition

Your MVP should be:

> A Dockerized web app that reads or creates weekly goals, uses Ollama Cloud to generate a realistic daily plan, tracks study sessions with a timer, stores execution data in PostgreSQL, and shows basic progress statistics.

Build that first. Everything else is Phase 2.