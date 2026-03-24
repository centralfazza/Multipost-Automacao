"""
Authentication endpoint tests — register, login, me.
"""
import pytest


@pytest.mark.asyncio
async def test_register_success(client, test_user_data):
    resp = await client.post("/auth/register", json=test_user_data)
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == test_user_data["email"]
    assert data["name"] == test_user_data["name"]
    assert "id" in data
    assert "hashed_password" not in data


@pytest.mark.asyncio
async def test_register_duplicate_email(client, test_user_data):
    await client.post("/auth/register", json=test_user_data)
    resp = await client.post("/auth/register", json=test_user_data)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_register_weak_password(client):
    resp = await client.post("/auth/register", json={
        "email": "weak@example.com",
        "name": "Weak",
        "password": "short",
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_empty_name(client):
    resp = await client.post("/auth/register", json={
        "email": "empty@example.com",
        "name": "   ",
        "password": "ValidPass123",
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_login_success(client, test_user_data):
    await client.post("/auth/register", json=test_user_data)
    resp = await client.post("/auth/login", data={
        "username": test_user_data["email"],
        "password": test_user_data["password"],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(client, test_user_data):
    await client.post("/auth/register", json=test_user_data)
    resp = await client.post("/auth/login", data={
        "username": test_user_data["email"],
        "password": "WrongPassword",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_user(client):
    resp = await client.post("/auth/login", data={
        "username": "nobody@example.com",
        "password": "whatever",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_authenticated(client, test_user_data):
    await client.post("/auth/register", json=test_user_data)
    login = await client.post("/auth/login", data={
        "username": test_user_data["email"],
        "password": test_user_data["password"],
    })
    token = login.json()["access_token"]

    resp = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == test_user_data["email"]


@pytest.mark.asyncio
async def test_me_unauthenticated(client):
    resp = await client.get("/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_invalid_token(client):
    resp = await client.get("/auth/me", headers={"Authorization": "Bearer invalidtoken"})
    assert resp.status_code == 401
