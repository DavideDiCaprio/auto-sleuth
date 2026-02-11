from sqlalchemy import Column, Integer, String, Float
from app.database import Base

class Car(Base):
    __tablename__ = "cars"

    id = Column(Integer, primary_key=True, index=True)
    make = Column(String, index=True)
    model = Column(String, index=True)
    year = Column(Integer, index=True)
    trim = Column(String)
    fuel_type = Column(String, nullable=True)
    engine = Column(String)
    consumption_l_100km = Column(Float, nullable=True)
    consumption_mpg = Column(Float, nullable=True)
