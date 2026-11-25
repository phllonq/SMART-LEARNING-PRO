"""
Multi-Format Question & Exam Importer - SMART LEARNING PRO
Supports pure-Python offline parsing of:
  - .json (structured JSON list or {"questions": [...]})
  - .csv (UTF-8 / UTF-8-SIG delimited spreadsheet)
  - .xlsx (Office Open XML spreadsheet via zipfile + ElementTree)
  - .docx (Office Open XML Word document via zipfile + ElementTree)
Validates every imported question strictly through QuestionCreate schemas.
"""

import csv
import io
import json
import re
import zipfile
import zlib
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from fastapi import HTTPException, status

from app.core.storage import validate_upload_bytes
from app.modules.questions.ai_extractor import (
    extract_questions_with_ai,
    is_ai_extraction_available,
)
from app.modules.questions.models import DifficultyLevel, QuestionType
from app.modules.questions.schemas import QuestionCreate, QuestionOptionCreate

ALLOWED_IMPORT_EXTENSIONS: Set[str] = {".json", ".csv", ".xlsx", ".docx", ".txt"}
ALLOWED_CONVERT_EXTENSIONS: Set[str] = {
    ".json",
    ".csv",
    ".xlsx",
    ".docx",
    ".txt",
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
}
MAX_IMPORT_FILE_SIZE_BYTES: int = 15 * 1024 * 1024  # 15 MB

_DIFFICULTY_MAP: Dict[str, DifficultyLevel] = {
    "RECOGNITION": DifficultyLevel.RECOGNITION,
    "NHAN BIET": DifficultyLevel.RECOGNITION,
    "NHẬN BIẾT": DifficultyLevel.RECOGNITION,
    "EASY": DifficultyLevel.RECOGNITION,
    "COMPREHENSION": DifficultyLevel.COMPREHENSION,
    "THONG HIEU": DifficultyLevel.COMPREHENSION,
    "THÔNG HIỂU": DifficultyLevel.COMPREHENSION,
    "MEDIUM": DifficultyLevel.COMPREHENSION,
    "APPLICATION": DifficultyLevel.APPLICATION,
    "VAN DUNG": DifficultyLevel.APPLICATION,
    "VẬN DỤNG": DifficultyLevel.APPLICATION,
    "HARD": DifficultyLevel.APPLICATION,
    "HIGH_APPLICATION": DifficultyLevel.HIGH_APPLICATION,
    "VAN DUNG CAO": DifficultyLevel.HIGH_APPLICATION,
    "VẬN DỤNG CAO": DifficultyLevel.HIGH_APPLICATION,
}

_TYPE_MAP: Dict[str, QuestionType] = {
    "SINGLE_CHOICE": QuestionType.SINGLE_CHOICE,
    "TRAC NGHIEM": QuestionType.SINGLE_CHOICE,
    "TRẮC NGHIỆM": QuestionType.SINGLE_CHOICE,
    "MULTIPLE_CHOICE": QuestionType.MULTIPLE_CHOICE,
    "NHIEU DAP AN": QuestionType.MULTIPLE_CHOICE,
    "NHIỀU ĐÁP ÁN": QuestionType.MULTIPLE_CHOICE,
    "TRUE_FALSE": QuestionType.TRUE_FALSE,
    "DUNG SAI": QuestionType.TRUE_FALSE,
    "ĐÚNG SAI": QuestionType.TRUE_FALSE,
    "SHORT_ANSWER": QuestionType.SHORT_ANSWER,
    "TRA LOI NGAN": QuestionType.SHORT_ANSWER,
    "TRẢ LỜI NGẮN": QuestionType.SHORT_ANSWER,
    "NUMERIC": QuestionType.NUMERIC,
    "ESSAY": QuestionType.ESSAY,
    "TU LUAN": QuestionType.ESSAY,
    "TỰ LUẬN": QuestionType.ESSAY,
}


@dataclass
class ParseErrorItem:
    index: int
    raw_preview: str
    error: str


@dataclass
class ParsedImportResult:
    valid_questions: List[QuestionCreate]
    errors: List[ParseErrorItem]
    total_detected: int


@dataclass
class ParsedDraftResult:
    draft_questions: List[Dict[str, Any]]
    errors: List[ParseErrorItem]
    total_detected: int
    extraction_method: str
    ai_used: bool = False
    ai_available: bool = False


@dataclass
class _RichLine:
    text: str
    accented_keys: Set[str] = field(default_factory=set)
    bold_keys: Set[str] = field(default_factory=set)
    whole_line_accented: bool = False
    whole_line_bold: bool = False


def _normalize_header(key: str) -> str:
    return re.sub(r"[\s\-]+", "_", key.strip().lower())


def _parse_difficulty(val: Optional[str]) -> DifficultyLevel:
    if not val:
        return DifficultyLevel.COMPREHENSION
    norm = val.strip().upper()
    if norm in _DIFFICULTY_MAP:
        return _DIFFICULTY_MAP[norm]
    norm_spaces = re.sub(r"[_\-]+", " ", norm)
    return _DIFFICULTY_MAP.get(norm_spaces, DifficultyLevel.COMPREHENSION)


def _parse_question_type(val: Optional[str], default: QuestionType = QuestionType.SINGLE_CHOICE) -> QuestionType:
    if not val:
        return default
    norm = val.strip().upper()
    if norm in _TYPE_MAP:
        return _TYPE_MAP[norm]
    norm_spaces = re.sub(r"[_\-]+", " ", norm)
    return _TYPE_MAP.get(norm_spaces, default)


def _parse_correct_keys(correct_raw: Any) -> Set[str]:
    if correct_raw is None:
        return set()
    if isinstance(correct_raw, list):
        return {str(x).strip().upper() for x in correct_raw if str(x).strip()}
    text = str(correct_raw).strip()
    if not text:
        return set()
    parts = re.split(r"[,;/|\s]+", text)
    return {p.strip().upper() for p in parts if p.strip()}


