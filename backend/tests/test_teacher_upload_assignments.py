import io
import json
import uuid
import zipfile
from datetime import datetime, timedelta, timezone

import httpx
import pytest


def _build_minimal_xlsx(rows: list[list[str]]) -> bytes:
    """Create a valid minimal .xlsx workbook in memory using stdlib zipfile."""
    buf = io.BytesIO()

    def col_letter(idx: int) -> str:
        res = ""
        n = idx + 1
        while n > 0:
            n, rem = divmod(n - 1, 26)
            res = chr(65 + rem) + res
        return res

    def xml_escape(val: str) -> str:
        return (
            val.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )

    sheet_rows = []
    for r_idx, row in enumerate(rows, start=1):
        cells = []
        for c_idx, cell_val in enumerate(row):
            ref = f"{col_letter(c_idx)}{r_idx}"
            cells.append(
                f'<c r="{ref}" t="inlineStr"><is><t>{xml_escape(cell_val)}</t></is></c>'
            )
        sheet_rows.append(f'<row r="{r_idx}">{"".join(cells)}</row>')

    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(sheet_rows)}</sheetData>'
        "</worksheet>"
    )
    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets>'
        "</workbook>"
    )
    rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
        "</Relationships>"
    )
    root_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        "</Relationships>"
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        "</Types>"
    )

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", root_rels)
        zf.writestr("xl/workbook.xml", workbook_xml)
        zf.writestr("xl/_rels/workbook.xml.rels", rels_xml)
        zf.writestr("xl/worksheets/sheet1.xml", sheet_xml)

    return buf.getvalue()


def _build_minimal_docx(paragraphs: list[str]) -> bytes:
    """Create a valid minimal .docx document in memory using stdlib zipfile."""
    buf = io.BytesIO()

    def xml_escape(val: str) -> str:
        return (
            val.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

    p_xml = "".join(
        f"<w:p><w:r><w:t>{xml_escape(p)}</w:t></w:r></w:p>"
        for p in paragraphs
    )
    doc_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{p_xml}</w:body>"
        "</w:document>"
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/types">'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        "</Types>"
    )
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("word/document.xml", doc_xml)
    return buf.getvalue()


async def _login_headers(client: httpx.AsyncClient, email: str, password: str) -> dict[str, str]:
    res = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


