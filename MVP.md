Below is the correct MVP build order for your current design:

```text id="r1olk7"
Next.js frontend
        ↓
FastAPI backend in Docker
        ↓
PostgreSQL in Docker
        ↓
Ollama Cloud API
        ↓
Notion API
```

Your MVP should still stay narrow: weekly goals, daily tasks, study timer, study sessions, dashboard, basic statistics, AI daily plan, and AI daily review. Your own MVP doc says this should be a working execution tracker, not the full life operating system. 

---

# Step 1 — Prepare accounts and tools

Install:

```text id="sfhodh"
Docker Desktop
Git
Python 3.12
Node.js 20+
VS Code
```

For Ollama Cloud, you **do not** need:
S
```text id="pqk3al"
ollama pull qwen2.5:3b
ollama serve
http://host.docker.internal:11434
```

Instead, create an Ollama API key. Ollama’s Cloud docs say direct access to `ollama.com` requires an API key, and the authentication docs say Ollama Cloud API access is served at `https://ollama.com/api`. ([Ollama][1])

Also verify which cloud models your account can use:

```bash id="p1f6rv"
curl https://ollama.com/api/tags \
  -H "Authorization: Bearer YOUR_OLLAMA_API_KEY"
```

Use the model you can actually access. For your previous plan:

```env id="y70i8q"
OLLAMA_MODEL=qwen3.5:cloud
```

If you get `403`, your account does not have access to that model or subscription level.

---

# Step 2 — Generate or keep the MVP catalog

Your file catalog is okay. Keep this structure:

```text id="3b1bvp"
ai-life-execution-system/
├── frontend/
├── backend/
├── docs/
├── scripts/
├── docker-compose.yml
├── .env.example
└── README.md
```

The backend should contain:

```text id="cj8whf"
backend/app/api/
backend/app/models/
backend/app/schemas/
backend/app/services/
backend/app/prompts/
```

Your MVP doc already lists the backend services you need: `notion_service.py`, `planning_service.py`, `stats_service.py`, and `llm_service.py`. 

Commit:

```bash id="dcx578"
git add .
git commit -m "Create MVP project catalog"
```

---

# Step 3 — Configure environment files for Ollama Cloud

In root:

```txt id="rq7gab"
.env.example
```

use:

```env id="d6fhqk"
DATABASE_URL=postgresql://postgres:postgres@postgres:5432/life_execution

OLLAMA_BASE_URL=https://ollama.com
OLLAMA_API_KEY=your_ollama_api_key
OLLAMA_MODEL=qwen3.5:cloud

NOTION_API_KEY=your_notion_api_key
NOTION_DATABASE_ID=your_notion_database_id
JWT_SECRET=your_jwt_secret
```

In:

```txt id="eic71t"
backend/.env.example
```

use the same:

```env id="3zfjzu"
DATABASE_URL=postgresql://postgres:postgres@postgres:5432/life_execution

OLLAMA_BASE_URL=https://ollama.com
OLLAMA_API_KEY=your_ollama_api_key
OLLAMA_MODEL=qwen3.5:cloud

NOTION_API_KEY=your_notion_api_key
NOTION_DATABASE_ID=your_notion_database_id
JWT_SECRET=your_jwt_secret
```

Then copy:

```powershell id="m7wpmz"
Copy-Item backend/.env.example backend/.env
Copy-Item frontend/.env.local.example frontend/.env.local
```

Edit `backend/.env` and put the real key:

```env id="rieeev"
OLLAMA_API_KEY=real_key_here
```

Do **not** commit `backend/.env`.

---

# Step 4 — Update `docker-compose.yml`

For Ollama Cloud, the backend only needs internet access. You do **not** need `extra_hosts`.

Use:

```yaml id="cy8ike"
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

Important difference:

```text id="j49rwq"
Local Ollama:
backend container → host.docker.internal:11434

