from __future__ import annotations

from datetime import date
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import DailyReview, WeeklyGoal


class NotionConfigurationError(RuntimeError):
    pass


class DailyReviewNotFoundError(LookupError):
    pass


class NotionService:
    """Synchronize weekly goals and daily reviews with a Notion database."""

    api_base_url = "https://api.notion.com/v1"
    notion_version = "2022-06-28"

    async def import_weekly_goals(self, db: Session, user_id: int) -> list[WeeklyGoal]:
        imported: list[WeeklyGoal] = []
        cursor: str | None = None

        while True:
            payload: dict[str, Any] = {"page_size": 100}
            if cursor:
                payload["start_cursor"] = cursor

            response = await self._request(
                "POST",
                f"/databases/{self._database_id()}/query",
                json=payload,
            )
            body = response.json()

            for page in body.get("results", []):
                goal_data = self._page_to_weekly_goal(page)
                page_id = page.get("id")
                if not page_id or goal_data is None:
                    continue

                goal = db.scalar(
                    select(WeeklyGoal).where(
                        WeeklyGoal.user_id == user_id,
                        WeeklyGoal.notion_page_id == page_id,
                    )
                )
                if goal is None:
                    goal = WeeklyGoal(user_id=user_id, notion_page_id=page_id)
                    db.add(goal)

                for field, value in goal_data.items():
                    setattr(goal, field, value)
                imported.append(goal)

            if not body.get("has_more"):
                break
            cursor = body.get("next_cursor")
            if not cursor:
                break

        db.commit()
        for goal in imported:
            db.refresh(goal)
        return imported

    async def export_daily_review(
        self,
        db: Session,
        user_id: int,
        review_date: date | None = None,
    ) -> str:
        target_date = review_date or date.today()
        review = db.scalar(
            select(DailyReview).where(
                DailyReview.user_id == user_id,
                DailyReview.review_date == target_date,
            )
        )
        if review is None:
            raise DailyReviewNotFoundError("Daily review not found")

        response = await self._request(
            "POST",
            "/pages",
            json={
                "parent": {"database_id": self._database_id()},
                "properties": {
                    "Name": {
                        "title": [
                            {
                                "text": {
                                    "content": f"Daily Review - {review.review_date.isoformat()}"
                                }
                            }
                        ]
                    },
                    "Date": {"date": {"start": review.review_date.isoformat()}},
                },
                "children": self._review_blocks(review),
            },
        )
        return str(response.json()["id"])

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        api_key = settings.notion_api_key
        if not api_key or api_key == "your_notion_api_key":
            raise NotionConfigurationError("NOTION_API_KEY is not configured")

        async with httpx.AsyncClient(
            base_url=self.api_base_url,
            timeout=30,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Notion-Version": self.notion_version,
                "Content-Type": "application/json",
            },
        ) as client:
            response = await client.request(method, path, **kwargs)
            response.raise_for_status()
            return response

    @staticmethod
    def _database_id() -> str:
        database_id = settings.notion_database_id
        if not database_id or database_id == "your_notion_database_id":
            raise NotionConfigurationError("NOTION_DATABASE_ID is not configured")
        return database_id

    def _page_to_weekly_goal(self, page: dict[str, Any]) -> dict[str, Any] | None:
        properties = page.get("properties", {})
        title = self._text_property(properties, "Title", "Name", "Goal")
        week_start = self._date_property(properties, "Week Start", "Start")
        week_end = self._date_property(properties, "Week End", "End")
        if not title or week_start is None or week_end is None or week_end < week_start:
            return None

        priority = self._select_property(properties, "Priority").lower()
        if priority not in {"low", "medium", "high"}:
            priority = "medium"
        status = self._select_property(properties, "Status").lower()
        if status not in {"active", "completed", "cancelled"}:
            status = "active"

        target_minutes = self._number_property(
            properties, "Target Minutes", "Target minutes"
        )
        return {
            "title": title[:255],
            "description": self._text_property(properties, "Description") or None,
            "week_start": week_start,
            "week_end": week_end,
            "priority": priority,
            "status": status,
            "target_minutes": (
                max(0, int(target_minutes)) if target_minutes is not None else None
            ),
        }

    @staticmethod
    def _property(properties: dict[str, Any], *names: str) -> dict[str, Any]:
        lowered = {key.lower(): value for key, value in properties.items()}
        for name in names:
            if name.lower() in lowered:
                return lowered[name.lower()]
        return {}

    def _text_property(self, properties: dict[str, Any], *names: str) -> str:
        prop = self._property(properties, *names)
        items = prop.get("title") or prop.get("rich_text") or []
        return "".join(item.get("plain_text", "") for item in items).strip()

    def _date_property(
        self, properties: dict[str, Any], *names: str
    ) -> date | None:
        value = self._property(properties, *names).get("date") or {}
        start = value.get("start")
        if not start:
            return None
        try:
            return date.fromisoformat(start[:10])
        except (TypeError, ValueError):
            return None

    def _select_property(self, properties: dict[str, Any], *names: str) -> str:
        prop = self._property(properties, *names)
        selected = prop.get("select") or prop.get("status") or {}
        return str(selected.get("name", ""))

    def _number_property(
        self, properties: dict[str, Any], *names: str
    ) -> float | None:
        value = self._property(properties, *names).get("number")
        return value if isinstance(value, (int, float)) else None

    @staticmethod
    def _review_blocks(review: DailyReview) -> list[dict[str, Any]]:
        sections = [
            ("Summary", review.summary),
            ("Tomorrow's adjustment", review.tomorrow_adjustment),
            (
                "Stats",
                (
                    f"Tasks: {review.completed_tasks}/{review.planned_tasks} completed · "
                    f"Focus: {review.focus_minutes} minutes"
                ),
            ),
        ]
        blocks: list[dict[str, Any]] = []
        for heading, content in sections:
            if not content:
                continue
            blocks.extend(
                [
                    {
                        "object": "block",
                        "type": "heading_2",
                        "heading_2": {
                            "rich_text": [{"text": {"content": heading}}]
                        },
                    },
                    {
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": [{"text": {"content": str(content)[:2000]}}]
                        },
                    },
                ]
            )
        return blocks


notion_service = NotionService()
