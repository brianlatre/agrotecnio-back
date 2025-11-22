import uuid
from typing import List, Optional

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.transport import Transport
from app.schemas.transport import TransportCreate, TransportUpdate

logger = get_logger(module="transport_service")


def create_transport(
    db: Session,
    transport_in: TransportCreate,
) -> Transport:
    transport_id = str(uuid.uuid4())

    db_obj = Transport(
        transport_id=transport_id,
        **transport_in.model_dump(),
    )
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)

    logger.info(
        "Camión creado en servicio",
        transport_id=db_obj.transport_id,
        type=getattr(db_obj, "type", None),
        capacity_tons=getattr(db_obj, "capacity_tons", None),
        cost_per_km=getattr(db_obj, "cost_per_km", None),
    )

    return db_obj


def get_transport(
    db: Session,
    transport_id: str,
) -> Optional[Transport]:
    obj = (
        db.query(Transport)
        .filter(Transport.transport_id == transport_id)
        .first()
    )
    # El not found ya se loguea en el router, aquí no spameamos.
    return obj


def list_transports(
    db: Session,
    skip: int = 0,
    limit: int = 100,
) -> List[Transport]:
    objs = (
        db.query(Transport)
        .offset(skip)
        .limit(limit)
        .all()
    )
    # El listado ya se loguea en el router.
    return objs


def update_transport(
    db: Session,
    transport_id: str,
    transport_in: TransportUpdate,
) -> Optional[Transport]:
    db_obj = get_transport(db, transport_id)
    if not db_obj:
        logger.warning(
            "Intento de actualización de camión inexistente en servicio",
            transport_id=transport_id,
        )
        return None

    update_data = transport_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_obj, field, value)

    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)

    logger.info(
        "Camión actualizado en servicio",
        transport_id=transport_id,
    )

    return db_obj


def delete_transport(
    db: Session,
    transport_id: str,
) -> bool:
    db_obj = get_transport(db, transport_id)
    if not db_obj:
        logger.warning(
            "Intento de borrado de camión inexistente en servicio",
            transport_id=transport_id,
        )
        return False

    db.delete(db_obj)
    db.commit()

    logger.info(
        "Camión eliminado en servicio",
        transport_id=transport_id,
    )

    return True
