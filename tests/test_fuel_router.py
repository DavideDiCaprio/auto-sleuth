import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from app.services.geolocation import GeolocationError
from app.services.fuel import FuelPriceError


# ---------------------------------------------------------------------------
# Sample mock data reused across tests
# ---------------------------------------------------------------------------

MOCK_IT_LOCATION = {
    "city": "Roma",
    "region": "LZ",
    "regionName": "Lazio",
    "country": "Italia",
    "countryCode": "IT",
    "lat": "41.9028",
    "lon": "12.4964",
}

MOCK_FOREIGN_LOCATION = {
    "city": "Berlin",
    "region": "BE",
    "regionName": "Berlin",
    "country": "Germany",
    "countryCode": "DE",
    "lat": "52.5200",
    "lon": "13.4050",
}

MOCK_NEARBY_PRICES = {
    "currency": "EUR",
    "gasoline": 1.789,
    "diesel": 1.649,
    "gpl": 0.729,
    "methane": 1.399,
    "source": "MIMIT Open Data (Avg of 15 stations within 20.0km)",
    "station_count": 15,
}

MOCK_REGIONAL_DATA = {
    "region": "Lazio",
    "prices": {"gasoline": 1.795, "diesel": 1.660, "gpl": 0.735, "methane": 1.410},
    "station_count": 450,
}

MOCK_NATIONAL_DATA = {
    "country": "Italy",
    "prices": {"gasoline": 1.810, "diesel": 1.670, "gpl": 0.740, "methane": 1.420},
    "station_count": 20000,
}


# ---------------------------------------------------------------------------
# Fuel price endpoint: /api/v1/fuel-price
# ---------------------------------------------------------------------------

