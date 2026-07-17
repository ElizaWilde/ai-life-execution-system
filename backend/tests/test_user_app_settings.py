def test_get_app_settings_creates_defaults(client, user_headers):
    response = client.get("/app-settings/me", headers=user_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["week_start"] == "Monday"
    assert data["focus_minutes"] == 25
    assert data["theme"] == "light"
    assert data["proactive"] is True
    assert data["integrations"] == []
    assert data["avatar_data_url"] is None


def test_update_app_settings_persists_full_page_preferences(client, user_headers):
    payload = {
        "week_start": "Sunday",
        "focus_minutes": 45,
        "short_break_minutes": 10,
        "long_break_minutes": 30,
        "workload": "high",
        "theme": "dark",
        "tone": "direct",
        "strictness": "strict",
        "adjustment": "strong",
        "proactive": False,
        "focus_matters": False,
        "protect_deep_work": False,
        "learn_from_feedback": False,
        "integrations": ["Notion", "Gmail"],
        "avatar_data_url": "data:image/png;base64,dGVzdA==",
    }

    updated = client.put("/app-settings/me", headers=user_headers, json=payload)
    fetched = client.get("/app-settings/me", headers=user_headers)

    assert updated.status_code == 200
    assert fetched.status_code == 200
    for key, value in payload.items():
        assert fetched.json()[key] == value


def test_invalid_app_setting_is_rejected(client, user_headers):
    response = client.put(
        "/app-settings/me",
        headers=user_headers,
        json={
            "week_start": "Friday",
            "focus_minutes": 25,
            "short_break_minutes": 5,
            "long_break_minutes": 15,
            "workload": "medium",
            "theme": "light",
            "tone": "supportive",
            "strictness": "balanced",
            "adjustment": "moderate",
            "proactive": True,
            "focus_matters": True,
            "protect_deep_work": True,
            "learn_from_feedback": True,
            "integrations": [],
            "avatar_data_url": None,
        },
    )

    assert response.status_code == 422
