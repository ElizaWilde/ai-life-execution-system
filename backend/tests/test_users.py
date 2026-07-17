from app.models import User
from conftest import TestingSessionLocal


def test_get_current_user_profile(client, user_headers):
    response = client.get("/users/me", headers=user_headers)

    assert response.status_code == 200
    assert response.json()["id"] == 1
    assert response.json()["email"] == "mvp@example.com"
    assert response.json()["display_name"] == "MVP User"


def test_update_profile_persists_name_and_email(client, user_headers):
    updated = client.patch(
        "/users/me",
        headers=user_headers,
        json={"display_name": "Car", "email": "CAR@example.com"},
    )
    fetched = client.get("/users/me", headers=user_headers)

    assert updated.status_code == 200
    assert updated.json()["display_name"] == "Car"
    assert updated.json()["email"] == "car@example.com"
    assert fetched.json()["display_name"] == "Car"
    assert fetched.json()["email"] == "car@example.com"


def test_duplicate_email_is_rejected(client, user_headers):
    with TestingSessionLocal() as db:
        db.add(
            User(
                id=2,
                email="used@example.com",
                password_hash="not-used",
                display_name="Second User",
            )
        )
        db.commit()

    response = client.patch(
        "/users/me",
        headers=user_headers,
        json={"email": "used@example.com"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Email is already in use"


def test_invalid_profile_email_is_rejected(client, user_headers):
    response = client.patch(
        "/users/me",
        headers=user_headers,
        json={"email": "not-an-email"},
    )

    assert response.status_code == 422