def _build_question_from_row(
    row: Dict[str, Any],
    topic_id: Optional[str],
    lesson_id: Optional[str],
    is_public: bool,
) -> QuestionCreate:
    norm_row = {_normalize_header(str(k)): v for k, v in row.items() if k is not None}

    content = (
        norm_row.get("content")
        or norm_row.get("cau_hoi")
        or norm_row.get("câu_hỏi")
        or norm_row.get("noi_dung")
        or norm_row.get("nội_dung")
        or norm_row.get("question")
        or ""
    )
    content_str = str(content).strip()
    if not content_str:
        raise ValueError("Thiếu nội dung câu hỏi (content).")

    raw_type = (
        norm_row.get("question_type")
        or norm_row.get("loai_cau_hoi")
        or norm_row.get("loại_câu_hỏi")
        or norm_row.get("loai")
        or norm_row.get("type")
    )
    raw_diff = (
        norm_row.get("difficulty_level")
        or norm_row.get("do_kho")
        or norm_row.get("độ_khó")
        or norm_row.get("muc_do")
        or norm_row.get("difficulty")
    )
    explanation = norm_row.get("explanation") or norm_row.get("loi_giai") or norm_row.get("lời_giải") or norm_row.get("giai_thich")
    hint = norm_row.get("hint") or norm_row.get("goi_y") or norm_row.get("gợi_ý")
    tags = norm_row.get("tags") or norm_row.get("the")

    q_type = _parse_question_type(str(raw_type) if raw_type else None)
    difficulty = _parse_difficulty(str(raw_diff) if raw_diff else None)

    options_out: List[QuestionOptionCreate] = []

    # 1. Structured options list (JSON)
    raw_options = norm_row.get("options")
    correct_raw = (
        norm_row.get("correct")
        or norm_row.get("correct_answers")
        or norm_row.get("correct_answer")
        or norm_row.get("dap_an")
        or norm_row.get("đáp_án")
        or norm_row.get("dap_an_dung")
        or norm_row.get("answer")
    )
    correct_keys = _parse_correct_keys(correct_raw)

    if isinstance(raw_options, list) and raw_options:
        for idx, opt in enumerate(raw_options):
            if isinstance(opt, dict):
                key = str(opt.get("option_key") or opt.get("key") or chr(65 + idx)).strip().upper()
                opt_content = str(opt.get("content") or opt.get("text") or "").strip()
                is_corr = bool(opt.get("is_correct")) or (key in correct_keys)
                if opt_content:
                    options_out.append(
                        QuestionOptionCreate(
                            option_key=key,
                            content=opt_content,
                            is_correct=is_corr,
                            order_index=int(opt.get("order_index", idx)),
                        )
                    )
    elif isinstance(raw_options, dict) and raw_options:
        for idx, (k, v) in enumerate(raw_options.items()):
            key = str(k).strip().upper()
            opt_content = str(v).strip()
            if opt_content:
                options_out.append(
                    QuestionOptionCreate(
                        option_key=key,
                        content=opt_content,
                        is_correct=(key in correct_keys),
                        order_index=idx,
                    )
                )
    else:
        # 2. Tabular option_a / a .. option_f / f columns
        col_aliases = [
            ("A", ("option_a", "a", "dap_an_a", "phuong_an_a")),
            ("B", ("option_b", "b", "dap_an_b", "phuong_an_b")),
            ("C", ("option_c", "c", "dap_an_c", "phuong_an_c")),
            ("D", ("option_d", "d", "dap_an_d", "phuong_an_d")),
            ("E", ("option_e", "e", "dap_an_e", "phuong_an_e")),
            ("F", ("option_f", "f", "dap_an_f", "phuong_an_f")),
        ]
        for idx, (key, keys_tuple) in enumerate(col_aliases):
            val = None
            for alias in keys_tuple:
                if alias in norm_row and norm_row[alias] is not None and str(norm_row[alias]).strip():
                    val = str(norm_row[alias]).strip()
                    break
            if val is not None:
                options_out.append(
                    QuestionOptionCreate(
                        option_key=key,
                        content=val,
                        is_correct=(key in correct_keys),
                        order_index=idx,
                    )
                )

    # Auto-adjust MULTIPLE_CHOICE if multiple correct keys specified and type defaulted to SINGLE_CHOICE
    if not raw_type and len(correct_keys) > 1 and len(options_out) >= 2:
        q_type = QuestionType.MULTIPLE_CHOICE

    # Handle SHORT_ANSWER / NUMERIC without option columns
    if not options_out and q_type in (QuestionType.SHORT_ANSWER, QuestionType.NUMERIC) and correct_raw is not None:
        ans_text = str(correct_raw).strip()
        if ans_text:
            options_out.append(
                QuestionOptionCreate(option_key="A", content=ans_text, is_correct=True, order_index=0)
            )
    elif not options_out and not raw_type and correct_raw is not None and str(correct_raw).strip():
        q_type = QuestionType.SHORT_ANSWER
        options_out.append(
            QuestionOptionCreate(option_key="A", content=str(correct_raw).strip(), is_correct=True, order_index=0)
        )

    return QuestionCreate(
        topic_id=topic_id,
        lesson_id=lesson_id,
        question_type=q_type,
        content=content_str,
        difficulty_level=difficulty,
        explanation=str(explanation).strip() if explanation is not None and str(explanation).strip() else None,
        hint=str(hint).strip() if hint is not None and str(hint).strip() else None,
        tags=str(tags).strip() if tags is not None and str(tags).strip() else None,
        is_public=is_public,
        options=options_out,
    )


