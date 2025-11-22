import uuid
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.farm import Farm
from app.schemas.farm import FarmCreate, FarmUpdate


def create_farm(db: Session, farm_in: FarmCreate) -> Farm:
    farm_id = str(uuid.uuid4())

    db_obj = Farm(
        farm_id=farm_id,
        **farm_in.model_dump(),
    )
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def get_farm(db: Session, farm_id: str) -> Optional[Farm]:
    return (
        db.query(Farm)
        .filter(Farm.farm_id == farm_id)
        .first()
    )


def list_farms(db: Session, skip: int = 0, limit: int = 100) -> List[Farm]:
    return (
        db.query(Farm)
        .offset(skip)
        .limit(limit)
        .all()
    )


def update_farm(db: Session, farm_id: str, farm_in: FarmUpdate) -> Optional[Farm]:
    db_obj = get_farm(db, farm_id)
    if not db_obj:
        return None

    update_data = farm_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_obj, field, value)

    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def delete_farm(db: Session, farm_id: str) -> bool:
    db_obj = get_farm(db, farm_id)
    if not db_obj:
        return False

    db.delete(db_obj)
    db.commit()
    return True
