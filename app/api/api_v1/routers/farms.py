from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.farm import FarmCreate, FarmUpdate, FarmRead   # 👈 importante
from app.services import farm_service

router = APIRouter(prefix="/farms", tags=["farms"])


@router.get("/", response_model=List[FarmRead])
def list_farms(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    return farm_service.list_farms(db=db, skip=skip, limit=limit)


@router.get("/{farm_id}", response_model=FarmRead)
def get_farm(
    farm_id: str,
    db: Session = Depends(get_db),
):
    farm = farm_service.get_farm(db=db, farm_id=farm_id)
    if not farm:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Farm not found")
    return farm


@router.post("/", response_model=FarmRead, status_code=status.HTTP_201_CREATED)
def create_farm(
    farm_in: FarmCreate,
    db: Session = Depends(get_db),
):
    return farm_service.create_farm(db=db, farm_in=farm_in)


@router.patch("/{farm_id}", response_model=FarmRead)
def update_farm(
    farm_id: str,
    farm_in: FarmUpdate,
    db: Session = Depends(get_db),
):
    farm = farm_service.update_farm(db=db, farm_id=farm_id, farm_in=farm_in)
    if not farm:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Farm not found")
    return farm


@router.delete("/{farm_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_farm(
    farm_id: str,
    db: Session = Depends(get_db),
):
    deleted = farm_service.delete_farm(db=db, farm_id=farm_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Farm not found")
