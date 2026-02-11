
import pytest
from unittest.mock import patch, MagicMock
from app.services.geolocation import GeolocationError
from app.services.fuel import FuelPriceError

def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "AutoSleuth"}