def _parse_json_bytes(
    content: bytes, topic_id: Optional[str], lesson_id: Optional[str], is_public: bool
) -> ParsedImportResult:
    try:
        payload = json.loads(content.decode("utf-8-sig"))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tệp JSON không hợp lệ: {exc}",
        )

    if isinstance(payload, dict) and isinstance(payload.get("questions"), list):
        items = payload["questions"]
    elif isinstance(payload, list):
        items = payload
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tệp JSON phải là mảng câu hỏi [...] hoặc đối tượng {\"questions\": [...]}.",
        )

    valid: List[QuestionCreate] = []
    errors: List[ParseErrorItem] = []

    for idx, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            errors.append(ParseErrorItem(index=idx, raw_preview=str(item)[:120], error="Phần tử phải là object JSON."))
            continue
        try:
            valid.append(_build_question_from_row(item, topic_id, lesson_id, is_public))
        except Exception as exc:
            errors.append(
                ParseErrorItem(
                    index=idx,
                    raw_preview=str(item.get("content") or item)[:120],
                    error=str(exc),
                )
            )

    return ParsedImportResult(valid_questions=valid, errors=errors, total_detected=len(items))


def _parse_csv_bytes(
    content: bytes, topic_id: Optional[str], lesson_id: Optional[str], is_public: bool
) -> ParsedImportResult:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("latin-1")

    sample = text[:2048]
    delimiter = ","
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        delimiter = dialect.delimiter
    except Exception:
        delimiter = ";" if sample.count(";") > sample.count(",") else ","

    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    if not reader.fieldnames:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tệp CSV không có dòng tiêu đề cột.",
        )

    valid: List[QuestionCreate] = []
    errors: List[ParseErrorItem] = []
    total = 0

    for row_idx, row in enumerate(reader, start=2):
        # Skip completely empty trailing rows
        if not any(v is not None and str(v).strip() for v in row.values()):
            continue
        total += 1
        try:
            valid.append(_build_question_from_row(row, topic_id, lesson_id, is_public))
        except Exception as exc:
            preview = str(row.get("content") or row.get("cau_hoi") or list(row.values())[:2])[:120]
            errors.append(ParseErrorItem(index=row_idx, raw_preview=preview, error=str(exc)))

    return ParsedImportResult(valid_questions=valid, errors=errors, total_detected=total)


def _col_ref_to_index(cell_ref: str) -> int:
    letters = "".join(ch for ch in cell_ref if ch.isalpha()).upper()
    idx = 0
    for ch in letters:
        idx = idx * 26 + (ord(ch) - ord("A") + 1)
    return max(0, idx - 1)


def _parse_xlsx_bytes(
    content: bytes, topic_id: Optional[str], lesson_id: Optional[str], is_public: bool
) -> ParsedImportResult:
    try:
        zf = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tệp .xlsx bị lỗi hoặc không đúng định dạng OOXML.",
        )

    with zf:
        shared_strings: List[str] = []
        if "xl/sharedStrings.xml" in zf.namelist():
            ss_root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            for si in ss_root.iter():
                if si.tag.endswith("}si") or si.tag == "si":
                    parts = [t.text or "" for t in si.iter() if t.tag.endswith("}t") or t.tag == "t"]
                    shared_strings.append("".join(parts))

        sheet_names = sorted(
            name for name in zf.namelist() if re.match(r"xl/worksheets/sheet\d+\.xml$", name)
        )
        if not sheet_names:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tệp .xlsx không chứa trang tính (worksheet) hợp lệ.",
            )

        sheet_root = ET.fromstring(zf.read(sheet_names[0]))
        rows_matrix: List[List[str]] = []

        for row_el in sheet_root.iter():
            if not (row_el.tag.endswith("}row") or row_el.tag == "row"):
                continue
            row_map: Dict[int, str] = {}
            max_col = -1
            for c_el in row_el:
                if not (c_el.tag.endswith("}c") or c_el.tag == "c"):
                    continue
                ref = c_el.attrib.get("r", "")
                col_idx = _col_ref_to_index(ref) if ref else (max_col + 1)
                max_col = max(max_col, col_idx)
                cell_type = c_el.attrib.get("t", "")

                val_str = ""
                if cell_type == "inlineStr":
                    parts = [t.text or "" for t in c_el.iter() if t.tag.endswith("}t") or t.tag == "t"]
                    val_str = "".join(parts)
                else:
                    v_el = next((ch for ch in c_el if ch.tag.endswith("}v") or ch.tag == "v"), None)
                    if v_el is not None and v_el.text is not None:
                        if cell_type == "s":
                            s_idx = int(v_el.text)
                            val_str = shared_strings[s_idx] if 0 <= s_idx < len(shared_strings) else ""
                        else:
                            val_str = v_el.text
                row_map[col_idx] = val_str

            if max_col >= 0:
                row_list = [row_map.get(i, "") for i in range(max_col + 1)]
                if any(cell.strip() for cell in row_list):
                    rows_matrix.append(row_list)

    if len(rows_matrix) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tệp .xlsx cần có tối thiểu 1 dòng tiêu đề và 1 dòng câu hỏi.",
        )

    headers = [h.strip() for h in rows_matrix[0]]
    valid: List[QuestionCreate] = []
    errors: List[ParseErrorItem] = []

    for row_num, row_cells in enumerate(rows_matrix[1:], start=2):
        row_dict = {headers[i]: (row_cells[i] if i < len(row_cells) else "") for i in range(len(headers)) if headers[i]}
        try:
            valid.append(_build_question_from_row(row_dict, topic_id, lesson_id, is_public))
        except Exception as exc:
            preview = str(row_cells[:2])[:120]
            errors.append(ParseErrorItem(index=row_num, raw_preview=preview, error=str(exc)))

    return ParsedImportResult(valid_questions=valid, errors=errors, total_detected=len(rows_matrix) - 1)


