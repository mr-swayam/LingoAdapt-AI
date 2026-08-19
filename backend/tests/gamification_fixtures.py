from sqlalchemy.orm import Session

from app.models.gamification import Achievement
from app.services.gamification_service import ACHIEVEMENT_CATALOG


def seed_achievement_catalog(db: Session) -> None:
    existing_codes = {a.code for a in db.query(Achievement).all()}
    for achievement_def in ACHIEVEMENT_CATALOG:
        if achievement_def.code in existing_codes:
            continue
        db.add(
            Achievement(
                code=achievement_def.code,
                name=achievement_def.name,
                description=achievement_def.description,
            )
        )
    db.commit()
