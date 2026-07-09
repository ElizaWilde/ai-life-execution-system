from datetime import date

from app.models import WeeklyGoal


def test_import_weekly_goals(client, user_headers, monkeypatch):
    async def fake_import(db, user_id):
        goal = WeeklyGoal(
            user_id=user_id,
            title="Ship Notion sync",
            week_start=date(2026, 7, 6),
            week_end=date(2026, 7, 12),
            priority="high",
            status="active",
            notion_page_id="notion-page-1",
        )
        db.add(goal)
        db.commit()
        db.refresh(goal)
        return [goal]

    monkeypatch.setattr(
        "app.api.notion.notion_service.import_weekly_goals", fake_import
    )

    response = client.post("/notion/import-weekly-goals", headers=user_headers)

    assert response.status_code == 200
    assert response.json()["imported_count"] == 1
    assert response.json()["goals"][0]["notion_page_id"] == "notion-page-1"


def test_export_daily_review(client, user_headers, monkeypatch):
    created = client.post(
        "/reviews",
        headers=user_headers,
        json={
            "review_date": "2026-07-09",
            "summary": "Made steady progress.",
        },
    )
    assert created.status_code == 201

    async def fake_export(db, user_id, review_date):
        assert user_id == 1
        assert review_date == date(2026, 7, 9)
        return "notion-review-page"

    monkeypatch.setattr(
        "app.api.notion.notion_service.export_daily_review", fake_export
    )

    response = client.post(
        "/notion/export-daily-review",
        headers=user_headers,
        json={"review_date": "2026-07-09"},
    )

    assert response.status_code == 201
    assert response.json() == {"notion_page_id": "notion-review-page"}