def _extract_docx_rich_lines(content: bytes) -> List[_RichLine]:
    try:
        zf = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tệp .docx bị lỗi hoặc không đúng định dạng OOXML.",
        )

    with zf:
        if "word/document.xml" not in zf.namelist():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tệp .docx thiếu word/document.xml.",
            )
        root = ET.fromstring(zf.read("word/document.xml"))

    def _run_flags(r_el: ET.Element) -> Tuple[bool, bool]:
        """Return (is_accented_underline_color_highlight, is_bold)."""
        is_accent = False
        is_bold = False
        rpr = next((ch for ch in r_el if ch.tag.split("}")[-1] == "rPr"), None)
        if rpr is None:
            return False, False
        for prop in rpr:
            ptag = prop.tag.split("}")[-1]
            val_attr = None
            for ak, av in prop.attrib.items():
                if ak.split("}")[-1] == "val":
                    val_attr = av
                    break
            if ptag == "u" and (val_attr or "single").lower() not in ("none", "0", "false"):
                is_accent = True
            elif ptag == "highlight" and (val_attr or "").lower() not in ("none", ""):
                is_accent = True
            elif ptag == "color" and (val_attr or "").lower() not in ("", "auto", "000000", "ffffff"):
                is_accent = True
            elif ptag == "b" and (val_attr or "1").lower() not in ("0", "false"):
                is_bold = True
        return is_accent, is_bold

    def _extract_paragraph_rich(p_el: ET.Element) -> List[_RichLine]:
        segments: List[Tuple[str, bool, bool]] = []
        for child in p_el:
            ctag = child.tag.split("}")[-1]
            if ctag == "r":
                acc, bld = _run_flags(child)
                buf: List[str] = []
                for el in child.iter():
                    etag = el.tag.split("}")[-1]
                    if etag == "t" and el.text:
                        buf.append(el.text)
                    elif etag == "tab":
                        buf.append("   ")
                    elif etag == "br":
                        buf.append("\n")
                txt = "".join(buf)
                if txt:
                    segments.append((txt, acc, bld))
            elif ctag == "hyperlink":
                for sub_r in child:
                    if sub_r.tag.split("}")[-1] == "r":
                        acc, bld = _run_flags(sub_r)
                        txt = "".join(
                            el.text for el in sub_r.iter()
                            if el.tag.split("}")[-1] == "t" and el.text
                        )
                        if txt:
                            segments.append((txt, acc, bld))

        full_text = "".join(s[0] for s in segments)
        if not full_text.strip():
            return []

        # Map character positions in full_text to accent/bold flags
        char_accent: List[bool] = []
        char_bold: List[bool] = []
        for txt, acc, bld in segments:
            char_accent.extend([acc] * len(txt))
            char_bold.extend([bld] * len(txt))

        out_lines: List[_RichLine] = []
        offset = 0
        for raw_sub in full_text.splitlines():
            sub_len = len(raw_sub)
            s = raw_sub.strip()
            if s:
                lead = len(raw_sub) - len(raw_sub.lstrip())
                start_i = offset + lead
                end_i = start_i + len(s)
                sub_acc = char_accent[start_i:end_i]
                sub_bld = char_bold[start_i:end_i]

                accented_keys: Set[str] = set()
                bold_keys: Set[str] = set()
                for m in re.finditer(r"(?:^|\s)(\*?[A-Fa-f])\s*[.\)]", s):
                    k = m.group(1).lstrip("*").upper()
                    span_start, span_end = m.span(1)
                    if any(sub_acc[span_start:span_end]):
                        accented_keys.add(k)
                    if any(sub_bld[span_start:span_end]):
                        bold_keys.add(k)

                non_space_acc = [a for ch, a in zip(s, sub_acc) if not ch.isspace()]
                non_space_bld = [b for ch, b in zip(s, sub_bld) if not ch.isspace()]
                whole_acc = bool(non_space_acc) and all(non_space_acc)
                whole_bld = bool(non_space_bld) and all(non_space_bld)

                out_lines.append(
                    _RichLine(
                        text=s,
                        accented_keys=accented_keys,
                        bold_keys=bold_keys,
                        whole_line_accented=whole_acc,
                        whole_line_bold=whole_bld,
                    )
                )
            offset += sub_len + 1
        return out_lines

    lines: List[_RichLine] = []
    body = next((ch for ch in root if ch.tag.split("}")[-1] == "body"), root)
    for node in body:
        ntag = node.tag.split("}")[-1]
        if ntag == "p":
            lines.extend(_extract_paragraph_rich(node))
        elif ntag == "tbl":
            # Read table rows as pipe-delimited lines so answer-key tables parse cleanly
            for tr in node:
                if tr.tag.split("}")[-1] != "tr":
                    continue
                row_cells: List[str] = []
                for tc in tr:
                    if tc.tag.split("}")[-1] != "tc":
                        continue
                    cell_parts: List[str] = []
                    for p in tc:
                        if p.tag.split("}")[-1] == "p":
                            for rl in _extract_paragraph_rich(p):
                                cell_parts.append(rl.text)
                    row_cells.append(" ".join(cell_parts).strip())
                joined = " | ".join(c for c in row_cells if c)
                if joined:
                    lines.append(_RichLine(text=joined))
    return lines


_RE_QUESTION_START = re.compile(r"^(?:Câu(?:\s*hỏi)?|Question|Bài)\s*(\d+)\s*[:.\)]\s*(.*)$", re.IGNORECASE)
_RE_NUM_START = re.compile(r"^(\d+)\s*[.\)]\s+(.+)$")
_RE_OPTION_LINE = re.compile(r"^(\*)?\s*([A-Fa-f])\s*[.\):]\s*(.+)$")
_RE_INLINE_STRICT = re.compile(r"(?:^|\s{2,}|\t)(\*?[A-Fa-f])\s*[.\)]\s*")
_RE_INLINE_SINGLE_SPACE = re.compile(r"(?:^|\s)(\*?[A-Da-d])\s*[.\)]\s+")
_RE_ANSWER_LINE = re.compile(r"^(?:Đáp án(?:\s*đúng)?|Answer|Key)\s*[:\-]\s*(.+)$", re.IGNORECASE)
_RE_EXPLANATION_LINE = re.compile(r"^(?:Lời giải|Giải thích|Hướng dẫn|Explanation)\s*[:\-]\s*(.+)$", re.IGNORECASE)
_RE_HINT_LINE = re.compile(r"^(?:Gợi ý|Hint)\s*[:\-]\s*(.+)$", re.IGNORECASE)
_RE_DIFFICULTY_LINE = re.compile(r"^(?:Độ khó|Mức độ|Difficulty)\s*[:\-]\s*(.+)$", re.IGNORECASE)
_RE_ANSWER_SECTION_HDR = re.compile(r"^(?:BẢNG\s*ĐÁP\s*ÁN|ĐÁP\s*ÁN(?:\s*THAM\s*KHẢO)?|HƯỚNG\s*DẪN\s*CHẤM|ANSWER\s*KEY)\b", re.IGNORECASE)