Ollama Cloud:
backend container → https://ollama.com/api/chat
```

---

# Step 5 — Update backend dependencies

In:

```txt id="nmjzqb"
backend/requirements.txt
```

use:

```txt id="qa4l9d"
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

You do **not** need:

```txt id="cxpm3m"
openai
```

You do **not** need local Ollama Python package either. The backend can call Ollama Cloud by HTTP.

---

# Step 6 — Update backend config

In:

```txt id="9h0yfp"
backend/app/config.py
```

use:

```python id="r6r8hb"
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

---

# Step 7 — Build `llm_service.py` for Ollama Cloud

In:

```txt id="y3n7lv"
backend/app/services/llm_service.py
```

use:

```python id="lqmu7r"
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
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
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

Ollama’s chat API is `/api/chat`, and Ollama Cloud uses the same API path under `https://ollama.com/api`. ([Ollama][2])

---

# Step 8 — Test Ollama Cloud inside Docker

Start only backend and postgres:

```bash id="3lp14r"
docker compose up --build backend postgres
```

Enter backend container:

```bash id="p67arf"
docker exec -it life_execution_backend bash
```

Run:

```bash id="4pqfmk"
python - << "EOF"
import os
import httpx

api_key = os.getenv("OLLAMA_API_KEY")
model = os.getenv("OLLAMA_MODEL", "qwen3.5:cloud")

response = httpx.post(
    "https://ollama.com/api/chat",
    json={
        "model": model,
        "messages": [
            {"role": "user", "content": "Say OK only"}
        ],
        "stream": False,
    },
    headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    },
    timeout=120,
)

print(response.status_code)
print(response.text)
EOF
```

Expected:

```text id="lz7aoo"
200
...
OK
...
```

If you get:

```text id="d8vcri"
401
```

your API key is missing or invalid.

If you get:

```text id="l7565m"
403
```

your account does not have access to that cloud model.

If you get:

```text id="hlo2uw"
404
```

the model name is probably wrong. Use `/api/tags` to list available models.

---

# Step 9 — Build database models

Implement these files:

```text id="vtidbw"
backend/app/models/user.py
backend/app/models/weekly_goal.py
backend/app/models/daily_task.py
backend/app/models/study_session.py
backend/app/models/daily_review.py
```

Minimum database tables:

```text id="kz5zbi"
users
weekly_goals
daily_tasks
study_sessions
daily_reviews
```

Your uploaded MVP doc already defines these as enough for the MVP database. 

---

# Step 10 — Build backend schemas

Implement:

```text id="jwhbwu"
backend/app/schemas/user.py
backend/app/schemas/weekly_goal.py
backend/app/schemas/daily_task.py
backend/app/schemas/study_session.py
backend/app/schemas/dashboard.py
backend/app/schemas/review.py
```

These files define API input/output shapes.

Example:

```python id="y9pbqc"
from datetime import date
from pydantic import BaseModel


class WeeklyGoalCreate(BaseModel):
    title: str
    description: str | None = None
    week_start: date
    week_end: date


class WeeklyGoalRead(WeeklyGoalCreate):
    id: int
    status: str

    class Config:
        from_attributes = True
```

---

# Step 11 — Build manual CRUD first

Do not touch AI planning yet.

Implement:

```text id="u9khm2"
backend/app/api/weekly_goals.py
backend/app/api/daily_tasks.py
backend/app/api/study_sessions.py
```

Target endpoints:

```text id="c0p6io"
POST   /weekly-goals
GET    /weekly-goals/current
PATCH  /weekly-goals/{goal_id}
DELETE /weekly-goals/{goal_id}

POST   /daily-tasks
GET    /daily-tasks/today
PATCH  /daily-tasks/{task_id}

POST   /study-sessions/start
POST   /study-sessions/finish
GET    /study-sessions/today
```

Success test:

```text id="qxef8l"
You can create weekly goals.
You can manually create daily tasks.
You can start and finish a study session.
```

