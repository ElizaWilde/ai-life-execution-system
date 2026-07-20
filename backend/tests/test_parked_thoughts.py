from app.models import User
from conftest import TestingSessionLocal


def test_parked_thought_crud(client, user_headers):
    created = client.post(
        "/parked-thoughts",
        headers=user_headers,
        json={"content": "  Explore spaced repetition  "},
    )

    assert created.status_code == 201
    assert created.json()["content"] == "Explore spaced repetition"
    assert created.json()["completed"] is False

    thought_id = created.json()["id"]
    completed = client.patch(
        f"/parked-thoughts/{thought_id}",
        headers=user_headers,
        json={"completed": True},
    )
    assert completed.status_code == 200
    assert completed.json()["completed"] is True
    assert completed.json()["completed_at"] is not None

    listed = client.get("/parked-thoughts", headers=user_headers)
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [thought_id]

    deleted = client.delete(
        f"/parked-thoughts/{thought_id}",
        headers=user_headers,
    )
    assert deleted.status_code == 204
    assert client.get("/parked-thoughts", headers=user_headers).json() == []


def test_user_cannot_change_another_users_parked_thought(client, user_headers):
    created = client.post(
        "/parked-thoughts",
        headers=user_headers,
        json={"content": "Private idea"},
    )
    with TestingSessionLocal() as db:
        db.add(
            User(
                id=2,
                email="park-user@example.com",
                password_hash="not-used",
                display_name="Park User",
            )
        )
        db.commit()

    response = client.patch(
        f"/parked-thoughts/{created.json()['id']}",
        headers={"X-User-ID": "2"},
        json={"completed": True},
    )

    assert response.status_code == 404


def test_blank_parked_thought_is_rejected(client, user_headers):
    response = client.post(
        "/parked-thoughts",
        headers=user_headers,
        json={"content": "   "},
    )

    assert response.status_code == 422