@pytest.mark.asyncio
async def test_import_questions_and_exam_from_files(client: httpx.AsyncClient):
    """Test CSV template, dry_run preview, CSV/JSON/XLSX/DOCX question import & Exam import."""
    teacher_headers = await _login_headers(
        client, "giaovien.toan@smartlearning.vn", "TeacherPassword123!"
    )
    student_headers = await _login_headers(
        client, "hocsinh.an@smartlearning.vn", "StudentPassword123!"
    )

    # 1. Template download RBAC
    tpl_stu = await client.get("/api/v1/questions/import-template/csv", headers=student_headers)
    assert tpl_stu.status_code == 403
    tpl_tea = await client.get("/api/v1/questions/import-template/csv", headers=teacher_headers)
    assert tpl_tea.status_code == 200
    assert "content,question_type" in tpl_tea.text

    # 2. CSV dry_run with 1 valid + 1 invalid row
    csv_bytes = (
        "\ufeff"
        "content,question_type,difficulty_level,option_a,option_b,option_c,option_d,correct,explanation,hint,tags\n"
        '"Tính $2 + 3$:",SINGLE_CHOICE,RECOGNITION,"4","5","6","7",B,"2 + 3 = 5","Cộng nhẩm","toan"\n'
        '"Câu thiếu đáp án đúng",SINGLE_CHOICE,RECOGNITION,"1","2","","",Z,"","",""\n'
    ).encode("utf-8")

    dry_res = await client.post(
        "/api/v1/questions/import",
        headers=teacher_headers,
        data={"dry_run": "true", "is_public": "true"},
        files={"file": ("cau_hoi.csv", csv_bytes, "text/csv")},
    )
    assert dry_res.status_code == 200, dry_res.text
    dry_data = dry_res.json()
    assert dry_data["dry_run"] is True
    assert dry_data["total_detected"] == 2
    assert dry_data["imported_count"] == 0
    assert dry_data["failed_count"] == 1
    assert len(dry_data["preview_questions"]) == 1

    # 3. Student cannot import questions
    stu_imp = await client.post(
        "/api/v1/questions/import",
        headers=student_headers,
        files={"file": ("cau_hoi.csv", csv_bytes, "text/csv")},
    )
    assert stu_imp.status_code == 403

    # 4. JSON real import
    json_bytes = json.dumps(
        [
            {
                "content": f"Giá trị của $\\sqrt{{16}}$ là? ({uuid.uuid4().hex[:6]})",
                "question_type": "SINGLE_CHOICE",
                "difficulty_level": "RECOGNITION",
                "options": [
                    {"option_key": "A", "content": "2", "is_correct": False},
                    {"option_key": "B", "content": "4", "is_correct": True},
                    {"option_key": "C", "content": "8", "is_correct": False},
                ],
                "explanation": "$\\sqrt{16} = 4$",
            }
        ],
        ensure_ascii=False,
    ).encode("utf-8")

    json_res = await client.post(
        "/api/v1/questions/import",
        headers=teacher_headers,
        data={"dry_run": "false", "is_public": "true"},
        files={"file": ("questions.json", json_bytes, "application/json")},
    )
    assert json_res.status_code == 200, json_res.text
    assert json_res.json()["imported_count"] == 1
    assert len(json_res.json()["questions"]) == 1

    # 5. XLSX question import
    xlsx_bytes = _build_minimal_xlsx(
        [
            ["content", "option_a", "option_b", "option_c", "option_d", "correct", "explanation"],
            [f"Số nguyên tố chẵn duy nhất là? ({uuid.uuid4().hex[:4]})", "1", "2", "3", "4", "B", "Số 2"],
        ]
    )
    xlsx_res = await client.post(
        "/api/v1/questions/import",
        headers=teacher_headers,
        files={
            "file": (
                "bank.xlsx",
                xlsx_bytes,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert xlsx_res.status_code == 200, xlsx_res.text
    assert xlsx_res.json()["imported_count"] == 1

    # 6. DOCX exam import (creates Exam + ExamQuestion and publishes immediately)
    docx_bytes = _build_minimal_docx(
        [
            f"Câu 1: Nghiệm của phương trình $x - 5 = 0$ là: ({uuid.uuid4().hex[:4]})",
            "A. x = 3",
            "B. x = 5",
            "C. x = -5",
            "D. x = 0",
            "Đáp án: B",
            "Lời giải: Chuyển vế ta được x = 5.",
            f"Câu 2: Đạo hàm của $x^2$ là: ({uuid.uuid4().hex[:4]})",
            "A. 2x",
            "B. x",
            "C. 2",
            "D. x^2",
            "Đáp án: A",
        ]
    )
    exam_title = f"Đề Word Tự Động {uuid.uuid4().hex[:6]}"
    exam_res = await client.post(
        "/api/v1/exams/import",
        headers=teacher_headers,
        data={
            "title": exam_title,
            "grade_id": "10",
            "duration_minutes": "15",
            "total_points": "10",
            "passing_points": "5",
            "publish_immediately": "true",
        },
        files={
            "file": (
                "de_thi.docx",
                docx_bytes,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert exam_res.status_code == 201, exam_res.text
    exam_data = exam_res.json()
    assert exam_data["imported_questions_count"] == 2
    assert exam_data["exam"]["status"] == "PUBLISHED"
    assert exam_data["exam"]["question_count"] == 2

    # Student can view and start the imported exam
    start_res = await client.post(
        f"/api/v1/exams/{exam_data['exam']['id']}/start", headers=student_headers
    )
    assert start_res.status_code == 200, start_res.text
    assert start_res.json()["total_questions"] == 2


@pytest.mark.asyncio
async def test_file_assignment_upload_download_submission_and_grading(client: httpx.AsyncClient):
    """Test teacher uploading file assignment, student downloading & submitting solution, and teacher grading."""
    teacher_headers = await _login_headers(
        client, "giaovien.toan@smartlearning.vn", "TeacherPassword123!"
    )
    student_headers = await _login_headers(
        client, "hocsinh.an@smartlearning.vn", "StudentPassword123!"
    )

    # Register outsider student (not in classroom)
    outsider_email = f"outsider_{uuid.uuid4().hex[:6]}@smartlearning.vn"
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": outsider_email,
            "password": "Password123!",
            "full_name": "Học Sinh Ngoài Lớp",
            "role": "STUDENT",
        },
    )
    assert reg.status_code in (200, 201), reg.text
    outsider_headers = await _login_headers(client, outsider_email, "Password123!")

    # Teacher creates classroom and Student An joins
    cls_res = await client.post(
        "/api/v1/classrooms",
        headers=teacher_headers,
        json={"name": f"Lớp Upload {uuid.uuid4().hex[:5]}", "grade_id": 10},
    )
    assert cls_res.status_code == 201, cls_res.text
    classroom_id = cls_res.json()["id"]
    invite_code = cls_res.json()["code"]

    join_res = await client.post(
        "/api/v1/classrooms/join",
        headers=student_headers,
        json={"code": invite_code},
    )
    assert join_res.status_code == 200, join_res.text

    due_date = (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()

    # 1. Reject masqueraded executable claiming .pdf extension (MZ magic bytes)
    bad_upload = await client.post(
        f"/api/v1/classrooms/{classroom_id}/assignments/upload",
        headers=teacher_headers,
        data={"title": "File giả mạo", "due_date": due_date},
        files={"file": ("baitap.pdf", b"MZ\x90\x00fake-exe", "application/pdf")},
    )
    assert bad_upload.status_code == 400

    # 2. Teacher uploads valid PDF assignment
    pdf_bytes = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n"
    upload_res = await client.post(
        f"/api/v1/classrooms/{classroom_id}/assignments/upload",
        headers=teacher_headers,
        data={
            "title": "Phiếu bài tập hình học không gian",
            "description": "Tải file PDF về làm rồi chụp ảnh hoặc xuất PDF nộp lại.",
            "due_date": due_date,
            "total_points": "10",
            "allow_late_submission": "false",
            "status": "PUBLISHED",
        },
        files={"file": ("Phieu_Bai_Tap_Hinh_Hoc.pdf", pdf_bytes, "application/pdf")},
    )
    assert upload_res.status_code == 201, upload_res.text
    assign = upload_res.json()
    assignment_id = assign["id"]
    assert assign["assignment_type"] == "FILE"
    assert assign["exam_id"] is None
    assert assign["has_attachment"] is True
    assert assign["attachment_name"] == "Phieu_Bai_Tap_Hinh_Hoc.pdf"

    # 3. Student member downloads attachment; outsider gets 403
    dl_stu = await client.get(
        f"/api/v1/assignments/{assignment_id}/attachment",
        headers=student_headers,
    )
    assert dl_stu.status_code == 200
    assert dl_stu.content == pdf_bytes

    dl_out = await client.get(
        f"/api/v1/assignments/{assignment_id}/attachment",
        headers=outsider_headers,
    )
    assert dl_out.status_code == 403

    # 4. Calling online exam /start on FILE assignment returns 403 cleanly
    start_file = await client.post(
        f"/api/v1/assignments/{assignment_id}/start",
        headers=student_headers,
    )
    assert start_file.status_code == 403

    # 5. Student uploads PNG solution file
    png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
    sub_res = await client.post(
        f"/api/v1/assignments/{assignment_id}/file-submission",
        headers=student_headers,
        data={"note": "Em nộp bài giải tay qua ảnh chụp."},
        files={"file": ("bai_giai_cua_an.png", png_bytes, "image/png")},
    )
    assert sub_res.status_code == 201, sub_res.text
    sub_data = sub_res.json()
    sub_id = sub_data["id"]
    assert sub_data["status"] == "SUBMITTED"
    assert sub_data["file_name"] == "bai_giai_cua_an.png"

    # 6. Outsider cannot download Student An's submission; Teacher can
    out_dl_sub = await client.get(
        f"/api/v1/assignments/{assignment_id}/file-submissions/{sub_id}/download",
        headers=outsider_headers,
    )
    assert out_dl_sub.status_code == 403

    tea_dl_sub = await client.get(
        f"/api/v1/assignments/{assignment_id}/file-submissions/{sub_id}/download",
        headers=teacher_headers,
    )
    assert tea_dl_sub.status_code == 200
    assert tea_dl_sub.content == png_bytes

    # 7. Teacher lists submissions and grades Student An's submission
    subs_list = await client.get(
        f"/api/v1/assignments/{assignment_id}/submissions",
        headers=teacher_headers,
    )
    assert subs_list.status_code == 200, subs_list.text
    subs_payload = subs_list.json()
    assert subs_payload["assignment_type"] == "FILE"
    assert subs_payload["submitted_count"] == 1
    assert subs_payload["items"][0]["file_submission"]["id"] == sub_id

    grade_res = await client.post(
        f"/api/v1/assignments/{assignment_id}/file-submissions/{sub_id}/grade",
        headers=teacher_headers,
        json={"score": 9.5, "teacher_feedback": "Trình bày rất rõ ràng!"},
    )
    assert grade_res.status_code == 200, grade_res.text
    graded = grade_res.json()
    assert graded["status"] == "GRADED"
    assert graded["score"] == 9.5

    # 8. Student sees updated grade and feedback in classroom assignment summary
    stu_list = await client.get(
        f"/api/v1/classrooms/{classroom_id}/assignments",
        headers=student_headers,
    )
    assert stu_list.status_code == 200
    matched = [item for item in stu_list.json() if item["id"] == assignment_id][0]
    assert matched["my_status"] == "GRADED"
    assert matched["my_score"] == 9.5
    assert matched["my_file_submission"]["teacher_feedback"] == "Trình bày rất rõ ràng!"

    # 9. Overdue FILE assignment without allow_late_submission blocks student upload
    past_due = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    late_assign_res = await client.post(
        f"/api/v1/classrooms/{classroom_id}/assignments/upload",
        headers=teacher_headers,
        data={
            "title": "Bài tập đã quá hạn",
            "due_date": past_due,
            "allow_late_submission": "false",
            "status": "PUBLISHED",
        },
        files={"file": ("past.pdf", pdf_bytes, "application/pdf")},
    )
    assert late_assign_res.status_code == 201
    late_sub = await client.post(
        f"/api/v1/assignments/{late_assign_res.json()['id']}/file-submission",
        headers=student_headers,
        files={"file": ("late.png", png_bytes, "image/png")},
    )
    assert late_sub.status_code == 403