def _extract_answer_key_map(rich_lines: List[_RichLine]) -> Tuple[List[_RichLine], Dict[int, Set[str]]]:
    """
    Detect an end-of-document answer key block or table (e.g. `1.A 2.B`, `1A 2B`,
    or table rows `Câu | 1 | 2` / `Đáp án | A | B`) and return (content_lines, key_map).
    """
    key_map: Dict[int, Set[str]] = {}
    cutoff_idx = len(rich_lines)

    for idx, rl in enumerate(rich_lines):
        if _RE_ANSWER_SECTION_HDR.match(rl.text):
            cutoff_idx = idx
            break

    # Also detect tail answer-pair block if no explicit header was given
    tail_lines = rich_lines[cutoff_idx:] if cutoff_idx < len(rich_lines) else []
    if not tail_lines and len(rich_lines) >= 2:
        # Check last few lines for dense pairs like "1.A  2.B  3.C" or "1A 2B 3C"
        scan_start = max(0, len(rich_lines) - 12)
        for i in range(scan_start, len(rich_lines)):
            pairs = re.findall(r"\b(\d{1,3})\s*[:.\-]?\s*([A-Fa-f])\b", rich_lines[i].text)
            if len(pairs) >= 3 and "|" not in rich_lines[i].text[:4]:
                # Ensure it isn't a question line itself
                if not _RE_QUESTION_START.match(rich_lines[i].text) and not _RE_OPTION_LINE.match(rich_lines[i].text):
                    cutoff_idx = min(cutoff_idx, i)
                    tail_lines = rich_lines[cutoff_idx:]
                    break

    if tail_lines:
        # Pattern 1: pairs like "1.A", "1: B", "Câu 1: C", "1A"
        for rl in tail_lines:
            txt = rl.text
            for q_num_str, ans_letter in re.findall(r"(?:Câu\s*)?(\d{1,3})\s*[:.\-\|]?\s*([A-Fa-f])\b", txt, flags=re.IGNORECASE):
                q_num = int(q_num_str)
                key_map.setdefault(q_num, set()).add(ans_letter.upper())

        # Pattern 2: Horizontal table rows: numbers row followed by letters row
        for i in range(len(tail_lines) - 1):
            row1 = [c.strip() for c in tail_lines[i].text.split("|") if c.strip()]
            row2 = [c.strip() for c in tail_lines[i + 1].text.split("|") if c.strip()]
            if len(row1) >= 2 and len(row1) == len(row2):
                nums_ok = all(re.fullmatch(r"(?:Câu\s*)?\d{1,3}", c, flags=re.IGNORECASE) or i_c == 0 for i_c, c in enumerate(row1))
                lets_ok = all(re.fullmatch(r"[A-Fa-f]{1,2}", c) or i_c == 0 for i_c, c in enumerate(row2))
                if nums_ok and lets_ok:
                    for c1, c2 in zip(row1, row2):
                        m_num = re.search(r"\d{1,3}", c1)
                        if m_num and re.fullmatch(r"[A-Fa-f]{1,2}", c2):
                            key_map.setdefault(int(m_num.group(0)), set()).update(ch.upper() for ch in c2)

    return rich_lines[:cutoff_idx], key_map


def _split_inline_options(line: str) -> Optional[List[Tuple[str, str, bool]]]:
    """
    Attempt to split multiple options appearing on one line, e.g.:
    `A. 1   B. 2   C. 3   D. 4` or `A. 1 B. 2 C. 3 D. 4`.
    Returns list of (key, content, is_starred) or None if not multi-option.
    """
    parts = _RE_INLINE_STRICT.split(line)
    if len(parts) < 5:
        # Check single-space inline when sequential letters appear (e.g. A. ... B. ...)
        matches = list(_RE_INLINE_SINGLE_SPACE.finditer(line))
        letters = [m.group(1).lstrip("*").upper() for m in matches]
        if len(matches) >= 2 and letters[0] == "A" and "B" in letters:
            out: List[Tuple[str, str, bool]] = []
            for idx, m in enumerate(matches):
                raw_k = m.group(1).strip()
                starred = raw_k.startswith("*")
                key = raw_k.lstrip("*").upper()
                val_start = m.end()
                val_end = matches[idx + 1].start() if idx + 1 < len(matches) else len(line)
                val = line[val_start:val_end].strip()
                if val:
                    out.append((key, val, starred))
            return out if len(out) >= 2 else None
        return None

    out_strict: List[Tuple[str, str, bool]] = []
    i = 1
    while i + 1 < len(parts):
        raw_k = parts[i].strip()
        val = parts[i + 1].strip()
        starred = raw_k.startswith("*")
        key = raw_k.lstrip("*").upper()
        if val:
            out_strict.append((key, val, starred))
        i += 2
    return out_strict if len(out_strict) >= 2 else None


