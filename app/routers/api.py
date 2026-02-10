
from fastapi import APIRouter
from app.routers import gas_price, car_info

router = APIRouter()

router.include_router(gas_price.router, tags=["Gas Price"])
router.include_router(car_info.router)