class TestFuelPriceEndpoint:
    """Tests for GET /api/v1/fuel-price."""

    ENDPOINT = "/api/v1/fuel-price"

    # --- Happy path ---

    @patch("app.routers.fuel.get_fuel_price_service")
    @patch("app.routers.fuel.get_user_location", new_callable=AsyncMock)
    @patch("app.routers.fuel.get_client_ip")
    def test_italian_user_gets_full_response(
        self, mock_ip, mock_location, mock_service_factory, client
    ):
        """An Italian user should receive location + nearby + regional + national prices."""
        mock_ip.return_value = "151.100.0.0"
        mock_location.return_value = MOCK_IT_LOCATION

        mock_service = MagicMock()
        mock_service.get_nearby_prices = AsyncMock(return_value=MOCK_NEARBY_PRICES)
        mock_service.get_regional_average = AsyncMock(return_value=MOCK_REGIONAL_DATA)
        mock_service.get_national_average = AsyncMock(return_value=MOCK_NATIONAL_DATA)
        mock_service_factory.return_value = mock_service

        response = client.get(self.ENDPOINT)

        assert response.status_code == 200
        data = response.json()

        # Top-level keys
        assert "location" in data
        assert "fuel_price" in data
        assert "price_data" in data

        # Location
        assert data["location"]["city"] == "Roma"
        assert data["location"]["countryCode"] == "IT"

        # Price data structure
        assert data["price_data"]["nearby"] == MOCK_NEARBY_PRICES
        assert data["price_data"]["regional"] == MOCK_REGIONAL_DATA
        assert data["price_data"]["national"] == MOCK_NATIONAL_DATA

    @patch("app.routers.fuel.get_fuel_price_service")
    @patch("app.routers.fuel.get_user_location", new_callable=AsyncMock)
    @patch("app.routers.fuel.get_client_ip")
    def test_fuel_price_is_nearby_data(
        self, mock_ip, mock_location, mock_service_factory, client
    ):
        """The top-level 'fuel_price' key should equal the nearby data."""
        mock_ip.return_value = "151.100.0.0"
        mock_location.return_value = MOCK_IT_LOCATION

        mock_service = MagicMock()
        mock_service.get_nearby_prices = AsyncMock(return_value=MOCK_NEARBY_PRICES)
        mock_service.get_regional_average = AsyncMock(return_value=MOCK_REGIONAL_DATA)
        mock_service.get_national_average = AsyncMock(return_value=MOCK_NATIONAL_DATA)
        mock_service_factory.return_value = mock_service

        data = client.get(self.ENDPOINT).json()
        assert data["fuel_price"] == data["price_data"]["nearby"]

    # --- Country restriction ---

    @patch("app.routers.fuel.get_user_location", new_callable=AsyncMock)
    @patch("app.routers.fuel.get_client_ip")
    def test_non_italian_user_gets_403(self, mock_ip, mock_location, client):
        """Users outside Italy should receive a 403 Forbidden."""
        mock_ip.return_value = "93.184.216.34"
        mock_location.return_value = MOCK_FOREIGN_LOCATION

        response = client.get(self.ENDPOINT)

        assert response.status_code == 403
        assert "Germany" in response.json()["detail"]

    @patch("app.routers.fuel.get_user_location", new_callable=AsyncMock)
    @patch("app.routers.fuel.get_client_ip")
    def test_403_detail_includes_country_name(self, mock_ip, mock_location, client):
        """The 403 error message should mention the user's detected country."""
        mock_ip.return_value = "1.2.3.4"
        mock_location.return_value = {
            **MOCK_FOREIGN_LOCATION,
            "country": "France",
            "countryCode": "FR",
        }

        response = client.get(self.ENDPOINT)
        assert response.status_code == 403
        assert "France" in response.json()["detail"]

    # --- Geolocation failures ---

    @patch("app.routers.fuel.get_user_location", new_callable=AsyncMock)
    @patch("app.routers.fuel.get_client_ip")
    def test_geolocation_error_returns_503(self, mock_ip, mock_location, client):
        """When geolocation service fails, return 503."""
        mock_ip.return_value = "10.0.0.1"
        mock_location.side_effect = GeolocationError("ip-api unreachable")

        response = client.get(self.ENDPOINT)

        assert response.status_code == 503
        assert "Geolocation service unavailable" in response.json()["detail"]
        assert "ip-api unreachable" in response.json()["detail"]

    # --- Fuel price service failures ---

    @patch("app.routers.fuel.get_fuel_price_service")
    @patch("app.routers.fuel.get_user_location", new_callable=AsyncMock)
    @patch("app.routers.fuel.get_client_ip")
    def test_fuel_price_error_returns_503(
        self, mock_ip, mock_location, mock_service_factory, client
    ):
        """When the fuel price service fails, return 503."""
        mock_ip.return_value = "151.100.0.0"
        mock_location.return_value = MOCK_IT_LOCATION

        mock_service = MagicMock()
        mock_service.get_nearby_prices = AsyncMock(
            side_effect=FuelPriceError("MIMIT CSV download failed")
        )
        mock_service_factory.return_value = mock_service

        response = client.get(self.ENDPOINT)

        assert response.status_code == 503
        assert "Fuel price service unavailable" in response.json()["detail"]

    # --- Regional data handling ---

    @patch("app.routers.fuel.get_fuel_price_service")
    @patch("app.routers.fuel.get_user_location", new_callable=AsyncMock)
    @patch("app.routers.fuel.get_client_ip")
    def test_missing_region_name_skips_regional_data(
        self, mock_ip, mock_location, mock_service_factory, client
    ):
        """When regionName is empty, regional data should be None."""
        mock_ip.return_value = "151.100.0.0"
        location_no_region = {**MOCK_IT_LOCATION, "regionName": ""}
        mock_location.return_value = location_no_region

        mock_service = MagicMock()
        mock_service.get_nearby_prices = AsyncMock(return_value=MOCK_NEARBY_PRICES)
        mock_service.get_regional_average = AsyncMock(return_value=MOCK_REGIONAL_DATA)
        mock_service.get_national_average = AsyncMock(return_value=MOCK_NATIONAL_DATA)
        mock_service_factory.return_value = mock_service

        data = client.get(self.ENDPOINT).json()

        assert data["price_data"]["regional"] is None
        # get_regional_average should NOT have been called
        mock_service.get_regional_average.assert_not_called()

    @patch("app.routers.fuel.get_fuel_price_service")
    @patch("app.routers.fuel.get_user_location", new_callable=AsyncMock)
    @patch("app.routers.fuel.get_client_ip")
    def test_service_called_with_correct_coordinates(
        self, mock_ip, mock_location, mock_service_factory, client
    ):
        """The service should receive the lat/lon from geolocation."""
        mock_ip.return_value = "151.100.0.0"
        mock_location.return_value = MOCK_IT_LOCATION

        mock_service = MagicMock()
        mock_service.get_nearby_prices = AsyncMock(return_value=MOCK_NEARBY_PRICES)
        mock_service.get_regional_average = AsyncMock(return_value=MOCK_REGIONAL_DATA)
        mock_service.get_national_average = AsyncMock(return_value=MOCK_NATIONAL_DATA)
        mock_service_factory.return_value = mock_service

        client.get(self.ENDPOINT)

        mock_service.get_nearby_prices.assert_called_once_with(41.9028, 12.4964)
        mock_service.get_regional_average.assert_called_once_with("Lazio")

    # --- IP extraction ---

    @patch("app.routers.fuel.get_fuel_price_service")
    @patch("app.routers.fuel.get_user_location", new_callable=AsyncMock)
    @patch("app.routers.fuel.get_client_ip")
    def test_client_ip_passed_to_geolocation(
        self, mock_ip, mock_location, mock_service_factory, client
    ):
        """The extracted client IP should be forwarded to get_user_location."""
        mock_ip.return_value = "203.0.113.50"
        mock_location.return_value = MOCK_IT_LOCATION

        mock_service = MagicMock()
        mock_service.get_nearby_prices = AsyncMock(return_value=MOCK_NEARBY_PRICES)
        mock_service.get_regional_average = AsyncMock(return_value=MOCK_REGIONAL_DATA)
        mock_service.get_national_average = AsyncMock(return_value=MOCK_NATIONAL_DATA)
        mock_service_factory.return_value = mock_service

        client.get(self.ENDPOINT)

        mock_location.assert_called_once_with("203.0.113.50")


# ---------------------------------------------------------------------------
# Health check endpoint (already exists in test_api.py, but grouped here too)
# ---------------------------------------------------------------------------

class TestHealthEndpoint:

    def test_health_returns_ok(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "service": "AutoSleuth"}