---

# Step 12 — Build dashboard statistics

Implement:

```text id="de7xbo"
backend/app/services/stats_service.py
backend/app/api/dashboard.py
```

Return:

```json id="fmm0h2"
{
  "today_focus_minutes": 120,
  "week_focus_minutes": 480,
  "today_completed_tasks": 3,
  "today_total_tasks": 5,
  "completion_rate": 0.6
}
```

Target endpoints:

```text id="ttrv3r"
GET /dashboard/today
GET /dashboard/week
```

---

# Step 13 — Add AI daily plan

Now connect AI.

Implement:

```text id="hmcxds"
backend/app/services/planning_service.py
```

Add endpoint:

```text id="aj27as"
POST /daily-tasks/generate
```

Backend flow:

```text id="yd7c3g"
1. Read current weekly goals.
2. Read unfinished daily tasks.
3. Send both to Ollama Cloud.
4. Parse JSON.
5. Save generated tasks into daily_tasks.
6. Return generated tasks.
```

Your MVP doc already says the core AI feature should simply call `generate_daily_plan(weekly_goals, unfinished_tasks, available_hours)` rather than building a complex agent. 

---

# Step 14 — Add AI daily review

Implement:

```text id="ae9963"
backend/app/services/review_service.py
backend/app/api/reviews.py
```

Target endpoints:

```text id="pyrer1"
POST /reviews/generate
GET  /reviews/today
```

Backend flow:

```text id="fsq4za"
1. Read today's planned tasks.
2. Read completed tasks.
3. Read study sessions.
4. Send summary input to Ollama Cloud.
5. Save result into daily_reviews.
6. Return review.
```

---

# Step 15 — Build frontend pages

Build in this order:

```text id="lanzee"
1. weekly-plan/page.tsx
2. today/page.tsx
3. timer/page.tsx
4. dashboard/page.tsx
5. review/page.tsx
6. login/page.tsx
```

Your MVP doc lists these same MVP pages: Weekly Plan, Today, Timer, Dashboard, and Review. 

Frontend should call only FastAPI:

```text id="kzvvyc"
Frontend → FastAPI backend → Ollama Cloud
```

Do not call Ollama Cloud directly from frontend. Otherwise your `OLLAMA_API_KEY` leaks to the browser.

---

# Step 16 — Add Notion integration last

Implement:

```text id="w2trh9"
backend/app/services/notion_service.py
backend/app/api/notion.py
```

Only support two MVP functions:

```text id="l47339"
POST /notion/import-weekly-goals
POST /notion/export-daily-review
```

Do not build full two-way sync yet.

---

# Step 17 — Final Docker run

Run:

```bash id="h8rdo0"
docker compose up --build
```

Open:

```text id="ez1ua5"
Frontend: http://localhost:3000
Backend docs: http://localhost:8000/docs
PostgreSQL: localhost:5432
```

---

# Final MVP acceptance test

The MVP is done when this works:

```text id="bqtfyd"
1. User logs in.
2. User creates weekly goals.
3. User clicks "Generate Today's Plan."
4. Backend calls Ollama Cloud.
5. Ollama Cloud returns 3–5 planned tasks.
6. Tasks are saved in PostgreSQL.
7. User starts a study timer.
8. User stops the timer.
9. Study session is saved.
10. Dashboard updates focus time and completion rate.
11. User generates daily review.
12. Backend calls Ollama Cloud again.
13. Review is saved.
14. Optional: review is exported to Notion.
```

Main rule:

```text id="f6taem"
Do not use local Ollama.
Do not use qwen2.5:3b.
Do not use host.docker.internal:11434.
Use Ollama Cloud through https://ollama.com/api/chat.
```

[1]: https://docs.ollama.com/cloud?utm_source=chatgpt.com "Cloud"
[2]: https://docs.ollama.com/api/authentication?utm_source=chatgpt.com "Authentication"
