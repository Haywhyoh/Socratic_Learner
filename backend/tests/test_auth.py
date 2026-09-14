from fastapi.testclient import TestClient


def test_register_and_me(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "new@example.com", "password": "password123"},
    )
    assert response.status_code == 201
    assert response.json()["email"] == "new@example.com"

    login = client.post(
        "/api/v1/auth/login",
        data={"username": "new@example.com", "password": "password123"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]

    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "new@example.com"


def test_duplicate_email(client: TestClient) -> None:
    payload = {"email": "dup@example.com", "password": "password123"}
    assert client.post("/api/v1/auth/register", json=payload).status_code == 201
    again = client.post("/api/v1/auth/register", json=payload)
    assert again.status_code == 409


def test_bad_password(client: TestClient) -> None:
    client.post(
        "/api/v1/auth/register",
        json={"email": "bad@example.com", "password": "password123"},
    )
    login = client.post(
        "/api/v1/auth/login",
        data={"username": "bad@example.com", "password": "wrong-password"},
    )
    assert login.status_code == 401


def test_protected_route_without_token(client: TestClient) -> None:
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
