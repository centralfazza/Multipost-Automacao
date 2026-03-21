"""
Health endpoint tests.
"""
import pytest


@pytest.mark.asyncio
async def test_health_endpoint(client):
    """Test that the health endpoint returns 200 and correct status."""
    response = await client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "multipost-api"
    assert "version" in data
