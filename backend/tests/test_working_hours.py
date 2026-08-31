import pytest


def test_working_hours_default_and_persist_with_working_days(client, user_headers):
    original = client.get("/automation-preferences", headers=user_headers).json()
    assert (original["working_start_hour"], original["working_end_hour"]) == (7, 22)
    response = client.patch("/automation-preferences", headers=user_headers, json={
        "working_start_hour": 8, "working_end_hour": 18, "working_days": ["tuesday", "friday"],
    })
    assert response.status_code == 200
    fetched = client.get("/automation-preferences", headers=user_headers).json()
    assert (fetched["working_start_hour"], fetched["working_end_hour"]) == (8, 18)
    assert fetched["working_days"] == ["tuesday", "friday"]
    client.patch("/automation-preferences", headers=user_headers, json={"automation_enabled": False})
    fetched = client.get("/automation-preferences", headers=user_headers).json()
    assert (fetched["working_start_hour"], fetched["working_end_hour"]) == (8, 18)


@pytest.mark.parametrize("payload", [
    {"working_start_hour": -1}, {"working_end_hour": 24},
    {"working_start_hour": None}, {"working_end_hour": None},
    {"working_start_hour": 8.5}, {"working_start_hour": 22},
    {"working_end_hour": 7}, {"working_start_hour": 18, "working_end_hour": 8},
])
def test_invalid_working_hours_leave_saved_range_unchanged(client, user_headers, payload):
    client.get("/automation-preferences", headers=user_headers)
    response = client.patch("/automation-preferences", headers=user_headers, json=payload)
    assert response.status_code == 422
    fetched = client.get("/automation-preferences", headers=user_headers).json()
    assert (fetched["working_start_hour"], fetched["working_end_hour"]) == (7, 22)


def test_valid_partial_hour_updates(client, user_headers):
    for payload in [{"working_start_hour": 0}, {"working_end_hour": 23}]:
        assert client.patch("/automation-preferences", headers=user_headers, json=payload).status_code == 200
    fetched = client.get("/automation-preferences", headers=user_headers).json()
    assert (fetched["working_start_hour"], fetched["working_end_hour"]) == (0, 23)