def _parse_rich_lines_blocks(rich_lines: List[_RichLine]) -> List[Dict[str, Any]]:
    content_lines, key_map = _extract_answer_key_map(rich_lines)
    blocks: List[Dict[str, Any]] = []
    current: Optional[Dict[str, Any]] = None

    for rl in content_lines:
        line = rl.text
        q_match = _RE_QUESTION_START.match(line) or _RE_NUM_START.match(line)
        if q_match:
            if current is not None:
                blocks.append(current)
            q_num = int(q_match.group(1))
            q_body = q_match.group(2).strip()
            current = {
                "q_num": q_num,
                "content": q_body,
                "options": {},
                "starred": set(),
                "accented": set(),
                "bold_opts": set(),
                "answer": None,
                "explanation": None,
                "hint": None,
                "difficulty": None,
            }
            continue

        if current is None:
            continue

        ans_match = _RE_ANSWER_LINE.match(line)
        if ans_match:
            current["answer"] = ans_match.group(1).strip()
            continue

        exp_match = _RE_EXPLANATION_LINE.match(line)
        if exp_match:
            current["explanation"] = exp_match.group(1).strip()
            continue

        hint_match = _RE_HINT_LINE.match(line)
        if hint_match:
            current["hint"] = hint_match.group(1).strip()
            continue

        diff_match = _RE_DIFFICULTY_LINE.match(line)
        if diff_match:
            current["difficulty"] = diff_match.group(1).strip()
            continue

        opt_match = _RE_OPTION_LINE.match(line)
        if opt_match:
            inline_opts = _split_inline_options(line)
            if inline_opts:
                for key, val, starred in inline_opts:
                    current["options"][key] = val
                    if starred:
                        current["starred"].add(key)
                    if key in rl.accented_keys:
                        current["accented"].add(key)
                    if key in rl.bold_keys:
                        current["bold_opts"].add(key)
            else:
                starred = bool(opt_match.group(1))
                key = opt_match.group(2).upper()
                val = opt_match.group(3).strip()
                current["options"][key] = val
                if starred:
                    current["starred"].add(key)
                if rl.whole_line_accented or key in rl.accented_keys:
                    current["accented"].add(key)
                if rl.whole_line_bold or key in rl.bold_keys:
                    current["bold_opts"].add(key)
            continue

        # Multi-line continuation of question content or explanation
        if current["explanation"] is not None:
            current["explanation"] += "\n" + line
        elif not current["options"]:
            current["content"] = (current["content"] + "\n" + line).strip()

    if current is not None:
        blocks.append(current)

    # Apply end-of-document answer key map & smart bold/accent inference
    for seq_idx, blk in enumerate(blocks, start=1):
        keys: Set[str] = set(blk["starred"]) | set(blk["accented"])
        if blk["answer"]:
            keys |= _parse_correct_keys(blk["answer"])
        if not keys:
            mapped = key_map.get(blk.get("q_num") or seq_idx) or key_map.get(seq_idx)
            if mapped:
                keys |= mapped
        # Bold heuristic: only when strictly a subset of options (e.g. 1 option) is bolded
        if not keys and blk["bold_opts"] and len(blk["bold_opts"]) < len(blk["options"]):
            keys |= set(blk["bold_opts"])
        blk["resolved_correct_keys"] = keys

    return blocks


def _parse_rich_lines_to_import_result(
    rich_lines: List[_RichLine],
    topic_id: Optional[str],
    lesson_id: Optional[str],
    is_public: bool,
    empty_detail: str,
) -> ParsedImportResult:
    blocks = _parse_rich_lines_blocks(rich_lines)
    if not blocks:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=empty_detail)

    valid: List[QuestionCreate] = []
    errors: List[ParseErrorItem] = []

    for idx, blk in enumerate(blocks, start=1):
        try:
            correct_keys = blk["resolved_correct_keys"]
            row_payload: Dict[str, Any] = {
                "content": blk["content"],
                "options": blk["options"] if blk["options"] else None,
                "correct": list(correct_keys) if blk["options"] else blk["answer"],
                "explanation": blk["explanation"],
                "hint": blk["hint"],
                "difficulty_level": blk["difficulty"],
            }
            valid.append(_build_question_from_row(row_payload, topic_id, lesson_id, is_public))
        except Exception as exc:
            errors.append(ParseErrorItem(index=idx, raw_preview=blk["content"][:120], error=str(exc)))

    return ParsedImportResult(valid_questions=valid, errors=errors, total_detected=len(blocks))


def _parse_docx_bytes(
    content: bytes, topic_id: Optional[str], lesson_id: Optional[str], is_public: bool
) -> ParsedImportResult:
    rich_lines = _extract_docx_rich_lines(content)
    if not rich_lines:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tệp .docx không có nội dung văn bản.",
        )
    return _parse_rich_lines_to_import_result(
        rich_lines=rich_lines,
        topic_id=topic_id,
        lesson_id=lesson_id,
        is_public=is_public,
        empty_detail="Không nhận diện được câu hỏi nào trong tệp .docx (hãy bắt đầu mỗi câu bằng 'Câu 1:', '1.' và các đáp án 'A.', 'B.', 'C.', 'D.', kèm 'Đáp án: A' hoặc bảng đáp án cuối đề).",
    )


def _extract_text_lines(content: bytes) -> List[_RichLine]:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("latin-1", errors="ignore")
    return [_RichLine(text=line.strip()) for line in text.splitlines() if line.strip()]


def _parse_txt_bytes(
    content: bytes, topic_id: Optional[str], lesson_id: Optional[str], is_public: bool
) -> ParsedImportResult:
    rich_lines = _extract_text_lines(content)
    if not rich_lines:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tệp văn bản (.txt) đang trống.",
        )
    return _parse_rich_lines_to_import_result(
        rich_lines=rich_lines,
        topic_id=topic_id,
        lesson_id=lesson_id,
        is_public=is_public,
        empty_detail="Không nhận diện được câu hỏi nào trong tệp .txt.",
    )


