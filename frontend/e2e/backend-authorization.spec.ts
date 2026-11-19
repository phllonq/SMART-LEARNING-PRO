import { test, expect } from "@playwright/test";

test.describe("Stage C — Backend Authorization & RBAC Matrix Verification", () => {
  const API_URL = "http://127.0.0.1:8000/api/v1";
  let studentToken: string;
  let teacherTokenA: string;
  let teacherTokenB: string;
  let adminToken: string;
  let classroomAId: string;
  let examAId: string;
  let questionAId: string;

  test.beforeAll(async ({ request }) => {
    const uniqueSuffix = Date.now().toString(36);

    // 1. Register & Login a fresh Student for clean attempt quotas
    const studentEmail = `student.auth.${uniqueSuffix}@smartlearning.vn`;
    await request.post(`${API_URL}/auth/register`, {
      data: {
        email: studentEmail,
        password: "StudentPassword123!",
        full_name: "Học Sinh Auth Test",
        role: "STUDENT",
        grade_level: 11,
      },
    });
    const studentLogin = await request.post(`${API_URL}/auth/login`, {
      data: {
        email: studentEmail,
        password: "StudentPassword123!",
      },
    });
    expect(studentLogin.status()).toBe(200);
    studentToken = (await studentLogin.json()).access_token;

    // 2. Login Teacher A
    const teacherALogin = await request.post(`${API_URL}/auth/login`, {
      data: {
        email: "giaovien.toan@smartlearning.vn",
        password: "TeacherPassword123!",
      },
    });
    expect(teacherALogin.status()).toBe(200);
    teacherTokenA = (await teacherALogin.json()).access_token;

    // 3. Register & Login Teacher B
    const teacherBEmail = `teacher.c.auth.${uniqueSuffix}@smartlearning.vn`;
    await request.post(`${API_URL}/auth/register`, {
      data: {
        email: teacherBEmail,
        password: "TeacherPassword123!",
        full_name: "Giáo Viên B Kiểm Thử",
        role: "TEACHER",
      },
    });
    const teacherBLogin = await request.post(`${API_URL}/auth/login`, {
      data: { email: teacherBEmail, password: "TeacherPassword123!" },
    });
    teacherTokenB = (await teacherBLogin.json()).access_token;

    // 4. Login Admin
    const adminLogin = await request.post(`${API_URL}/auth/login`, {
      data: {
        email: "admin@smartlearning.vn",
        password: "AdminSecurePassword123!",
      },
    });
    expect(adminLogin.status()).toBe(200);
    adminToken = (await adminLogin.json()).access_token;

    // 5. Create Teacher A resources for isolation testing
    const classRes = await request.post(`${API_URL}/classrooms`, {
      headers: { Authorization: `Bearer ${teacherTokenA}` },
      data: {
        name: `Lớp Auth Test ${uniqueSuffix}`,
        grade_id: 10,
        max_students: 35,
      },
    });
    expect(classRes.status()).toBe(201);
    classroomAId = (await classRes.json()).id;

    const examRes = await request.post(`${API_URL}/exams`, {
      headers: { Authorization: `Bearer ${teacherTokenA}` },
      data: {
        title: `Đề Auth Test ${uniqueSuffix}`,
        grade_id: 10,
        duration_minutes: 30,
        total_points: 10,
        passing_points: 5,
        status: "DRAFT",
      },
    });
    expect(examRes.status()).toBe(201);
    examAId = (await examRes.json()).id;

    const qRes = await request.post(`${API_URL}/questions`, {
      headers: { Authorization: `Bearer ${teacherTokenA}` },
      data: {
        content: `Câu hỏi kiểm thử ma trận $x^2 + 1 = 0$ ${uniqueSuffix}`,
        question_type: "SINGLE_CHOICE",
        difficulty: "RECOGNITION",
        grade_id: 10,
        points: 2.0,
        options: [
          { option_key: "A", content: "$x = \\pm i$", is_correct: true, order_index: 1 },
          { option_key: "B", content: "$x = 0$", is_correct: false, order_index: 2 },
        ],
        explanation: "Phương trình vô nghiệm thực",
      },
    });
    expect(qRes.status()).toBe(201);
    questionAId = (await qRes.json()).id;
  });

  test("1. Student calling Teacher-only endpoints receives 403 Forbidden", async ({ request }) => {
    // Student creating classroom
    const createClass = await request.post(`${API_URL}/classrooms`, {
      headers: { Authorization: `Bearer ${studentToken}` },
      data: { name: "Lớp Học Sinh Tự Tạo", grade_id: 10 },
    });
    expect(createClass.status()).toBe(403);

    // Student creating exam
    const createExam = await request.post(`${API_URL}/exams`, {
      headers: { Authorization: `Bearer ${studentToken}` },
      data: { title: "Đề Thi Học Sinh Tự Tạo", grade_id: 10 },
    });
    expect(createExam.status()).toBe(403);

    // Student creating question
    const createQuestion = await request.post(`${API_URL}/questions`, {
      headers: { Authorization: `Bearer ${studentToken}` },
      data: { content: "Câu hỏi student", question_type: "SINGLE_CHOICE" },
    });
    expect(createQuestion.status()).toBe(403);

    // Student creating assignment
    const createAssign = await request.post(`${API_URL}/classrooms/${classroomAId}/assignments`, {
      headers: { Authorization: `Bearer ${studentToken}` },
      data: { title: "Bài tập student", exam_id: examAId, due_date: "2026-12-31T23:59:00" },
    });
    expect(createAssign.status()).toBe(403);
  });

  test("2. Student accessing non-enrolled classroom receives 403 Forbidden", async ({ request }) => {
    // Classroom A was created by Teacher A; student is NOT a member
    const viewClass = await request.get(`${API_URL}/classrooms/${classroomAId}`, {
      headers: { Authorization: `Bearer ${studentToken}` },
    });
    expect(viewClass.status()).toBe(403);
    const err = await viewClass.json();
    expect(err.detail).toContain("Bạn không có quyền truy cập");

    // Student trying to view members of non-enrolled classroom
    const viewMembers = await request.get(`${API_URL}/classrooms/${classroomAId}/members`, {
      headers: { Authorization: `Bearer ${studentToken}` },
    });
    expect(viewMembers.status()).toBe(403);
  });

  test("3. Teacher B accessing Teacher A's classroom receives 403 Forbidden", async ({ request }) => {
    // Teacher B views Teacher A's class
    const viewClass = await request.get(`${API_URL}/classrooms/${classroomAId}`, {
      headers: { Authorization: `Bearer ${teacherTokenB}` },
    });
    expect(viewClass.status()).toBe(403);

    // Teacher B regenerates invite code for Teacher A's class
    const regenCode = await request.post(`${API_URL}/classrooms/${classroomAId}/regenerate-invite-code`, {
      headers: { Authorization: `Bearer ${teacherTokenB}` },
    });
    expect(regenCode.status()).toBe(403);

    // Teacher B archives Teacher A's class
    const archiveClass = await request.post(`${API_URL}/classrooms/${classroomAId}/archive`, {
      headers: { Authorization: `Bearer ${teacherTokenB}` },
    });
    expect(archiveClass.status()).toBe(403);
  });

  test("4. Teacher B modifying Teacher A's exam or question receives 403 Forbidden", async ({ request }) => {
    // Teacher B modifies Teacher A's exam
    const editExam = await request.patch(`${API_URL}/exams/${examAId}`, {
      headers: { Authorization: `Bearer ${teacherTokenB}` },
      data: { title: "Hacked by Teacher B" },
    });
    expect(editExam.status()).toBe(403);

    // Teacher B publishes Teacher A's exam
    const pubExam = await request.post(`${API_URL}/exams/${examAId}/publish`, {
      headers: { Authorization: `Bearer ${teacherTokenB}` },
    });
    expect(pubExam.status()).toBe(403);

    // Teacher B modifies Teacher A's question
    const editQ = await request.patch(`${API_URL}/questions/${questionAId}`, {
      headers: { Authorization: `Bearer ${teacherTokenB}` },
      data: { content: "Tampered question content" },
    });
    expect(editQ.status()).toBe(403);

    // Teacher B deletes Teacher A's question
    const delQ = await request.delete(`${API_URL}/questions/${questionAId}`, {
      headers: { Authorization: `Bearer ${teacherTokenB}` },
    });
    expect(delQ.status()).toBe(403);
  });

  test("5. Unauthenticated user calling protected endpoints receives 401 Unauthorized", async ({ request }) => {
    // Protected auth endpoint
    const meRes = await request.get(`${API_URL}/auth/me`);
    expect(meRes.status()).toBe(401);

    // Protected classrooms endpoint
    const classRes = await request.get(`${API_URL}/classrooms`);
    expect(classRes.status()).toBe(401);

    // Protected POST endpoint: creating a question requires authentication
    const questionsRes = await request.post(`${API_URL}/questions`, {
      data: { content: "Unauthorized question attempt" },
    });
    expect(questionsRes.status()).toBe(401);

    // Protected exams lobby
    const examsRes = await request.get(`${API_URL}/exams/available`);
    expect(examsRes.status()).toBe(401);

    // Protected assignments submissions
    const subRes = await request.get(`${API_URL}/assignments/my-submissions`);
    expect(subRes.status()).toBe(401);
  });

  test("6. Student cannot read answer key or explanation before allowed review", async ({ request }) => {
    // 1. Question Bank: Student querying questions must NOT receive is_correct or explanation
    const qbRes = await request.get(`${API_URL}/questions`, {
      headers: { Authorization: `Bearer ${studentToken}` },
    });
    expect(qbRes.status()).toBe(200);
    const qbData = await qbRes.json();
    for (const q of qbData.items) {
      expect(q).not.toHaveProperty("explanation");
      for (const opt of q.options) {
        expect(opt).not.toHaveProperty("is_correct");
      }
    }

    // 2. Active Exam: Student starts an attempt
    const startRes = await request.post(`${API_URL}/exams/exam-toan11-ptlg-45p/start`, {
      headers: { Authorization: `Bearer ${studentToken}` },
    });
    expect(startRes.status()).toBe(200);
    const startData = await startRes.json();
    const attemptId = startData.attempt_id;

    // Verify active attempt options do NOT leak is_correct
    for (const q of startData.questions) {
      expect(q).not.toHaveProperty("explanation");
      for (const opt of q.options) {
        expect(opt).not.toHaveProperty("is_correct");
      }
    }

    // 3. Trying to access review before submitting must be rejected (403 Forbidden)
    const earlyReview = await request.get(`${API_URL}/exams/attempts/${attemptId}/review`, {
      headers: { Authorization: `Bearer ${studentToken}` },
    });
    expect([400, 403]).toContain(earlyReview.status());
    const err = await earlyReview.json();
    expect(err.detail).toContain("chưa được nộp");
  });

  test("7. Admin has privileged override access across resources", async ({ request }) => {
    // Admin can view Teacher A's classroom details
    const viewClass = await request.get(`${API_URL}/classrooms/${classroomAId}`, {
      headers: { Authorization: `Bearer ${adminToken}` },
    });
    expect(viewClass.status()).toBe(200);

    // Admin can view Teacher A's exam details
    const viewExam = await request.get(`${API_URL}/exams/${examAId}`, {
      headers: { Authorization: `Bearer ${adminToken}` },
    });
    expect(viewExam.status()).toBe(200);
  });
});
