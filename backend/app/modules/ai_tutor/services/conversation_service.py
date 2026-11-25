"""
Conversation Lifecycle Service - SMART LEARNING PRO
Manages conversation creation, retrieval, renaming, deletion, authorization, and message history pagination.
Guarantees:
  - Strict owner-only access (user_id authoritative check).
  - Uniform 404 responses to prevent conversation enumeration across tenants/users.
  - Paginated deterministic message history retrieval.
  - Transaction integrity with SQLAlchemy 2 async.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from sqlalchemy import select, func, and_, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.ai_tutor.exceptions import (
    ConversationNotFoundException,
    ConversationAccessDeniedException,
)
from app.modules.ai_tutor.models import AIConversation, AIMessage
from app.modules.ai_tutor.schemas import (
    ConversationCreateRequest,
    ConversationRenameRequest,
    ConversationResponse,
    ConversationListResponse,
    TutorMessageResponse,
)
from app.modules.ai_tutor.services.message_state import parse_message_metadata

logger = logging.getLogger(__name__)


class ConversationService:
    """Service handling the lifecycle and access control of AI Tutor conversations."""

    async def create_conversation(
        self,
        db: AsyncSession,
        user_id: str,
        request: ConversationCreateRequest,
    ) -> ConversationResponse:
        """
        Create a new conversation thread for the authenticated user.
        Client cannot specify user_id; it is strictly injected from the authenticated session.
        """
        title = request.title or "Đoạn hội thoại học tập"
        conv_id = str(uuid.uuid4())

        conversation = AIConversation(
            id=conv_id,
            user_id=user_id,
            topic_id=request.topic_id,
            title=title,
        )

        db.add(conversation)
        await db.commit()
        await db.refresh(conversation)

        logger.info("Created conversation %s for user %s", conv_id, user_id)

        return ConversationResponse(
            id=conversation.id,
            user_id=conversation.user_id,
            topic_id=conversation.topic_id,
            title=conversation.title,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
            message_count=0,
        )

    async def get_conversation(
        self,
        db: AsyncSession,
        conversation_id: str,
        user_id: str,
    ) -> ConversationResponse:
        """
        Retrieve details of a single conversation thread.
        Enforces strict ownership: returns 404 if not found or belongs to another user.
        """
        conv = await self.verify_conversation_ownership(db, conversation_id, user_id)

        # Count total messages in this conversation
        count_stmt = select(func.count(AIMessage.id)).where(AIMessage.conversation_id == conversation_id)
        count_res = await db.execute(count_stmt)
        msg_count = count_res.scalar_one_or_none() or 0

        return ConversationResponse(
            id=conv.id,
            user_id=conv.user_id,
            topic_id=conv.topic_id,
            title=conv.title,
            created_at=conv.created_at,
            updated_at=conv.updated_at,
            message_count=msg_count,
        )

    async def list_conversations(
        self,
        db: AsyncSession,
        user_id: str,
        page: int = 1,
        page_size: int = 20,
    ) -> ConversationListResponse:
        """
        List all conversations owned by the user with pagination and message counts.
        """
        safe_page = max(1, page)
        safe_size = max(1, min(100, page_size))
        offset = (safe_page - 1) * safe_size

        # 1. Total count of conversations for user
        total_stmt = select(func.count(AIConversation.id)).where(AIConversation.user_id == user_id)
        total_res = await db.execute(total_stmt)
        total = total_res.scalar_one_or_none() or 0

        if total == 0:
            return ConversationListResponse(items=[], total=0, page=safe_page, page_size=safe_size)

        # 2. Query conversations joined with message count
        # Subquery for message counts
        msg_count_subq = (
            select(
                AIMessage.conversation_id,
                func.count(AIMessage.id).label("msg_count"),
            )
            .group_by(AIMessage.conversation_id)
            .subquery()
        )

        stmt = (
            select(
                AIConversation,
                func.coalesce(msg_count_subq.c.msg_count, 0).label("msg_count"),
            )
            .outerjoin(msg_count_subq, AIConversation.id == msg_count_subq.c.conversation_id)
            .where(AIConversation.user_id == user_id)
            .order_by(AIConversation.updated_at.desc())
            .offset(offset)
            .limit(safe_size)
        )

        rows = (await db.execute(stmt)).all()

        items: List[ConversationResponse] = []
        for conv, count in rows:
            items.append(
                ConversationResponse(
                    id=conv.id,
                    user_id=conv.user_id,
                    topic_id=conv.topic_id,
                    title=conv.title,
                    created_at=conv.created_at,
                    updated_at=conv.updated_at,
                    message_count=int(count),
                )
            )

        return ConversationListResponse(
            items=items,
            total=total,
            page=safe_page,
            page_size=safe_size,
        )

    async def rename_conversation(
        self,
        db: AsyncSession,
        conversation_id: str,
        user_id: str,
        request: ConversationRenameRequest,
    ) -> ConversationResponse:
        """
        Rename an existing conversation thread after verifying ownership.
        """
        conv = await self.verify_conversation_ownership(db, conversation_id, user_id)

        conv.title = request.title
        # Timestamp updated automatically or explicitly
        conv.updated_at = datetime.now(timezone.utc)

        await db.commit()
        await db.refresh(conv)

        logger.info("Renamed conversation %s to '%s'", conversation_id, conv.title)

        # Get message count
        count_stmt = select(func.count(AIMessage.id)).where(AIMessage.conversation_id == conversation_id)
        msg_count = (await db.execute(count_stmt)).scalar_one_or_none() or 0

        return ConversationResponse(
            id=conv.id,
            user_id=conv.user_id,
            topic_id=conv.topic_id,
            title=conv.title,
            created_at=conv.created_at,
            updated_at=conv.updated_at,
            message_count=msg_count,
        )

    async def delete_conversation(
        self,
        db: AsyncSession,
        conversation_id: str,
        user_id: str,
    ) -> bool:
        """
        Permanently delete a conversation thread and all cascaded messages.
        """
        conv = await self.verify_conversation_ownership(db, conversation_id, user_id)

        await db.delete(conv)
        await db.commit()

        logger.info("Deleted conversation %s and associated messages", conversation_id)
        return True

    async def get_conversation_history(
        self,
        db: AsyncSession,
        conversation_id: str,
        user_id: str,
        limit: int = 50,
        before_message_id: Optional[str] = None,
    ) -> List[TutorMessageResponse]:
        """
        Retrieve ordered chronological message history for a conversation.
        """
        await self.verify_conversation_ownership(db, conversation_id, user_id)

        safe_limit = max(1, min(100, limit))

        stmt = (
            select(AIMessage)
            .where(AIMessage.conversation_id == conversation_id)
            .order_by(AIMessage.created_at.asc())
            .limit(safe_limit)
        )

        rows = (await db.execute(stmt)).scalars().all()

        responses: List[TutorMessageResponse] = []
        for msg in rows:
            meta = parse_message_metadata(msg.metadata_json)
            responses.append(
                TutorMessageResponse(
                    id=msg.id,
                    conversation_id=msg.conversation_id,
                    role=msg.role,
                    content=msg.content,
                    metadata=meta,
                    created_at=msg.created_at,
                )
            )

        return responses

    async def verify_conversation_ownership(
        self,
        db: AsyncSession,
        conversation_id: str,
        user_id: str,
    ) -> AIConversation:
        """
        Authoritative ownership verification helper.
        Raises ConversationNotFoundException if conversation does not exist or user_id does not match.
        Uniform 404 response eliminates cross-tenant conversation probing.
        """
        stmt = (
            select(AIConversation)
            .options(selectinload(AIConversation.topic))
            .where(AIConversation.id == conversation_id)
        )
        conv = (await db.execute(stmt)).scalar_one_or_none()

        if conv is None or conv.user_id != user_id:
            logger.warning(
                "Access denied or not found: conversation_id=%s, requester_user_id=%s",
                conversation_id,
                user_id,
            )
            raise ConversationNotFoundException(
                "Đoạn hội thoại không tồn tại hoặc bạn không có quyền truy cập."
            )

        return conv


# Global singleton instance for application use
conversation_service = ConversationService()
