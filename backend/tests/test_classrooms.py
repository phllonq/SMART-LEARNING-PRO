import uuid
import pytest
import httpx


@pytest.mark.asyncio
async def test_classroom_creation_and_ownership(client: httpx.AsyncClient):
    """
    Test Teacher creates classroom, updates details, and validates
    Teacher ownership boundaries and Admin override.
    """
    # 1. Login Teacher A
    login_a = await client.post("/api/v1/auth/login", json={
        "email": "giaovien.toan@smartlearning.vn",
        "password": "TeacherPassword123!"
    })
    token_a = login_a.json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # 2. Teacher A creates a classroom
    class_payload = {
        "name": "Lớp 11 Toán Nâng Cao A1",
        "grade_id": 11,
        "description": "Luyện thi chuyên đề hình học và đại số 11",
        "max_students": 40
    }
    create_res = await client.post("/api/v1/classrooms", headers=headers_a, json=class_payload)
    assert create_res.status_code == 201
    classroom = create_res.json()
    classroom_id = classroom["id"]
    invite_code = classroom["code"]

    assert classroom["name"] == "Lớp 11 Toán Nâng Cao A1"
    assert classroom["status"] == "ACTIVE"
    assert classroom["is_archived"] is False
    assert invite_code.startswith("SL-")
    assert classroom["max_students"] == 40

    # 3. Teacher A updates classroom
    update_res = await client.patch(
        f"/api/v1/classrooms/{classroom_id}",
        headers=headers_a,
        json={"name": "Lớp 11 Toán Chuyên Sâu A1 - Đổi Tên", "max_students": 45}
    )
    assert update_res.status_code == 200
    assert update_res.json()["name"] == "Lớp 11 Toán Chuyên Sâu A1 - Đổi Tên"
    assert update_res.json()["max_students"] == 45

    # 4. Teacher A regenerates invite code
    regen_res = await client.post(f"/api/v1/classrooms/{classroom_id}/regenerate-invite-code", headers=headers_a)
    assert regen_res.status_code == 200
    new_code = regen_res.json()["code"]
    assert new_code != invite_code
    assert new_code.startswith("SL-")

    # 5. Teacher B registers and logs in
    email_b = f"teacher_b_{uuid.uuid4().hex[:6]}@smartlearning.vn"
    await client.post("/api/v1/auth/register", json={
        "email": email_b, "password": "Password123!", "full_name": "Giáo Viên B", "role": "TEACHER"
    })
    login_b = await client.post("/api/v1/auth/login", json={"email": email_b, "password": "Password123!"})
    headers_b = {"Authorization": f"Bearer {login_b.json()['access_token']}"}

    # Teacher B tries to edit Teacher A's classroom -> 403 Forbidden
    edit_b = await client.patch(f"/api/v1/classrooms/{classroom_id}", headers=headers_b, json={"name": "Hacked by Teacher B"})
    assert edit_b.status_code == 403
    assert "Bạn không có quyền" in edit_b.json()["detail"] or "giáo viên phụ trách" in edit_b.json()["detail"]

    # Teacher B tries to archive Teacher A's classroom -> 403 Forbidden
    arch_b = await client.post(f"/api/v1/classrooms/{classroom_id}/archive", headers=headers_b)
    assert arch_b.status_code == 403

    # 6. Admin Override: Admin can edit and manage
    login_admin = await client.post("/api/v1/auth/login", json={
        "email": "admin@smartlearning.vn", "password": "AdminSecurePassword123!"
    })
    headers_admin = {"Authorization": f"Bearer {login_admin.json()['access_token']}"}

    edit_admin = await client.patch(
        f"/api/v1/classrooms/{classroom_id}",
        headers=headers_admin,
        json={"name": "Lớp Chuẩn Sở Giáo Dục"}
    )
    assert edit_admin.status_code == 200
    assert edit_admin.json()["name"] == "Lớp Chuẩn Sở Giáo Dục"


