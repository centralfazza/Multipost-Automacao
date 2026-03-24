"""
Channel CRUD endpoint tests.
"""
import pytest


async def _register_and_login(client, user_data):
    """Helper: register + login, return auth headers."""
    await client.post("/auth/register", json=user_data)
    login = await client.post("/auth/login", data={
        "username": user_data["email"],
        "password": user_data["password"],
    })
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_create_channel(client, test_user_data):
    headers = await _register_and_login(client, test_user_data)
    resp = await client.post("/channels", json={
        "platform": "instagram",
        "account_id": "ig_123",
        "account_name": "myaccount",
    }, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["platform"] == "instagram"
    assert data["account_id"] == "ig_123"


@pytest.mark.asyncio
async def test_create_channel_invalid_platform(client, test_user_data):
    headers = await _register_and_login(client, test_user_data)
    resp = await client.post("/channels", json={
        "platform": "snapchat",
    }, headers=headers)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_list_channels(client, test_user_data):
    headers = await _register_and_login(client, test_user_data)
    await client.post("/channels", json={"platform": "instagram"}, headers=headers)
    await client.post("/channels", json={"platform": "tiktok"}, headers=headers)

    resp = await client.get("/channels", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_list_channels_filter_platform(client, test_user_data):
    headers = await _register_and_login(client, test_user_data)
    await client.post("/channels", json={"platform": "instagram"}, headers=headers)
    await client.post("/channels", json={"platform": "tiktok"}, headers=headers)

    resp = await client.get("/channels?platform=instagram", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["platform"] == "instagram"


@pytest.mark.asyncio
async def test_get_channel(client, test_user_data):
    headers = await _register_and_login(client, test_user_data)
    create_resp = await client.post("/channels", json={"platform": "youtube"}, headers=headers)
    channel_id = create_resp.json()["id"]

    resp = await client.get(f"/channels/{channel_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == channel_id


@pytest.mark.asyncio
async def test_get_channel_not_found(client, test_user_data):
    headers = await _register_and_login(client, test_user_data)
    resp = await client.get("/channels/nonexistent-id", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_channel(client, test_user_data):
    headers = await _register_and_login(client, test_user_data)
    create_resp = await client.post("/channels", json={
        "platform": "twitter",
        "account_name": "old_name",
    }, headers=headers)
    channel_id = create_resp.json()["id"]

    resp = await client.patch(f"/channels/{channel_id}", json={
        "account_name": "new_name",
    }, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["account_name"] == "new_name"


@pytest.mark.asyncio
async def test_delete_channel(client, test_user_data):
    headers = await _register_and_login(client, test_user_data)
    create_resp = await client.post("/channels", json={"platform": "linkedin"}, headers=headers)
    channel_id = create_resp.json()["id"]

    resp = await client.delete(f"/channels/{channel_id}", headers=headers)
    assert resp.status_code == 204

    resp2 = await client.get(f"/channels/{channel_id}", headers=headers)
    assert resp2.status_code == 404


@pytest.mark.asyncio
async def test_channels_require_auth(client):
    resp = await client.get("/channels")
    assert resp.status_code == 401
