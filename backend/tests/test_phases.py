from datetime import date, timedelta


def phase_payload(title: str = "Q3 Goal Achievement") -> dict:
    today = date.today()
    return {
        "title": title,
        "description": "Reach the quarter objectives",
        "start_date": today.isoformat(),
        "end_date": (today + timedelta(days=90)).isoformat(),
        "status": "active",
        "progress": 25,
        "estimated_focus_minutes": 7200,
        "notes": "Protect two deep-work blocks each week.",
    }


def test_phase_and_milestone_crud(client, user_headers):
    created = client.post("/phases", json=phase_payload(), headers=user_headers)
    assert created.status_code == 201
    phase = created.json()
    assert phase["title"] == "Q3 Goal Achievement"
    assert phase["milestones"] == []

    milestone = client.post(
        f"/phases/{phase['id']}/milestones",
        headers=user_headers,
        json={
            "title": "Define success metrics",
            "description": "Agree on measurable outcomes",
            "due_date": (date.today() + timedelta(days=7)).isoformat(),
            "status": "in_progress",
            "progress": 40,
        },
    )
    assert milestone.status_code == 201
    milestone_data = milestone.json()

    updated = client.patch(
        f"/phases/{phase['id']}/milestones/{milestone_data['id']}",
        headers=user_headers,
        json={"status": "completed"},
    )
    assert updated.status_code == 200
    assert updated.json()["progress"] == 100

    phases = client.get("/phases", headers=user_headers)
    assert phases.status_code == 200
    assert phases.json()[0]["milestones"][0]["status"] == "completed"

    changed = client.patch(
        f"/phases/{phase['id']}",
        headers=user_headers,
        json={"title": "Updated Q3", "progress": 50},
    )
    assert changed.status_code == 200
    assert changed.json()["title"] == "Updated Q3"

    deleted = client.delete(f"/phases/{phase['id']}", headers=user_headers)
    assert deleted.status_code == 204
    assert client.get("/phases", headers=user_headers).json() == []


def test_phase_records_are_user_scoped(client, user_headers):
    created = client.post("/phases", json=phase_payload(), headers=user_headers)
    phase_id = created.json()["id"]

    assert client.get("/phases", headers={"X-User-ID": "2"}).status_code == 401
    response = client.patch(
        f"/phases/{phase_id}",
        headers={"X-User-ID": "2"},
        json={"title": "Not allowed"},
    )
    assert response.status_code == 401


def test_phase_rejects_invalid_date_range(client, user_headers):
    payload = phase_payload()
    payload["end_date"] = (date.today() - timedelta(days=1)).isoformat()
    response = client.post("/phases", json=payload, headers=user_headers)
    assert response.status_code == 422
