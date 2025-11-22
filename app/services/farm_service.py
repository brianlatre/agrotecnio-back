import uuid
from typing import List, Optional

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.farm import Farm
from app.schemas.farm import FarmCreate, FarmUpdate

logger = get_logger(module="farm_service")


def create_farm(db: Session, farm_in: FarmCreate) -> Farm:
    farm_id = str(uuid.uuid4())

    db_obj = Farm(
        farm_id=farm_id,
        **farm_in.model_dump(),
    )
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)

    logger.info(
        "Granja creada en servicio",
        farm_id=db_obj.farm_id,
        name=getattr(db_obj, "name", None),
        inventory_pigs=getattr(db_obj, "inventory_pigs", None),
    )

    return db_obj


def get_farm(db: Session, farm_id: str) -> Optional[Farm]:
    farm = (
        db.query(Farm)
        .filter(Farm.farm_id == farm_id)
        .first()
    )
    # No meto log aquí para no spamear en cada GET; ya se loguea en el router.
    return farm


def list_farms(db: Session, skip: int = 0, limit: int = 100) -> List[Farm]:
    farms = (
        db.query(Farm)
        .offset(skip)
        .limit(limit)
        .all()
    )
    # Igual que get_farm: el log “bonito” ya está en el router.
    return farms


def update_farm(db: Session, farm_id: str, farm_in: FarmUpdate) -> Optional[Farm]:
    db_obj = get_farm(db, farm_id)
    if not db_obj:
        logger.warning(
            "Intento de actualización de granja inexistente en servicio",
            farm_id=farm_id,
        )
        return None

    update_data = farm_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_obj, field, value)

    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)

    logger.info(
        "Granja actualizada en servicio",
        farm_id=farm_id,
    )

    return db_obj


def delete_farm(db: Session, farm_id: str) -> bool:
    db_obj = get_farm(db, farm_id)
    if not db_obj:
        logger.warning(
            "Intento de borrado de granja inexistente en servicio",
            farm_id=farm_id,
        )
        return False

    db.delete(db_obj)
    db.commit()

    logger.info(
        "Granja eliminada en servicio",
        farm_id=farm_id,
    )

    return True
