import uuid
from typing import List, Optional

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.slaughterhouse import Slaughterhouse
from app.schemas.slaughterhouse import (
    SlaughterhouseCreate,
    SlaughterhouseUpdate,
)

logger = get_logger(module="slaughterhouse_service")


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

    logger.info(
        "Matadero creado en servicio",
        slaughterhouse_id=db_obj.slaughterhouse_id,
        capacity_per_day=getattr(db_obj, "capacity_per_day", None),
        price_per_kg=getattr(db_obj, "price_per_kg", None),
    )

    return db_obj


def get_slaughterhouse(
    db: Session,
    slaughterhouse_id: str,
) -> Optional[Slaughterhouse]:
    obj = (
        db.query(Slaughterhouse)
        .filter(Slaughterhouse.slaughterhouse_id == slaughterhouse_id)
        .first()
    )
    # El not found ya se loguea en el router; aquí no spameamos.
    return obj


def list_slaughterhouses(
    db: Session,
    skip: int = 0,
    limit: int = 100,
) -> List[Slaughterhouse]:
    objs = (
        db.query(Slaughterhouse)
        .offset(skip)
        .limit(limit)
        .all()
    )
    # El log de listado ya está en el router.
    return objs


def update_slaughterhouse(
    db: Session,
    slaughterhouse_id: str,
    slaughterhouse_in: SlaughterhouseUpdate,
) -> Optional[Slaughterhouse]:
    db_obj = get_slaughterhouse(db, slaughterhouse_id)
    if not db_obj:
        logger.warning(
            "Intento de actualización de matadero inexistente en servicio",
            slaughterhouse_id=slaughterhouse_id,
        )
        return None

    update_data = slaughterhouse_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_obj, field, value)

    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)

    logger.info(
        "Matadero actualizado en servicio",
        slaughterhouse_id=slaughterhouse_id,
    )

    return db_obj


def delete_slaughterhouse(
    db: Session,
    slaughterhouse_id: str,
) -> bool:
    db_obj = get_slaughterhouse(db, slaughterhouse_id)
    if not db_obj:
        logger.warning(
            "Intento de borrado de matadero inexistente en servicio",
            slaughterhouse_id=slaughterhouse_id,
        )
        return False

    db.delete(db_obj)
    db.commit()

    logger.info(
        "Matadero eliminado en servicio",
        slaughterhouse_id=slaughterhouse_id,
    )

    return True
