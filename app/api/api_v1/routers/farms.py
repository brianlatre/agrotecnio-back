from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db import get_db
from app.schemas.farm import FarmCreate, FarmUpdate, FarmRead
from app.services import farm_service

router = APIRouter(prefix="/farms", tags=["farms"])
logger = get_logger(module="farms")


@router.get("/", response_model=List[FarmRead])
def list_farms(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    farms = farm_service.list_farms(db=db, skip=skip, limit=limit)
    logger.info(
        "Listando granjas",
        skip=skip,
        limit=limit,
        farms_count=len(farms),
    )
    return farms


@router.get("/{farm_id}", response_model=FarmRead)
def get_farm(
    farm_id: str,
    db: Session = Depends(get_db),
):
    farm = farm_service.get_farm(db=db, farm_id=farm_id)
    if not farm:
        logger.warning("Granja no encontrada", farm_id=farm_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Farm not found",
        )

    logger.info(
        "Granja recuperada",
        farm_id=farm_id,
    )
    return farm


@router.post("/", response_model=FarmRead, status_code=status.HTTP_201_CREATED)
def create_farm(
    farm_in: FarmCreate,
    db: Session = Depends(get_db),
):
    farm = farm_service.create_farm(db=db, farm_in=farm_in)
    logger.info(
        "Granja creada",
        farm_id=farm.farm_id,
        name=getattr(farm, "name", None),
    )
    return farm


@router.patch("/{farm_id}", response_model=FarmRead)
def update_farm(
    farm_id: str,
    farm_in: FarmUpdate,
    db: Session = Depends(get_db),
):
    farm = farm_service.update_farm(db=db, farm_id=farm_id, farm_in=farm_in)
    if not farm:
        logger.warning("Intento de actualización de granja inexistente", farm_id=farm_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Farm not found",
        )

    logger.info(
        "Granja actualizada",
        farm_id=farm_id,
    )
    return farm


@router.delete("/{farm_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_farm(
    farm_id: str,
    db: Session = Depends(get_db),
):
    deleted = farm_service.delete_farm(db=db, farm_id=farm_id)
    if not deleted:
        logger.warning("Intento de borrado de granja inexistente", farm_id=farm_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Farm not found",
        )

    logger.info(
        "Granja eliminada",
        farm_id=farm_id,
    )
