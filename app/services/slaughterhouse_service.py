import uuid
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.slaughterhouse import Slaughterhouse
from app.schemas.slaughterhouse import (
    SlaughterhouseCreate,
    SlaughterhouseUpdate,
)


def create_slaughterhouse(
    db: Session,
    slaughterhouse_in: SlaughterhouseCreate,
) -> Slaughterhouse:
    slaughterhouse_id = str(uuid.uuid4())

    db_obj = Slaughterhouse(
        slaughterhouse_id=slaughterhouse_id,
        **slaughterhouse_in.model_dump(),
    )
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def get_slaughterhouse(
    db: Session,
    slaughterhouse_id: str,
) -> Optional[Slaughterhouse]:
    return (
        db.query(Slaughterhouse)
        .filter(Slaughterhouse.slaughterhouse_id == slaughterhouse_id)
        .first()
    )


def list_slaughterhouses(
    db: Session,
    skip: int = 0,
    limit: int = 100,
) -> List[Slaughterhouse]:
    return (
        db.query(Slaughterhouse)
        .offset(skip)
        .limit(limit)
        .all()
    )


def update_slaughterhouse(
    db: Session,
    slaughterhouse_id: str,
    slaughterhouse_in: SlaughterhouseUpdate,
) -> Optional[Slaughterhouse]:
    db_obj = get_slaughterhouse(db, slaughterhouse_id)
    if not db_obj:
        return None

    update_data = slaughterhouse_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_obj, field, value)

    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def delete_slaughterhouse(
    db: Session,
    slaughterhouse_id: str,
) -> bool:
    db_obj = get_slaughterhouse(db, slaughterhouse_id)
    if not db_obj:
        return False

    db.delete(db_obj)
    db.commit()
    return True
