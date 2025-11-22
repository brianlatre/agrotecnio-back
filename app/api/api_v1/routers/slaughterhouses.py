from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db import get_db
from app.schemas.slaughterhouse import (
    SlaughterhouseCreate,
    SlaughterhouseUpdate,
    SlaughterhouseRead,
)
from app.services import slaughterhouse_service

router = APIRouter(prefix="/slaughterhouses", tags=["slaughterhouses"])
logger = get_logger(module="slaughterhouses")


@router.get("/", response_model=List[SlaughterhouseRead])
def list_slaughterhouses(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    objs = slaughterhouse_service.list_slaughterhouses(db=db, skip=skip, limit=limit)

    logger.info(
        "Listando mataderos",
        skip=skip,
        limit=limit,
        count=len(objs),
    )

    return objs


@router.get("/{slaughterhouse_id}", response_model=SlaughterhouseRead)
def get_slaughterhouse(
    slaughterhouse_id: str,
    db: Session = Depends(get_db),
):
    obj = slaughterhouse_service.get_slaughterhouse(
        db=db,
        slaughterhouse_id=slaughterhouse_id,
    )

    if not obj:
        logger.warning(
            "Matadero no encontrado",
            slaughterhouse_id=slaughterhouse_id,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Slaughterhouse not found",
        )

    logger.info(
        "Matadero recuperado",
        slaughterhouse_id=slaughterhouse_id,
    )

    return obj


@router.post(
    "/",
    response_model=SlaughterhouseRead,
    status_code=status.HTTP_201_CREATED,
)
def create_slaughterhouse(
    slaughterhouse_in: SlaughterhouseCreate,
    db: Session = Depends(get_db),
):
    obj = slaughterhouse_service.create_slaughterhouse(
        db=db,
        slaughterhouse_in=slaughterhouse_in,
    )

    logger.info(
        "Matadero creado",
        slaughterhouse_id=obj.slaughterhouse_id,
        capacity=obj.capacity_per_day,
    )

    return obj


@router.patch("/{slaughterhouse_id}", response_model=SlaughterhouseRead)
def update_slaughterhouse(
    slaughterhouse_id: str,
    slaughterhouse_in: SlaughterhouseUpdate,
    db: Session = Depends(get_db),
):
    obj = slaughterhouse_service.update_slaughterhouse(
        db=db,
        slaughterhouse_id=slaughterhouse_id,
        slaughterhouse_in=slaughterhouse_in,
    )
    if not obj:
        logger.warning(
            "Intento de actualización de matadero inexistente",
            slaughterhouse_id=slaughterhouse_id,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Slaughterhouse not found",
        )

    logger.info(
        "Matadero actualizado",
        slaughterhouse_id=slaughterhouse_id,
    )

    return obj


@router.delete(
    "/{slaughterhouse_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_slaughterhouse(
    slaughterhouse_id: str,
    db: Session = Depends(get_db),
):
    deleted = slaughterhouse_service.delete_slaughterhouse(
        db=db,
        slaughterhouse_id=slaughterhouse_id,
    )

    if not deleted:
        logger.warning(
            "Intento de borrado de matadero inexistente",
            slaughterhouse_id=slaughterhouse_id,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Slaughterhouse not found",
        )

    logger.info(
        "Matadero eliminado",
        slaughterhouse_id=slaughterhouse_id,
    )