def _try_extract_pdf_text_offline(content: bytes) -> str:
    """
    Lightweight pure-Python text extraction from text-based PDF streams (FlateDecode or plain).
    Returns empty string if PDF is scanned/image-only or uses unsupported encoding.
    """
    chunks: List[str] = []
    for m in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", content, flags=re.DOTALL):
        raw_stream = m.group(1)
        data = raw_stream
        if raw_stream[:1] in (b"x", b"\x78"):
            try:
                data = zlib.decompress(raw_stream)
            except Exception:
                pass
        # Extract PDF literal strings (...) inside text blocks
        if b"Tj" in data or b"TJ" in data or b"BT" in data:
            for str_m in re.finditer(rb"\(([^()\\]*(?:\\.[^()\\]*)*)\)", data):
                raw_s = str_m.group(1)
                raw_s = (
                    raw_s.replace(rb"\(", b"(")
                    .replace(rb"\)", b")")
                    .replace(rb"\\", b"\\")
                    .replace(rb"\n", b"\n")
                    .replace(rb"\r", b"\r")
                    .replace(rb"\t", b"\t")
                )
                if raw_s.startswith(b"\xfe\xff"):
                    decoded = raw_s[2:].decode("utf-16-be", errors="ignore")
                else:
                    try:
                        decoded = raw_s.decode("utf-8")
                    except UnicodeDecodeError:
                        decoded = raw_s.decode("latin-1", errors="ignore")
                cleaned = "".join(ch for ch in decoded if ch.isprintable() or ch in "\n\t ")
                if cleaned.strip():
                    chunks.append(cleaned)
            chunks.append("\n")
    return " ".join(chunks).strip()


def _question_create_to_draft_dict(q: QuestionCreate) -> Dict[str, Any]:
    has_corr = any(o.is_correct for o in q.options) or q.question_type == QuestionType.ESSAY
    return {
        "content": q.content,
        "question_type": q.question_type.value,
        "difficulty_level": q.difficulty_level.value,
        "options": [
            {
                "option_key": o.option_key,
                "content": o.content,
                "is_correct": o.is_correct,
                "order_index": o.order_index,
            }
            for o in q.options
        ],
        "explanation": q.explanation,
        "hint": q.hint,
        "tags": q.tags,
        "has_correct_answer": has_corr,
        "warning": None if has_corr else "Chưa nhận diện được đáp án đúng — vui lòng bấm chọn A/B/C/D trước khi tạo đề.",
    }


def _block_to_draft_dict(blk: Dict[str, Any]) -> Dict[str, Any]:
    options_map: Dict[str, str] = blk.get("options") or {}
    correct_keys: Set[str] = blk.get("resolved_correct_keys") or set()
    ordered_keys = sorted(options_map.keys())
    opts_list = [
        {
            "option_key": k,
            "content": options_map[k],
            "is_correct": k in correct_keys,
            "order_index": idx,
        }
        for idx, k in enumerate(ordered_keys)
    ]

    if len(opts_list) >= 2:
        q_type = QuestionType.MULTIPLE_CHOICE.value if len(correct_keys) > 1 else QuestionType.SINGLE_CHOICE.value
        has_corr = len(correct_keys) >= 1
    elif blk.get("answer"):
        q_type = QuestionType.SHORT_ANSWER.value
        opts_list = [
            {
                "option_key": "A",
                "content": str(blk["answer"]).strip(),
                "is_correct": True,
                "order_index": 0,
            }
        ]
        has_corr = True
    else:
        q_type = QuestionType.ESSAY.value
        has_corr = True

    return {
        "content": blk["content"],
        "question_type": q_type,
        "difficulty_level": _parse_difficulty(blk.get("difficulty")).value,
        "options": opts_list,
        "explanation": blk.get("explanation"),
        "hint": blk.get("hint"),
        "tags": None,
        "has_correct_answer": has_corr,
        "warning": None if has_corr else "Chưa nhận diện được đáp án đúng — vui lòng bấm chọn đáp án đúng ở dưới.",
    }


def _ai_items_to_drafts(ai_items: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[ParseErrorItem]]:
    drafts: List[Dict[str, Any]] = []
    errors: List[ParseErrorItem] = []

    for idx, item in enumerate(ai_items, start=1):
        content_str = str(item.get("content") or "").strip()
        if len(content_str) < 3:
            errors.append(ParseErrorItem(index=idx, raw_preview=content_str[:80], error="Nội dung câu hỏi quá ngắn."))
            continue

        q_type = _parse_question_type(str(item.get("question_type") or "")).value
        diff = _parse_difficulty(str(item.get("difficulty_level") or "")).value
        raw_opts = item.get("options") if isinstance(item.get("options"), list) else []

        opts_list: List[Dict[str, Any]] = []
        for o_idx, o in enumerate(raw_opts):
            if not isinstance(o, dict):
                continue
            key = str(o.get("option_key") or chr(65 + o_idx)).strip().upper()
            txt = str(o.get("content") or "").strip()
            if txt:
                opts_list.append(
                    {
                        "option_key": key,
                        "content": txt,
                        "is_correct": bool(o.get("is_correct")),
                        "order_index": o_idx,
                    }
                )

        has_corr = any(o["is_correct"] for o in opts_list) or q_type == QuestionType.ESSAY.value
        if q_type in (QuestionType.SINGLE_CHOICE.value, QuestionType.MULTIPLE_CHOICE.value) and len(opts_list) < 2:
            q_type = QuestionType.ESSAY.value
            has_corr = True

        drafts.append(
            {
                "content": content_str,
                "question_type": q_type,
                "difficulty_level": diff,
                "options": opts_list,
                "explanation": str(item.get("explanation")).strip() if item.get("explanation") else None,
                "hint": str(item.get("hint")).strip() if item.get("hint") else None,
                "tags": str(item.get("tags")).strip() if item.get("tags") else None,
                "has_correct_answer": has_corr,
                "warning": None if has_corr else "AI chưa xác định chắc chắn đáp án đúng — vui lòng kiểm tra và chọn đáp án.",
            }
        )

    return drafts, errors


