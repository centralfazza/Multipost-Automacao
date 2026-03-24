"""
Posts endpoint tests — create, list, get, delete.
Publishing is tested with mocked services.
"""
import pytest


async def _setup_user_with_channel(client, user_data):
    """Helper: register, login, create a channel, return (headers, channel_id)."""
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
async def test_create_post(client, test_user_data):
    headers, channel_id = await _setup_user_with_channel(client, test_user_data)
    resp = await client.post("/posts", json={
        "caption": "Hello world!",
        "media_urls": ["https://example.com/img.jpg"],
        "media_type": "image",
        "channel_ids": [channel_id],
    }, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["caption"] == "Hello world!"
    assert data["status"] == "pending"
    assert len(data["results"]) == 1


@pytest.mark.asyncio
async def test_create_post_no_channels(client, test_user_data):
    headers, _ = await _setup_user_with_channel(client, test_user_data)
    resp = await client.post("/posts", json={
        "caption": "No channels",
        "channel_ids": ["nonexistent-id"],
    }, headers=headers)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_create_post_empty_channel_ids(client, test_user_data):
    headers, _ = await _setup_user_with_channel(client, test_user_data)
    resp = await client.post("/posts", json={
        "caption": "Empty",
        "channel_ids": [],
    }, headers=headers)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_scheduled_post(client, test_user_data):
    headers, channel_id = await _setup_user_with_channel(client, test_user_data)
    resp = await client.post("/posts", json={
        "caption": "Scheduled post",
        "channel_ids": [channel_id],
        "scheduled_at": "2099-12-31T23:59:59Z",
    }, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["scheduled_at"] is not None
    assert data["status"] == "pending"


@pytest.mark.asyncio
async def test_list_posts(client, test_user_data):
    headers, channel_id = await _setup_user_with_channel(client, test_user_data)
    await client.post("/posts", json={
        "caption": "Post 1",
        "channel_ids": [channel_id],
    }, headers=headers)
    await client.post("/posts", json={
        "caption": "Post 2",
        "channel_ids": [channel_id],
    }, headers=headers)

    resp = await client.get("/posts", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_list_posts_filter_status(client, test_user_data):
    headers, channel_id = await _setup_user_with_channel(client, test_user_data)
    await client.post("/posts", json={
        "caption": "A post",
        "channel_ids": [channel_id],
    }, headers=headers)

    resp = await client.get("/posts?status=pending", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) >= 1

    resp2 = await client.get("/posts?status=done", headers=headers)
    assert resp2.status_code == 200
    assert len(resp2.json()) == 0


@pytest.mark.asyncio
async def test_get_post(client, test_user_data):
    headers, channel_id = await _setup_user_with_channel(client, test_user_data)
    create = await client.post("/posts", json={
        "caption": "Get me",
        "channel_ids": [channel_id],
    }, headers=headers)
    post_id = create.json()["id"]

    resp = await client.get(f"/posts/{post_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == post_id


@pytest.mark.asyncio
async def test_get_post_not_found(client, test_user_data):
    headers, _ = await _setup_user_with_channel(client, test_user_data)
    resp = await client.get("/posts/nonexistent-id", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_post(client, test_user_data):
    headers, channel_id = await _setup_user_with_channel(client, test_user_data)
    create = await client.post("/posts", json={
        "caption": "Delete me",
        "channel_ids": [channel_id],
    }, headers=headers)
    post_id = create.json()["id"]

    resp = await client.delete(f"/posts/{post_id}", headers=headers)
    assert resp.status_code == 204

    resp2 = await client.get(f"/posts/{post_id}", headers=headers)
    assert resp2.status_code == 404


@pytest.mark.asyncio
async def test_posts_require_auth(client):
    resp = await client.get("/posts")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_post_invalid_media_url(client, test_user_data):
    headers, channel_id = await _setup_user_with_channel(client, test_user_data)
    resp = await client.post("/posts", json={
        "caption": "Bad URL",
        "media_urls": ["http://insecure.com/img.jpg"],
        "channel_ids": [channel_id],
    }, headers=headers)
    assert resp.status_code == 422
