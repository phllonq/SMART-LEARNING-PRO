"""
Usage Accounting - SMART LEARNING PRO
Calculates token costs and records AI consumption using the existing AIUsageLog model.
Enforces date-aware, tier-aware pricing schedules, zero-migration persistence,
and error-isolated telemetry.
"""

import logging
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional, Dict, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ai_engine.contracts import (
    NormalizedChatResponse,
    AIUsageRecord,
)
from app.modules.ai_tutor.models import AIUsageLog

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ModelPricingSchedule:
    """Pricing schedule for a specific model, tier, and validity window."""

    model_id: str
    tier: str  # "standard", "batch"
    effective_start: date
    effective_end: date
    input_per_million: float
    output_per_million: float
    cached_input_per_million: Optional[float] = None


# Official verified pricing schedules for Gemini API
# Source: https://ai.google.dev/gemini-api/docs/pricing (Verified Nov 2026)
# Standard pricing through 2026-12-31:
#   Input: $0.75 / 1M tokens
#   Output: $3.75 / 1M tokens
#   Context Cache Input: $0.075 / 1M tokens
# Standard pricing effective 2027-01-01:
#   Input: $1.50 / 1M tokens
#   Output: $7.50 / 1M tokens
#   Context Cache Input: $0.150 / 1M tokens
VERIFIED_PRICING_SCHEDULES: List[ModelPricingSchedule] = [
    # Gemini 3.8 Flash - Standard (Current through Dec 31, 2026)
    ModelPricingSchedule(
        model_id="gemini-3.8-flash",
        tier="standard",
        effective_start=date(2026, 1, 1),
        effective_end=date(2026, 12, 31),
        input_per_million=0.75,
        output_per_million=3.75,
        cached_input_per_million=0.075,
    ),
    # Gemini 3.8 Flash - Standard (Effective Jan 1, 2027 onwards)
    ModelPricingSchedule(
        model_id="gemini-3.8-flash",
        tier="standard",
        effective_start=date(2027, 1, 1),
        effective_end=date(2099, 12, 31),
        input_per_million=1.50,
        output_per_million=7.50,
        cached_input_per_million=0.150,
    ),
    # Gemini 3.8 Flash - Batch (50% discount on standard)
    ModelPricingSchedule(
        model_id="gemini-3.8-flash",
        tier="batch",
        effective_start=date(2026, 1, 1),
        effective_end=date(2026, 12, 31),
        input_per_million=0.375,
        output_per_million=1.875,
        cached_input_per_million=None,
    ),
    # Gemini 3.8 Flash - Batch (Effective Jan 1, 2027 onwards)
    ModelPricingSchedule(
        model_id="gemini-3.8-flash",
        tier="batch",
        effective_start=date(2027, 1, 1),
        effective_end=date(2099, 12, 31),
        input_per_million=0.75,
        output_per_million=3.75,
        cached_input_per_million=None,
    ),
    # Mock Provider (Zero cost)
    ModelPricingSchedule(
        model_id="mock-model-v1",
        tier="standard",
        effective_start=date(2020, 1, 1),
        effective_end=date(2099, 12, 31),
        input_per_million=0.0,
        output_per_million=0.0,
        cached_input_per_million=0.0,
    ),
]


def find_pricing_schedule(
    model_name: str,
    as_of: Optional[date] = None,
    tier: str = "standard",
) -> Optional[ModelPricingSchedule]:
    """Find the applicable pricing schedule for a model, date, and tier."""
    check_date = as_of or date.today()
    norm_model = model_name.strip().lower()
    norm_tier = tier.strip().lower()

    for sched in VERIFIED_PRICING_SCHEDULES:
        if (
            sched.model_id.lower() == norm_model
            and sched.tier.lower() == norm_tier
            and sched.effective_start <= check_date <= sched.effective_end
        ):
            return sched
    return None


