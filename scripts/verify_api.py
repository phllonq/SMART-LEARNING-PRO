import asyncio
import sys
import os
import httpx
from httpx import ASGITransport

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))
from app.main import app
import tests.test_rbac  # registers test rbac router for verification


async def verify():
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        print("=== 1. VERIFY HEALTH ENDPOINT ===")
        res = await client.get("/api/v1/health")
        print(f"GET /api/v1/health -> Status: {res.status_code}")
        print("Payload:", res.json())
        assert res.status_code == 200

        print("\n=== 2. VERIFY OPENAPI SCHEMA ===")
        res = await client.get("/openapi.json")
        print(f"GET /openapi.json -> Status: {res.status_code}")
        openapi = res.json()
        print(f"API Title: {openapi.get('info', {}).get('title')}, Endpoints count: {len(openapi.get('paths', {}))}")
        assert res.status_code == 200

        print("\n=== 3. VERIFY AUTHENTICATION WITH SEEDED ACCOUNTS ===")
        accounts = [
            ("admin@smartlearning.vn", "AdminSecurePassword123!", "SUPERADMIN"),
            ("giaovien.toan@smartlearning.vn", "TeacherPassword123!", "TEACHER"),
            ("hocsinh.an@smartlearning.vn", "StudentPassword123!", "STUDENT"),
        ]
        tokens = {}
        for email, password, expected_role in accounts:
            login_res = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
            print(f"Login {email} -> Status: {login_res.status_code}")
            assert login_res.status_code == 200
            data = login_res.json()
            user = data["user"]
            token = data["access_token"]
            tokens[expected_role] = token
            print(f" - Verified User: {user['full_name']} | Role: {user['role']} (Expected: {expected_role})")
            assert user["role"] == expected_role

            # Test GET /auth/me with Bearer token
            me_res = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
            assert me_res.status_code == 200
            print(f" - GET /api/v1/auth/me -> Status: {me_res.status_code} | Name: {me_res.json()['full_name']}")

        print("\n=== 4. VERIFY RBAC RESTRICTIONS ===")
        # Student attempting to access teacher or admin endpoints
        student_headers = {"Authorization": f"Bearer {tokens['STUDENT']}"}
        teacher_headers = {"Authorization": f"Bearer {tokens['TEACHER']}"}
        admin_headers = {"Authorization": f"Bearer {tokens['SUPERADMIN']}"}

        # Test RBAC using test endpoints from test_rbac if registered, or direct check
        res_stu_on_tea = await client.get("/api/v1/test-rbac/teacher-only", headers=student_headers)
        print(f"Student -> /test-rbac/teacher-only -> Status: {res_stu_on_tea.status_code} (Expected: 403)")
        assert res_stu_on_tea.status_code == 403

        res_tea_on_tea = await client.get("/api/v1/test-rbac/teacher-only", headers=teacher_headers)
        print(f"Teacher -> /test-rbac/teacher-only -> Status: {res_tea_on_tea.status_code} (Expected: 200)")
        assert res_tea_on_tea.status_code == 200

        res_tea_on_adm = await client.get("/api/v1/test-rbac/admin-only", headers=teacher_headers)
        print(f"Teacher -> /test-rbac/admin-only   -> Status: {res_tea_on_adm.status_code} (Expected: 403)")
        assert res_tea_on_adm.status_code == 403

        res_adm_on_adm = await client.get("/api/v1/test-rbac/admin-only", headers=admin_headers)
        print(f"Admin   -> /test-rbac/admin-only   -> Status: {res_adm_on_adm.status_code} (Expected: 200)")
        assert res_adm_on_adm.status_code == 200

        print("\nALL VERIFICATIONS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    asyncio.run(verify())
