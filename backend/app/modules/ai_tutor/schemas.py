"""
Domain Schemas and Enums for AI Tutor - SMART LEARNING PRO
Defines request/response contracts for AI Tutor conversations, streaming telemetry, and security boundaries.
"""

from datetime import datetime
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator, ConfigDict


class MessageStatus(str, Enum):
    """Lifecycle status of a tutor message during generation and storage."""
    PENDING = "PENDING"
    STREAMING = "STREAMING"
    COMPLETED = "COMPLETED"
    INTERRUPTED = "INTERRUPTED"
    FAILED = "FAILED"


class MessageRole(str, Enum):
    """Allowed participant roles in tutor dialogue."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ConversationCreateRequest(BaseModel):
    """
    Client request payload to initiate a new AI Tutor conversation.
    Explicitly forbids client-injected identifiers (e.g. user_id).
    """
    title: Optional[str] = Field(None, max_length=255, description="Tiêu đề gợi nhớ cho đoạn hội thoại")
    topic_id: Optional[str] = Field(None, max_length=36, description="ID chủ đề học tập liên quan nếu có")

    model_config = ConfigDict(extra="forbid")

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            stripped = v.strip()
            if not stripped:
                return None
            return stripped
        return None


class ConversationRenameRequest(BaseModel):
    """Client request payload to rename an existing conversation."""
    title: str = Field(..., min_length=1, max_length=255, description="Tiêu đề mới cho đoạn hội thoại")

    model_config = ConfigDict(extra="forbid")

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Tiêu đề không được để trống hoặc chỉ chứa khoảng trắng.")
        return stripped


class ConversationResponse(BaseModel):
    """Normalized response schema representing an AI Tutor conversation thread."""
    id: str = Field(..., description="UUID định danh duy nhất của đoạn hội thoại")
    user_id: str = Field(..., description="UUID người sở hữu đoạn hội thoại")
    topic_id: Optional[str] = Field(None, description="ID chủ đề học tập liên quan")
    title: str = Field(..., description="Tiêu đề đoạn hội thoại")
    created_at: datetime = Field(..., description="Thời điểm khởi tạo")
    updated_at: datetime = Field(..., description="Thời điểm cập nhật mới nhất")
    message_count: int = Field(0, description="Tổng số tin nhắn trong đoạn hội thoại")

    model_config = ConfigDict(from_attributes=True)


class ConversationListResponse(BaseModel):
    """Paginated list of AI Tutor conversation threads."""
    items: List[ConversationResponse]
    total: int
    page: int
    page_size: int


class TutorMessageRequest(BaseModel):
    """
    Client request to send a message to the AI Tutor.
    Strictly forbids role tampering, prompt injection overrides, or token metrics from client.
    """
    content: str = Field(
        ...,
        min_length=1,
        max_length=4000,
        description="Nội dung câu hỏi hoặc phản hồi của học sinh",
    )

    model_config = ConfigDict(extra="forbid")

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Nội dung tin nhắn không được để trống hoặc chỉ chứa khoảng trắng.")
        return stripped


class TutorMessageMetadata(BaseModel):
    """Metadata and execution telemetry associated with an AI Tutor message."""
    status: MessageStatus = Field(default=MessageStatus.COMPLETED, description="Trạng thái hoàn thành của tin nhắn")
    input_tokens: Optional[int] = Field(None, ge=0, description="Số token đầu vào tính toán")
    output_tokens: Optional[int] = Field(None, ge=0, description="Số token đầu ra sinh ra")
    model_name: Optional[str] = Field(None, description="Tên mô hình AI thực thi")
    latency_ms: Optional[float] = Field(None, ge=0.0, description="Độ trễ xử lý (milliseconds)")


class TutorMessageResponse(BaseModel):
    """Response schema for a single persisted message in the AI Tutor thread."""
    id: str = Field(..., description="UUID định danh tin nhắn")
    conversation_id: str = Field(..., description="UUID đoạn hội thoại chứa tin nhắn")
    role: str = Field(..., description="Vai trò phát ngôn (user, assistant, system)")
    content: str = Field(..., description="Nội dung văn bản")
    metadata: Optional[TutorMessageMetadata] = Field(None, description="Dữ liệu kỹ thuật và chỉ số token")
    created_at: datetime = Field(..., description="Thời điểm gửi tin nhắn")

    model_config = ConfigDict(from_attributes=True)
