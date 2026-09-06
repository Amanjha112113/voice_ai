"""Integration tests for FastAPI Control Plane endpoints."""

import pytest
import httpx
from backend.app.main import app


@pytest.mark.asyncio
async def test_health_endpoint():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "active_sessions_count" in data
        assert "media_plane" in data


@pytest.mark.asyncio
async def test_session_lifecycle_endpoints():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # 1. Create Session
        create_resp = await client.post(
            "/sessions",
            json={"customer_id": "cust_123", "language": "en-IN", "use_mock_providers": True}
        )
        assert create_resp.status_code == 201
        session_data = create_resp.json()
        assert "session_id" in session_data
        assert "channel" in session_data
        assert "token" in session_data
        assert session_data["status"] == "starting"

        session_id = session_data["session_id"]

        # 2. Get Session Details
        detail_resp = await client.get(f"/sessions/{session_id}")
        assert detail_resp.status_code == 200
        detail_data = detail_resp.json()
        assert detail_data["session_id"] == session_id
        assert detail_data["current_state"] == "IDLE"
        assert "active_generation_id" in detail_data
        assert detail_data["metrics_summary"]["total_turns"] == 0

        # 3. Delete Session
        delete_resp = await client.delete(f"/sessions/{session_id}")
        assert delete_resp.status_code == 200

        # 4. Verify Not Found after deletion
        get_after_del = await client.get(f"/sessions/{session_id}")
        assert get_after_del.status_code == 404
