import uuid
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.transport import Transport
from app.schemas.transport import TransportCreate, TransportUpdate


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
    return db_obj


def get_transport(
    db: Session,
    transport_id: str,
) -> Optional[Transport]:
    return (
        db.query(Transport)
        .filter(Transport.transport_id == transport_id)
        .first()
    )


def list_transports(
    db: Session,
    skip: int = 0,
    limit: int = 100,
) -> List[Transport]:
    return (
        db.query(Transport)
        .offset(skip)
        .limit(limit)
        .all()
    )


def update_transport(
    db: Session,
    transport_id: str,
    transport_in: TransportUpdate,
) -> Optional[Transport]:
    db_obj = get_transport(db, transport_id)
    if not db_obj:
        return None

    update_data = transport_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_obj, field, value)

    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def delete_transport(
    db: Session,
    transport_id: str,
) -> bool:
    db_obj = get_transport(db, transport_id)
    if not db_obj:
        return False

    db.delete(db_obj)
    db.commit()
    return True
