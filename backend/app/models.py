"""
Central models registry to ensure all SQLAlchemy ORM models are registered with Base.metadata.
"""
from app.core.database import Base
from app.modules.auth.models import User, UserSession, UserRole
from app.modules.curriculum.models import Grade, Subject, Chapter, Topic, Lesson, LearningMaterial
from app.modules.questions.models import Question, QuestionOption, QuestionType, DifficultyLevel
from app.modules.exams.models import Exam, ExamQuestion, ExamAttempt, StudentAnswer, ExamResult, AttemptStatus, ExamStatus
from app.modules.classrooms.models import Classroom, ClassroomMember, Assignment
from app.modules.analytics.models import TopicMastery, KnowledgeGap, GapSeverity
from app.modules.ai_tutor.models import AIConversation, AIMessage, AIUsageLog, KnowledgeDocument
from app.modules.gamification.models import Notification, AuditLog

__all__ = [
    "Base",
    "User",
    "UserSession",
    "UserRole",
    "Grade",
    "Subject",
    "Chapter",
    "Topic",
    "Lesson",
    "LearningMaterial",
    "Question",
    "QuestionOption",
    "QuestionType",
    "DifficultyLevel",
    "Exam",
    "ExamQuestion",
    "ExamAttempt",
    "StudentAnswer",
    "ExamResult",
    "AttemptStatus",
    "Classroom",
    "ClassroomMember",
    "Assignment",
    "TopicMastery",
    "KnowledgeGap",
    "GapSeverity",
    "AIConversation",
    "AIMessage",
    "AIUsageLog",
    "KnowledgeDocument",
    "Notification",
    "AuditLog",
]
