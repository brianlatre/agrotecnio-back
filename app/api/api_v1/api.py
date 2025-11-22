# app/api/api_v1/api.py
from fastapi import APIRouter

from app.api.api_v1.routers import (
    farms,
    slaughterhouses,
    transports,
)

api_router = APIRouter()

api_router.include_router(farms.router)
api_router.include_router(slaughterhouses.router)
api_router.include_router(transports.router)
