from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models.car import Car
from app.schemas.car import CarInfo

router = APIRouter()


@router.get("/cars", response_model=List[CarInfo])
async def list_cars(db: Session = Depends(get_db)):
    """List all cars cached in the database."""
    cars = db.query(Car).all()
    return [
        CarInfo(
            make=c.make,
            model=c.model,
            year=c.year,
            trim=c.trim,
            fuel_type=c.fuel_type,
            engine=c.engine,
            consumption_l_100km=c.consumption_l_100km,
            consumption_mpg=c.consumption_mpg,
        )
        for c in cars
    ]


@router.get("/cars/{car_id}", response_model=CarInfo)
async def get_car(car_id: int, db: Session = Depends(get_db)):
    """Get a single car by ID."""
    car = db.query(Car).filter(Car.id == car_id).first()
    if not car:
        raise HTTPException(status_code=404, detail="Car not found")
    return CarInfo(
        make=car.make,
        model=car.model,
        year=car.year,
        trim=car.trim,
        fuel_type=car.fuel_type,
        engine=car.engine,
        consumption_l_100km=car.consumption_l_100km,
        consumption_mpg=car.consumption_mpg,
    )


@router.delete("/cars/{car_id}")
async def delete_car(car_id: int, db: Session = Depends(get_db)):
    """Delete a cached car entry."""
    car = db.query(Car).filter(Car.id == car_id).first()
    if not car:
        raise HTTPException(status_code=404, detail="Car not found")
    db.delete(car)
    db.commit()
    return {"message": f"Car {car_id} deleted"}
