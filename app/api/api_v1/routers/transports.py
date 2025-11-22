from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db import get_db
from app.schemas.transport import (
    TransportCreate,
    TransportUpdate,
    TransportRead,
)
from app.services import transport_service

router = APIRouter(prefix="/transports", tags=["transports"])
logger = get_logger(module="transports")


@router.get("/", response_model=List[TransportRead])
def list_transports(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    objs = transport_service.list_transports(db=db, skip=skip, limit=limit)

    logger.info(
        "Listando camiones",
        skip=skip,
        limit=limit,
        count=len(objs),
    )

    return objs


@router.get("/{transport_id}", response_model=TransportRead)
def get_transport(
    transport_id: str,
    db: Session = Depends(get_db),
):
    obj = transport_service.get_transport(
        db=db,
        transport_id=transport_id,
    )

    if not obj:
        logger.warning(
            "Camión no encontrado",
            transport_id=transport_id,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transport not found",
        )

    logger.info(
        "Camión recuperado",
        transport_id=transport_id,
    )

    return obj


@router.post(
    "/",
    response_model=TransportRead,
    status_code=status.HTTP_201_CREATED,
)
def create_transport(
    transport_in: TransportCreate,
    db: Session = Depends(get_db),
):
    obj = transport_service.create_transport(
        db=db,
        transport_in=transport_in,
    )

    logger.info(
        "Camión creado",
        transport_id=obj.transport_id,
        capacity_tons=obj.capacity_tons,
        cost_per_km=obj.cost_per_km,
    )

    return obj


@router.patch("/{transport_id}", response_model=TransportRead)
def update_transport(
    transport_id: str,
    transport_in: TransportUpdate,
    db: Session = Depends(get_db),
):
    obj = transport_service.update_transport(
        db=db,
        transport_id=transport_id,
        transport_in=transport_in,
    )

    if not obj:
        logger.warning(
            "Intento de actualización de camión inexistente",
            transport_id=transport_id,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transport not found",
        )

    logger.info(
        "Camión actualizado",
        transport_id=transport_id,
    )

    return obj


@router.delete(
    "/{transport_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_transport(
    transport_id: str,
    db: Session = Depends(get_db),
):
    deleted = transport_service.delete_transport(
        db=db,
        transport_id=transport_id,
    )

    if not deleted:
        logger.warning(
            "Intento de borrado de camión inexistente",
            transport_id=transport_id,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transport not found",
        )

    logger.info(
        "Camión eliminado",
        transport_id=transport_id,
    )