async def convert_exam_file_to_draft(
    filename: Optional[str],
    content: bytes,
    topic_id: Optional[str] = None,
    lesson_id: Optional[str] = None,
    is_public: bool = True,
    use_ai: bool = True,
) -> ParsedDraftResult:
    """
    Convert an uploaded teacher exam file (.docx, .txt, .pdf, .png/.jpg/.webp, .xlsx, .csv, .json)
    into editable quiz draft questions, automatically detecting multiple-choice options and keys
    and falling back to Gemini multimodal AI when configured.
    """
    _, ext = validate_upload_bytes(
        filename=filename,
        content=content,
        allowed_extensions=ALLOWED_CONVERT_EXTENSIONS,
        max_size_bytes=MAX_IMPORT_FILE_SIZE_BYTES,
    )
    ai_avail = is_ai_extraction_available()

    # 1. Structured spreadsheet / JSON formats
    if ext in (".json", ".csv", ".xlsx"):
        parsed = parse_questions_file(
            filename=filename,
            content=content,
            topic_id=topic_id,
            lesson_id=lesson_id,
            is_public=is_public,
        )
        return ParsedDraftResult(
            draft_questions=[_question_create_to_draft_dict(q) for q in parsed.valid_questions],
            errors=parsed.errors,
            total_detected=parsed.total_detected,
            extraction_method="structured",
            ai_used=False,
            ai_available=ai_avail,
        )

    # 2. Image files -> requires Gemini Vision AI
    if ext in (".png", ".jpg", ".jpeg", ".webp"):
        if not (use_ai and ai_avail):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Chuyển ảnh chụp đề thi sang trắc nghiệm cần cấu hình AI_PROVIDER=google và GEMINI_API_KEY, hoặc bạn có thể tải lên tệp Word (.docx), .txt, .xlsx, .csv.",
            )
        ai_items = await extract_questions_with_ai(filename or f"exam{ext}", content)
        drafts, errs = _ai_items_to_drafts(ai_items)
        if not drafts:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="AI không nhận diện được câu hỏi trắc nghiệm nào trong ảnh.",
            )
        return ParsedDraftResult(
            draft_questions=drafts,
            errors=errs,
            total_detected=len(ai_items),
            extraction_method="ai_gemini",
            ai_used=True,
            ai_available=ai_avail,
        )

    # 3. PDF files -> try offline text stream first, upgrade/fallback to Gemini PDF multimodal
    if ext == ".pdf":
        offline_text = _try_extract_pdf_text_offline(content)
        offline_blocks: List[Dict[str, Any]] = []
        if offline_text:
            rich_pdf = [_RichLine(text=ln.strip()) for ln in offline_text.splitlines() if ln.strip()]
            offline_blocks = _parse_rich_lines_blocks(rich_pdf)

        if use_ai and ai_avail and (not offline_blocks or sum(1 for b in offline_blocks if b.get("options")) == 0):
            ai_items = await extract_questions_with_ai(filename or "exam.pdf", content)
            drafts, errs = _ai_items_to_drafts(ai_items)
            if drafts:
                return ParsedDraftResult(
                    draft_questions=drafts,
                    errors=errs,
                    total_detected=len(ai_items),
                    extraction_method="ai_gemini",
                    ai_used=True,
                    ai_available=ai_avail,
                )

        if not offline_blocks:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Tệp PDF này là bản scan/ảnh hoặc dùng bảng mã phông chữ nén không đọc được offline. "
                    "Hãy lưu/xuất sang Word (.docx) hoặc cấu hình AI_PROVIDER=google & GEMINI_API_KEY để AI tự động tách trắc nghiệm."
                ),
            )
        drafts = [_block_to_draft_dict(b) for b in offline_blocks if len(b["content"].strip()) >= 3]
        return ParsedDraftResult(
            draft_questions=drafts,
            errors=[],
            total_detected=len(offline_blocks),
            extraction_method="heuristic_pdf",
            ai_used=False,
            ai_available=ai_avail,
        )

    # 4. Word (.docx) & Plain text (.txt) -> smart deterministic parser + optional AI fallback
    rich_lines = _extract_docx_rich_lines(content) if ext == ".docx" else _extract_text_lines(content)
    blocks = _parse_rich_lines_blocks(rich_lines)

    if use_ai and ai_avail and not blocks:
        plain_text = "\n".join(rl.text for rl in rich_lines)
        ai_items = await extract_questions_with_ai(filename or f"exam{ext}", content, raw_text=plain_text)
        drafts, errs = _ai_items_to_drafts(ai_items)
        if drafts:
            return ParsedDraftResult(
                draft_questions=drafts,
                errors=errs,
                total_detected=len(ai_items),
                extraction_method="ai_gemini",
                ai_used=True,
                ai_available=ai_avail,
            )

    if not blocks:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Không nhận diện được câu hỏi nào trong tệp {ext}. Hãy kiểm tra định dạng đánh số 'Câu 1:', đáp án 'A. B. C. D.'.",
        )

    drafts = [_block_to_draft_dict(b) for b in blocks if len(b["content"].strip()) >= 3]
    return ParsedDraftResult(
        draft_questions=drafts,
        errors=[],
        total_detected=len(blocks),
        extraction_method=f"heuristic_{ext.lstrip('.')}",
        ai_used=False,
        ai_available=ai_avail,
    )


def parse_questions_file(
    filename: Optional[str],
    content: bytes,
    topic_id: Optional[str] = None,
    lesson_id: Optional[str] = None,
    is_public: bool = True,
) -> ParsedImportResult:
    """Validate and parse an uploaded .json, .csv, .xlsx, .docx, or .txt question file."""
    _, ext = validate_upload_bytes(
        filename=filename,
        content=content,
        allowed_extensions=ALLOWED_IMPORT_EXTENSIONS,
        max_size_bytes=MAX_IMPORT_FILE_SIZE_BYTES,
    )

    if ext == ".json":
        return _parse_json_bytes(content, topic_id, lesson_id, is_public)
    if ext == ".csv":
        return _parse_csv_bytes(content, topic_id, lesson_id, is_public)
    if ext == ".xlsx":
        return _parse_xlsx_bytes(content, topic_id, lesson_id, is_public)
    if ext == ".docx":
        return _parse_docx_bytes(content, topic_id, lesson_id, is_public)
    if ext == ".txt":
        return _parse_txt_bytes(content, topic_id, lesson_id, is_public)

    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Định dạng '{ext}' chưa được hỗ trợ.")