def calculate_estimated_cost(
    model_name: str,
    input_tokens: Optional[int],
    output_tokens: Optional[int],
    as_of: Optional[date] = None,
    tier: str = "standard",
    cached_tokens: Optional[int] = None,
) -> Optional[float]:
    """
    Calculate estimated cost in USD based on official date-aware token pricing.

    Returns:
        float if model pricing and tokens are known, or None if pricing is unavailable,
        date is unmapped, tier is unsupported, or token metrics are missing.
        Does NOT invent costs.
    """
    if input_tokens is None or output_tokens is None:
        return None

    schedule = find_pricing_schedule(model_name, as_of=as_of, tier=tier)
    if not schedule:
        logger.debug(
            "No verified pricing schedule for model '%s', tier '%s', as_of '%s'. Cost set to None.",
            model_name,
            tier,
            as_of or date.today(),
        )
        return None

    if input_tokens < 0 or output_tokens < 0:
        return None

    # Handle cached tokens breakdown if present
    if cached_tokens is not None:
        if cached_tokens < 0:
            logger.warning(
                "Invalid usage metadata: negative cached_tokens (%d) for model '%s'. Cost set to None.",
                cached_tokens,
                model_name,
            )
            return None

        if cached_tokens > input_tokens:
            logger.warning(
                "Invalid usage metadata: cached_tokens (%d) > input_tokens (%d) for model '%s'. Cost set to None.",
                cached_tokens,
                input_tokens,
                model_name,
            )
            return None

        if cached_tokens > 0:
            if schedule.cached_input_per_million is None:
                # Tier does not support context caching discount (e.g. batch tier)
                logger.debug(
                    "Cached tokens present (%d) but model '%s' tier '%s' does not support cache discount. Cost set to None.",
                    cached_tokens,
                    model_name,
                    tier,
                )
                return None
            regular_input_tokens = input_tokens - cached_tokens
            cost_in_regular = (regular_input_tokens * schedule.input_per_million) / 1_000_000.0
            cost_in_cache = (cached_tokens * schedule.cached_input_per_million) / 1_000_000.0
            cost_in_total = cost_in_regular + cost_in_cache
        else:
            # cached_tokens == 0: all input is regular input
            cost_in_total = (input_tokens * schedule.input_per_million) / 1_000_000.0
    else:
        # cached_tokens is None: standard calculation on all input tokens
        cost_in_total = (input_tokens * schedule.input_per_million) / 1_000_000.0

    cost_out = (output_tokens / 1_000_000.0) * schedule.output_per_million
    total_cost = round(cost_in_total + cost_out, 6)
    return total_cost


def create_usage_record(
    response: NormalizedChatResponse,
    user_id: Optional[str] = None,
    feature: str = "AI_FOUNDATION",
    tier: str = "standard",
    cached_tokens: Optional[int] = None,
    thoughts_tokens: Optional[int] = None,
    as_of: Optional[date] = None,
) -> AIUsageRecord:
    """Build a normalized AIUsageRecord from a completed provider response."""
    if cached_tokens is None and hasattr(response, "metadata") and isinstance(response.metadata, dict):
        cached_tokens = response.metadata.get("cached_tokens")
    if thoughts_tokens is None and hasattr(response, "metadata") and isinstance(response.metadata, dict):
        thoughts_tokens = response.metadata.get("thoughts_tokens")

    cost = calculate_estimated_cost(
        model_name=response.model,
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
        as_of=as_of,
        tier=tier,
        cached_tokens=cached_tokens,
    )
    return AIUsageRecord(
        user_id=user_id,
        feature=feature,
        provider=response.provider,
        model_name=response.model,
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
        total_tokens=response.total_tokens,
        cached_tokens=cached_tokens,
        thoughts_tokens=thoughts_tokens,
        estimated_cost_usd=cost,
        latency_ms=response.latency_ms,
    )


async def record_usage_to_db(
    db: AsyncSession,
    usage_record: AIUsageRecord,
) -> Optional[AIUsageLog]:
    """
    Persist an AIUsageRecord into the existing `ai_usage_logs` table.
    Catches and isolates any database exceptions to prevent telemetry failures
    from breaking or corrupting the user's AI experience.

    Strict Data Integrity Policy:
        - If input_tokens is None or output_tokens is None:
          Usage metadata is unavailable (e.g. streaming chunks without final usage,
          mock responses without tokens, network drops, or unmetered provider calls).
          DO NOT PERSIST fake 0-token rows. Log a sanitized warning and return None.
        - If estimated_cost_usd is None:
          Because the database schema defines `estimated_cost_usd` as `Float, default=0.0, nullable=False`,
          persisting 0.0 would falsely report an unknown cost as a verified zero-cost transaction.
          The schema currently cannot represent unknown/NULL costs.
          DO NOT PERSIST fake cost=0.0 rows. Log a sanitized warning and return None.
        - If tokens and estimated_cost_usd are known (including verified cost == 0.0):
          Persist the record accurately.
    """
    if usage_record.input_tokens is None or usage_record.output_tokens is None:
        logger.warning(
            "Skipping AIUsageLog persistence: usage metadata unavailable (input=%s, output=%s) for model '%s'",
            usage_record.input_tokens,
            usage_record.output_tokens,
            usage_record.model_name,
        )
        return None

    if usage_record.estimated_cost_usd is None:
        logger.warning(
            "Skipping AIUsageLog persistence: estimated cost is unverified/unknown for model '%s' (input=%s, output=%s)",
            usage_record.model_name,
            usage_record.input_tokens,
            usage_record.output_tokens,
        )
        return None

    try:
        log_entry = AIUsageLog(
            user_id=usage_record.user_id,
            feature=usage_record.feature[:50],
            model_name=usage_record.model_name[:50],
            prompt_tokens=usage_record.input_tokens,
            completion_tokens=usage_record.output_tokens,
            estimated_cost_usd=usage_record.estimated_cost_usd,
        )
        db.add(log_entry)
        await db.flush()
        return log_entry
    except Exception as exc:
        logger.error(
            "Telemetry error: Failed to persist AIUsageLog for user '%s', model '%s': %s",
            usage_record.user_id,
            usage_record.model_name,
            exc,
        )
        # Never re-raise: usage logging failure must not crash business response
        return None
