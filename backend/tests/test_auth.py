import pytest
import httpx
import uuid
from httpx import ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_register_and_login_flow(client: httpx.AsyncClient):
    unique_email = f"student_{uuid.uuid4().hex[:8]}@smartlearning.vn"
    password = "SecurePassword123!"

    # 1. Register a new student
    register_payload = {
        "email": unique_email,
        "password": password,
        "full_name": "Nguyễn Văn Test",
        "role": "STUDENT",
        "grade_level": 11
    }
    reg_res = await client.post("/api/v1/auth/register", json=register_payload)
    assert reg_res.status_code == 201, reg_res.text
    reg_data = reg_res.json()
    assert reg_data["email"] == unique_email.lower()
    assert reg_data["role"] == "STUDENT"
    assert reg_data["grade_level"] == 11

    # 2. Reject duplicate registration
    dup_res = await client.post("/api/v1/auth/register", json=register_payload)
    assert dup_res.status_code == 409

    # 3. Reject invalid login credentials
    bad_login_res = await client.post("/api/v1/auth/login", json={
        "email": unique_email,
        "password": "WrongPassword!"
    })
    assert bad_login_res.status_code == 401

    # 4. Successful login (sets HttpOnly cookie and returns tokens)
    login_res = await client.post("/api/v1/auth/login", json={
        "email": unique_email,
        "password": password
    })
    assert login_res.status_code == 200
    login_data = login_res.json()
    assert "access_token" in login_data
    assert "refresh_token" in login_data
    assert login_data["user"]["email"] == unique_email.lower()

    token = login_data["access_token"]

    # 5. Get current user profile with Authorization Bearer header
    me_res = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["email"] == unique_email.lower()
    assert me_data["full_name"] == "Nguyễn Văn Test"

    # 6. Verify authentication also works via the HttpOnly cookie automatically saved in client
    cookie_me_res = await client.get("/api/v1/auth/me")
    assert cookie_me_res.status_code == 200

    # 7. Reject unauthenticated access using a separate client without cookies
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as unauth_client:
        unauth_res = await unauth_client.get("/api/v1/auth/me")
        assert unauth_res.status_code == 401

    # 8. Logout
    logout_res = await client.post("/api/v1/auth/logout")
    assert logout_res.status_code == 200
