# FRONTEND API INTEGRATION GUIDE
## SMART LEARNING PRO — Phase 6: Frontend Foundation

**Base URL:** `http://localhost:8000/api/v1`

---

## 1. AUTHENTICATION MODULE

| Endpoint | Method | Frontend Service | Payload / Description |
|---|---|---|---|
| `/auth/login` | POST | `authApi.login(data)` | `{ email, password }` -> Returns `{ access_token, user }` and sets cookies. |
| `/auth/register` | POST | `authApi.register(data)` | `{ email, password, full_name, role, grade_level }` -> Creates user. |
| `/auth/me` | GET | `authApi.getMe()` | Returns current authenticated `User` profile. |
| `/auth/logout` | POST | `authApi.logout()` | Clears session cookie and client token. |

---

## 2. CLASSROOM MODULE

| Endpoint | Method | Frontend Service | Payload / Description |
|---|---|---|---|
| `/classrooms` | GET | `classroomsApi.getClassrooms()` | Role-filtered list (Student's enrolled or Teacher's owned). |
| `/classrooms/{id}` | GET | `classroomsApi.getClassroom(id)` | Detailed classroom metadata + member roster. |
| `/classrooms` | POST | `classroomsApi.createClassroom(data)` | `{ name, grade_id, description, max_students }`. Auto-generates unique code. |
| `/classrooms/join` | POST | `classroomsApi.joinClassroom(code)` | `{ code }` -> Student joins class by unique code (`SL-XXXXXX`). |
| `/classrooms/{id}/leave` | POST | `classroomsApi.leaveClassroom(id)` | Student voluntarily leaves class. |
| `/classrooms/{id}/regenerate-invite-code` | POST | `classroomsApi.regenerateInviteCode(id)` | Teacher generates new invite code. |
| `/classrooms/{id}/members/{student_id}` | DELETE | `classroomsApi.removeStudent(id, studentId)` | Teacher removes student from class. |

---

## 3. ASSIGNMENT & GRADEBOOK MODULE

| Endpoint | Method | Frontend Service | Payload / Description |
|---|---|---|---|
| `/classrooms/{id}/assignments` | GET | `assignmentsApi.getClassroomAssignments(id)` | List assignments in classroom. |
| `/classrooms/{id}/assignments` | POST | `assignmentsApi.createAssignment(id, data)` | `{ exam_id, title, description, due_date }`. |
| `/assignments/{id}/publish` | POST | `assignmentsApi.publishAssignment(id)` | Transitions assignment from `DRAFT` to `PUBLISHED`. |
| `/assignments/{id}/cancel` | POST | `assignmentsApi.cancelAssignment(id)` | Cancels assignment. |
| `/assignments/{id}/submissions` | GET | `assignmentsApi.getAssignmentSubmissions(id)` | Real-time classroom gradebook. |

---

## 4. CURRICULUM & QUESTION BANK MODULES

| Endpoint | Method | Frontend Service | Description |
|---|---|---|---|
| `/curriculum/grades` | GET | `curriculumApi.getGrades()` | Grades 6 to 12. |
| `/curriculum/subjects` | GET | `curriculumApi.getSubjects(params)` | Filterable by `grade_id`. |
| `/questions` | GET | `questionsApi.getQuestions(params)` | Search & filter by difficulty, subject. KaTeX ready. |
| `/exams` | GET | `examsApi.getExams(params)` | Teacher exam management list. |
| `/exams/available` | GET | `examsApi.getAvailableExams()` | Student practice exams with active windows. |
| `/exams` | POST | `examsApi.createExam(data)` | Creates new exam matrix. |
| `/exams/{id}/publish` | POST | `examsApi.publishExam(id)` | Publishes exam for practice / homework assignment. |
