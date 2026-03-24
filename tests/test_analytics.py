"""
Analytics endpoint tests.
"""
import pytest


async def _auth_headers(client, user_data):
    await client.post("/auth/register", json=user_data)
    login = await client.post("/auth/login", data={
        "username": user_data["email"],
        "password": user_data["password"],
    })
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


@pytest.mark.asyncio
async def test_analytics_summary_empty(client, test_user_data):
    headers = await _auth_headers(client, test_user_data)
    resp = await client.get("/analytics/summary", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_posts"] == 0
    assert data["successful"] == 0
    assert data["failed"] == 0
    assert data["pending"] == 0


@pytest.mark.asyncio
async def test_analytics_summary_with_posts(client, test_user_data):
    headers = await _auth_headers(client, test_user_data)

    ch = await client.post("/channels", json={
        "platform": "instagram",
        "account_id": "ig_test",
        "access_token": "fake",
    }, headers=headers)
    channel_id = ch.json()["id"]

    await client.post("/posts", json={
        "caption": "Post 1",
        "channel_ids": [channel_id],
    }, headers=headers)

    resp = await client.get("/analytics/summary", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_posts"] == 1
    assert data["pending"] >= 1


@pytest.mark.asyncio
async def test_analytics_requires_auth(client):
    resp = await client.get("/analytics/summary")
    assert resp.status_code == 401
