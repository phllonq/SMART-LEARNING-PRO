import uuid
from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Integer, Float, Text, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin


class AIConversation(Base, TimestampMixin):
    __tablename__ = "ai_conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    topic_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("topics.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[str] = mapped_column(String(255), default="Đoạn hội thoại học tập", nullable=False)

    user = relationship("app.modules.auth.models.User")
    topic = relationship("app.modules.curriculum.models.Topic")
    messages: Mapped[List["AIMessage"]] = relationship("AIMessage", back_populates="conversation", cascade="all, delete-orphan", order_by="AIMessage.created_at")


class AIMessage(Base):
    __tablename__ = "ai_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id: Mapped[str] = mapped_column(String(36), ForeignKey("ai_conversations.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # user, assistant, system
    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Structured JSON diagnostics
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    conversation: Mapped["AIConversation"] = relationship("AIConversation", back_populates="messages")


class AIUsageLog(Base):
    __tablename__ = "ai_usage_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    feature: Mapped[str] = mapped_column(String(50), nullable=False)  # WRONG_ANSWER_ANALYSIS, TUTOR_CHAT, QUESTION_GEN
    model_name: Mapped[str] = mapped_column(String(50), nullable=False)  # gemini-1.5-flash
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    estimated_cost_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    user = relationship("app.modules.auth.models.User")


class KnowledgeDocument(Base, TimestampMixin):
    __tablename__ = "knowledge_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    topic_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("topics.id", ondelete="CASCADE"), nullable=True)
    title: Mapped[str] = mapped_column(String(255), default="Tài liệu tri thức", nullable=False)
    chunk_content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Vector representation
    source_reference: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    topic = relationship("app.modules.curriculum.models.Topic")
