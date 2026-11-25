"""
AI Exam-to-Quiz Extractor - SMART LEARNING PRO
Uses Google GenAI (Gemini multimodal/text) when configured (`AI_PROVIDER=google`)
to convert uploaded PDFs, images, or unstructured Word/text exams into structured
multiple-choice questions with KaTeX math notation.
"""

import asyncio
import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from google import genai
from google.genai import types

from app.modules.ai_engine.config import get_ai_config

logger = logging.getLogger(__name__)

_MIME_BY_EXT: Dict[str, str] = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}

_EXTRACTION_SYSTEM_PROMPT = """Bạn là chuyên gia số hóa đề thi THCS/THPT tại Việt Nam.
Nhiệm vụ: Trích xuất TOÀN BỘ câu hỏi từ tài liệu giáo viên tải lên và trả về một mảng JSON hợp lệ (KHÔNG bọc markdown ```json).

Quy tắc bắt buộc:
1. Mỗi phần tử JSON đại diện cho 1 câu hỏi với cấu trúc:
{
  "content": "Nội dung câu hỏi (giữ công thức toán dạng LaTeX $...$ hoặc $$...$$)",
  "question_type": "SINGLE_CHOICE" | "MULTIPLE_CHOICE" | "TRUE_FALSE" | "SHORT_ANSWER" | "ESSAY",
  "difficulty_level": "RECOGNITION" | "COMPREHENSION" | "APPLICATION" | "HIGH_APPLICATION",
  "options": [
    {"option_key": "A", "content": "Nội dung đáp án A", "is_correct": false},
    {"option_key": "B", "content": "Nội dung đáp án B", "is_correct": true}
  ],
  "explanation": "Lời giải chi tiết (hoặc null nếu không có)",
  "hint": "Gợi ý ngắn cho học sinh (hoặc null)",
  "tags": "từ khóa cách nhau bởi dấu phẩy (hoặc null)"
}
2. Nếu tài liệu có đánh dấu đáp án đúng (in đậm, gạch chân, tô màu, dấu *, hoặc bảng đáp án cuối đề), đặt `is_correct: true` đúng phương án đó.
3. Nếu tài liệu CHƯA ghi đáp án nhưng là câu hỏi trắc nghiệm khách quan rõ ràng có thể giải chắc chắn, hãy tự giải chính xác để chọn `is_correct: true` và viết `explanation` ngắn gọn; nếu không chắc chắn, để tất cả `is_correct: false` để giáo viên tự chọn.
4. Giữ nguyên tiếng Việt chuẩn xác, không bịa đặt thêm câu hỏi không có trong đề.
"""


def is_ai_extraction_available() -> bool:
    """Return True when Gemini provider is configured with a non-empty API key."""
    try:
        cfg = get_ai_config()
        return cfg.provider.strip().lower() == "google" and bool(cfg.api_key.strip())
    except Exception:
        return False


def _strip_json_fences(raw_text: str) -> str:
    text = raw_text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


async def extract_questions_with_ai(
    filename: str,
    content: bytes,
    raw_text: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Convert an uploaded exam file (PDF, image, or extracted text) into structured
    question dictionaries via Google Gemini.
    """
    cfg = get_ai_config()
    if cfg.provider.strip().lower() != "google" or not cfg.api_key.strip():
        raise RuntimeError(
            "AI_PROVIDER chưa được cấu hình sang 'google' với GEMINI_API_KEY."
        )

    ext = Path(filename or "").suffix.lower()
    parts: List[Any] = []

    if ext in _MIME_BY_EXT:
        parts.append(
            types.Part.from_bytes(
                data=content,
                mime_type=_MIME_BY_EXT[ext],
            )
        )
        parts.append(
            "Hãy đọc tài liệu đính kèm và trích xuất toàn bộ câu hỏi thành JSON array theo đúng quy tắc."
        )
    else:
        text_payload = (raw_text or "").strip()
        if not text_payload:
            text_payload = content.decode("utf-8", errors="ignore").strip()
        if not text_payload:
            raise ValueError("Không có nội dung văn bản để AI phân tích.")
        parts.append(
            f"Hãy trích xuất toàn bộ câu hỏi từ văn bản đề thi sau thành JSON array:\n\n{text_payload[:60000]}"
        )

    client = genai.Client(api_key=cfg.api_key.strip())
    timeout_sec = max(float(cfg.timeout_seconds), 45.0)

    try:
        response = await asyncio.wait_for(
            client.aio.models.generate_content(
                model=cfg.model.strip(),
                contents=parts,
                config=types.GenerateContentConfig(
                    system_instruction=_EXTRACTION_SYSTEM_PROMPT,
                    temperature=0.1,
                    response_mime_type="application/json",
                ),
            ),
            timeout=timeout_sec,
        )
    except asyncio.TimeoutError as exc:
        raise TimeoutError(f"AI xử lý đề thi quá thời gian ({timeout_sec:.0f}s).") from exc
    finally:
        try:
            client.close()
        except Exception:
            pass

    raw_output = getattr(response, "text", None) or ""
    cleaned = _strip_json_fences(raw_output)
    data = json.loads(cleaned)
    if isinstance(data, dict) and isinstance(data.get("questions"), list):
        data = data["questions"]
    if not isinstance(data, list):
        raise ValueError("AI không trả về danh sách câu hỏi JSON hợp lệ.")
    return [item for item in data if isinstance(item, dict)]
