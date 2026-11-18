import pytest
import httpx
import uuid
from httpx import ASGITransport
from app.main import app
from app.modules.auth.models import UserRole
from app.core.dependencies import require_roles, get_current_user
from fastapi import APIRouter, Depends


# Create test router for RBAC verification
rbac_router = APIRouter(prefix="/api/v1/test-rbac")

@rbac_router.get("/student-only")
async def student_only(user=Depends(require_roles(UserRole.STUDENT))):
    return {"message": "student access granted", "role": user.role}

@rbac_router.get("/teacher-only")
async def teacher_only(user=Depends(require_roles(UserRole.TEACHER))):
    return {"message": "teacher access granted", "role": user.role}

@rbac_router.get("/admin-only")
async def admin_only(user=Depends(require_roles(UserRole.ADMIN))):
    return {"message": "admin access granted", "role": user.role}

app.include_router(rbac_router)


@pytest.mark.asyncio
async def test_rbac_permissions(client: httpx.AsyncClient):
    # 1. Register a student
    student_email = f"student_{uuid.uuid4().hex[:6]}@smartlearning.vn"
    reg_student = await client.post("/api/v1/auth/register", json={
        "email": student_email,
        "password": "Password123!",
        "full_name": "Em Học Sinh",
        "role": "STUDENT",
        "grade_level": 10
    })
    assert reg_student.status_code == 201

    # Login student
    login_stu = await client.post("/api/v1/auth/login", json={
        "email": student_email,
        "password": "Password123!"
    })
    student_token = login_stu.json()["access_token"]
    student_headers = {"Authorization": f"Bearer {student_token}"}

    # 2. Register a teacher
    teacher_email = f"teacher_{uuid.uuid4().hex[:6]}@smartlearning.vn"
    reg_teacher = await client.post("/api/v1/auth/register", json={
        "email": teacher_email,
        "password": "Password123!",
        "full_name": "Thầy Giáo Viên",
        "role": "TEACHER"
    })
    assert reg_teacher.status_code == 201

    # Login teacher
    login_tea = await client.post("/api/v1/auth/login", json={
        "email": teacher_email,
        "password": "Password123!"
    })
    teacher_token = login_tea.json()["access_token"]
    teacher_headers = {"Authorization": f"Bearer {teacher_token}"}

    # 3. Test Student Access
    res = await client.get("/api/v1/test-rbac/student-only", headers=student_headers)
    assert res.status_code == 200

    # Student trying teacher-only -> 403 Forbidden
    res = await client.get("/api/v1/test-rbac/teacher-only", headers=student_headers)
    assert res.status_code == 403

    # Student trying admin-only -> 403 Forbidden
    res = await client.get("/api/v1/test-rbac/admin-only", headers=student_headers)
    assert res.status_code == 403

    # 4. Test Teacher Access
    res = await client.get("/api/v1/test-rbac/teacher-only", headers=teacher_headers)
    assert res.status_code == 200

    # Teacher trying admin-only -> 403 Forbidden
    res = await client.get("/api/v1/test-rbac/admin-only", headers=teacher_headers)
    assert res.status_code == 403
