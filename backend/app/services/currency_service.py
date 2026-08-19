"""Virtual currency (gems). Thin, deterministic wrapper - no AI involved,
rules.md §2: currency balances are server-owned. Mirrors XPTransaction's
idempotency pattern: a (source_id, reason) pair can only ever be awarded
once, enforced at the DB level (uq_currency_transaction_source_reason) and
checked here so a duplicate call is a safe no-op, not a duplicate award.
"""

import uuid

from sqlalchemy.orm import Session

from app.models.gamification import CurrencyReason, CurrencyTransaction
from app.repositories import gamification_repository


def get_balance(db: Session, user_id: uuid.UUID) -> int:
    return gamification_repository.get_currency_balance(db, user_id)


def award_currency(
    db: Session, *, user_id: uuid.UUID, amount: int, reason: CurrencyReason, source_id: str
) -> CurrencyTransaction | None:
    """Returns None (no-op) if this exact (source_id, reason) was already
    awarded - safe to call every time the triggering condition is observed,
    not just the first time."""
    existing = gamification_repository.get_currency_transaction(
        db, source_id=source_id, reason=reason
    )
    if existing is not None:
        return None

    return gamification_repository.record_currency_transaction(
        db, user_id=user_id, amount=amount, reason=reason, source_id=source_id
    )
