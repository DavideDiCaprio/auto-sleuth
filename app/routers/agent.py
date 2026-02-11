from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models.car import Car
from app.schemas.car import CarQuery, CarInfo, CarResponse
from app.services.car_agent import get_car_info

import os

# ... existing imports ...

router = APIRouter()


@router.get("/status")
async def get_agent_status():
    """Check if the AI agent is configured and available."""
    api_key = os.getenv("GOOGLE_API_KEY")
    # Check if key is present and not the placeholder
    is_available = bool(api_key and api_key != "your-api-key-here")
    return {"available": is_available}


def search_car_in_db(db: Session, query: str) -> Car | None:
    """Search for a car in the database using keywords from the query."""
    words = query.strip().split()
    if not words:
        return None

    # Start with all cars, then narrow down by matching keywords
    # against make, model, and year columns
    q = db.query(Car)
    for word in words:
        # Check if the word is a year (4-digit number)
        if word.isdigit() and len(word) == 4:
            q = q.filter(Car.year == int(word))
        else:
            # Match against make or model (case-insensitive)
            pattern = f"%{word}%"
            q = q.filter(
                func.lower(Car.make).like(func.lower(pattern))
                | func.lower(Car.model).like(func.lower(pattern))
            )

    return q.first()


def save_car_to_db(db: Session, car_info: CarInfo) -> Car:
    """Save car info from the agent to the database."""
    car = Car(
        make=car_info.make,
        model=car_info.model,
        year=car_info.year,
        trim=car_info.trim,
        fuel_type=car_info.fuel_type,
        engine=car_info.engine,
        consumption_l_100km=car_info.consumption_l_100km,
        consumption_mpg=car_info.consumption_mpg,
    )
    db.add(car)
    db.commit()
    db.refresh(car)
    return car


def car_row_to_info(car: Car) -> CarInfo:
    """Convert a Car SQLAlchemy row to a CarInfo schema."""
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


@router.post("/chat", response_model=CarResponse)
async def chat_agent(query: CarQuery, db: Session = Depends(get_db)):
    """
    Look up car information.
    First checks the database; if not found, uses the AI agent
    to retrieve info and caches it in the database.
    """
    # Step 1: Search database first
    existing_car = search_car_in_db(db, query.query)
    if existing_car:
        return CarResponse(
            car=car_row_to_info(existing_car),
            source="database",
        )

    # Step 2: Not in DB — call the AI agent
    try:
        car_info = await get_car_info(query.query)
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"AI agent failed to retrieve car info: {str(e)}",
        )

    # Step 3: Save to database for future lookups
    save_car_to_db(db, car_info)

    return CarResponse(car=car_info, source="agent")
