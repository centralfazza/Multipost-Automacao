"""
Batch operations endpoint tests.
"""
import pytest


async def _setup_user_with_channel(client, user_data):
    await client.post("/auth/register", json=user_data)
    login = await client.post("/auth/login", data={
        "username": user_data["email"],
        "password": user_data["password"],
    })
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    ch = await client.post("/channels", json={
        "platform": "instagram",
        "account_id": "ig_test",
        "access_token": "fake_token",
    }, headers=headers)
    return headers, ch.json()["id"]


@pytest.mark.asyncio
async def test_batch_create(client, test_user_data):
    headers, channel_id = await _setup_user_with_channel(client, test_user_data)
    resp = await client.post("/posts/batch/create", json={
        "posts": [
            {"caption": "Batch 1", "channel_ids": [channel_id]},
            {"caption": "Batch 2", "channel_ids": [channel_id]},
            {"caption": "Batch 3", "channel_ids": [channel_id]},
        ],
    }, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["total_requested"] == 3
    assert data["created"] == 3
    assert data["failed"] == 0


@pytest.mark.asyncio
async def test_batch_create_empty(client, test_user_data):
    headers, _ = await _setup_user_with_channel(client, test_user_data)
    resp = await client.post("/posts/batch/create", json={"posts": []}, headers=headers)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_batch_create_exceeds_limit(client, test_user_data):
    headers, channel_id = await _setup_user_with_channel(client, test_user_data)
    posts = [{"caption": f"Post {i}", "channel_ids": [channel_id]} for i in range(101)]
    resp = await client.post("/posts/batch/create", json={"posts": posts}, headers=headers)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_batch_create_with_invalid_channels(client, test_user_data):
    headers, channel_id = await _setup_user_with_channel(client, test_user_data)
    resp = await client.post("/posts/batch/create", json={
        "posts": [
            {"caption": "Valid", "channel_ids": [channel_id]},
            {"caption": "Invalid", "channel_ids": ["nonexistent-id"]},
        ],
    }, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["created"] == 1
    assert data["failed"] == 1


@pytest.mark.asyncio
async def test_batch_publish_empty(client, test_user_data):
    headers, _ = await _setup_user_with_channel(client, test_user_data)
    resp = await client.post("/posts/batch/publish", json={"post_ids": []}, headers=headers)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_batch_publish_not_found(client, test_user_data):
    headers, _ = await _setup_user_with_channel(client, test_user_data)
    resp = await client.post("/posts/batch/publish", json={
        "post_ids": ["nonexistent-id"],
    }, headers=headers)
    assert resp.status_code == 404