@pytest.mark.asyncio
async def test_student_join_and_membership_rules(client: httpx.AsyncClient):
    """
    Test student joining with code, duplicate prevention, capacity check,
    archived classroom rejection, member listing, and leaving classroom.
    """
    # 1. Login Teacher A & create classroom
    login_teacher = await client.post("/api/v1/auth/login", json={
        "email": "giaovien.toan@smartlearning.vn",
        "password": "TeacherPassword123!"
    })
    headers_teacher = {"Authorization": f"Bearer {login_teacher.json()['access_token']}"}

    create_res = await client.post("/api/v1/classrooms", headers=headers_teacher, json={
        "name": "Lớp 12 Hóa Học",
        "grade_id": 12,
        "max_students": 2  # low capacity to test limit
    })
    classroom = create_res.json()
    classroom_id = classroom["id"]
    code = classroom["code"]

    # 2. Login Student 1
    login_stu1 = await client.post("/api/v1/auth/login", json={
        "email": "hocsinh.an@smartlearning.vn",
        "password": "StudentPassword123!"
    })
    headers_stu1 = {"Authorization": f"Bearer {login_stu1.json()['access_token']}"}

    # 3. Test Invalid invite code -> 404
    bad_join = await client.post("/api/v1/classrooms/join", headers=headers_stu1, json={"code": "INVALID99"})
    assert bad_join.status_code == 404

    # 4. Student 1 joins with valid code -> 200 OK
    join_ok = await client.post("/api/v1/classrooms/join", headers=headers_stu1, json={"code": code})
    assert join_ok.status_code == 200
    assert join_ok.json()["id"] == classroom_id

    # 5. Duplicate membership check: Student 1 attempts to join again -> 409 Conflict
    dup_join = await client.post("/api/v1/classrooms/join", headers=headers_stu1, json={"code": code})
    assert dup_join.status_code == 409
    assert "Bạn đã là thành viên" in dup_join.json()["detail"]

    # 6. Student 2 registers and joins -> 200 OK (reaches max capacity = 2)
    email_stu2 = f"student2_{uuid.uuid4().hex[:6]}@smartlearning.vn"
    await client.post("/api/v1/auth/register", json={
        "email": email_stu2, "password": "Password123!", "full_name": "Học Sinh 2", "role": "STUDENT"
    })
    login_stu2 = await client.post("/api/v1/auth/login", json={"email": email_stu2, "password": "Password123!"})
    headers_stu2 = {"Authorization": f"Bearer {login_stu2.json()['access_token']}"}

    join_stu2 = await client.post("/api/v1/classrooms/join", headers=headers_stu2, json={"code": code})
    assert join_stu2.status_code == 200

    # 7. Student 3 registers and tries to join -> rejected due to capacity limit (max 2)
    email_stu3 = f"student3_{uuid.uuid4().hex[:6]}@smartlearning.vn"
    await client.post("/api/v1/auth/register", json={
        "email": email_stu3, "password": "Password123!", "full_name": "Học Sinh 3", "role": "STUDENT"
    })
    login_stu3 = await client.post("/api/v1/auth/login", json={"email": email_stu3, "password": "Password123!"})
    headers_stu3 = {"Authorization": f"Bearer {login_stu3.json()['access_token']}"}

    join_overflow = await client.post("/api/v1/classrooms/join", headers=headers_stu3, json={"code": code})
    assert join_overflow.status_code == 403
    assert "sĩ số tối đa" in join_overflow.json()["detail"]

    # 8. Check member roster
    members_res = await client.get(f"/api/v1/classrooms/{classroom_id}/members", headers=headers_teacher)
    assert members_res.status_code == 200
    members = members_res.json()
    assert len(members) == 2
    student_names = [m["student_name"] for m in members]
    assert "Nguyễn Văn An" in student_names
    assert "Học Sinh 2" in student_names

    # 9. Student 3 (non-member) tries to access classroom details -> 403 Forbidden
    non_member_access = await client.get(f"/api/v1/classrooms/{classroom_id}", headers=headers_stu3)
    assert non_member_access.status_code == 403

    # 10. Student 2 leaves the classroom
    leave_res = await client.post(f"/api/v1/classrooms/{classroom_id}/leave", headers=headers_stu2)
    assert leave_res.status_code == 204

    # Now Student 3 can join because a spot opened up
    join_now_ok = await client.post("/api/v1/classrooms/join", headers=headers_stu3, json={"code": code})
    assert join_now_ok.status_code == 200

    # 11. Teacher archives classroom -> no one can join archived classroom
    arch_res = await client.post(f"/api/v1/classrooms/{classroom_id}/archive", headers=headers_teacher)
    assert arch_res.status_code == 200
    assert arch_res.json()["is_archived"] is True

    email_stu4 = f"student4_{uuid.uuid4().hex[:6]}@smartlearning.vn"
    await client.post("/api/v1/auth/register", json={
        "email": email_stu4, "password": "Password123!", "full_name": "Học Sinh 4", "role": "STUDENT"
    })
    login_stu4 = await client.post("/api/v1/auth/login", json={"email": email_stu4, "password": "Password123!"})
    headers_stu4 = {"Authorization": f"Bearer {login_stu4.json()['access_token']}"}

    join_arch = await client.post("/api/v1/classrooms/join", headers=headers_stu4, json={"code": code})
    assert join_arch.status_code == 403
    assert "lưu trữ" in join_arch.json()["detail"]
