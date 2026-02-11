import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from app.services.geolocation import get_client_ip, get_user_location, GeolocationError


# ---------------------------------------------------------------------------
# Tests for get_client_ip
# ---------------------------------------------------------------------------

class TestGetClientIp:
    """Tests for extracting the client IP from a FastAPI Request object."""

    def _make_request(self, headers=None, client_host="192.168.1.1"):
        """Helper to build a minimal mock Request."""
        request = MagicMock()
        request.headers = headers or {}
        request.client.host = client_host
        return request

    def test_returns_client_host_when_no_forwarded_header(self):
        request = self._make_request(client_host="10.0.0.5")
        assert get_client_ip(request) == "10.0.0.5"

    def test_returns_first_ip_from_x_forwarded_for(self):
        """X-Forwarded-For may contain a chain: 'client, proxy1, proxy2'."""
        request = self._make_request(
            headers={"X-Forwarded-For": "203.0.113.50, 70.41.3.18, 150.172.238.178"},
            client_host="127.0.0.1",
        )
        assert get_client_ip(request) == "203.0.113.50"

    def test_returns_single_ip_from_x_forwarded_for(self):
        request = self._make_request(
            headers={"X-Forwarded-For": "203.0.113.50"},
            client_host="127.0.0.1",
        )
        assert get_client_ip(request) == "203.0.113.50"

    def test_strips_whitespace_from_forwarded_ip(self):
        request = self._make_request(
            headers={"X-Forwarded-For": "  203.0.113.50 , 70.41.3.18"},
        )
        assert get_client_ip(request) == "203.0.113.50"

    def test_falls_back_to_client_host_when_header_is_absent(self):
        request = self._make_request(headers={}, client_host="172.16.0.1")
        assert get_client_ip(request) == "172.16.0.1"


# ---------------------------------------------------------------------------
# Tests for get_user_location
# ---------------------------------------------------------------------------

# Sample successful API response (Italian locale)
SAMPLE_SUCCESS_RESPONSE = {
    "status": "success",
    "city": "Roma",
    "region": "LZ",
    "regionName": "Lazio",
    "country": "Italia",
    "countryCode": "IT",
    "lat": 41.8933,
    "lon": 12.4829,
}

# Sample failed API response
SAMPLE_FAIL_RESPONSE = {
    "status": "fail",
    "message": "reserved range",
}


class TestGetUserLocation:
    """Tests for the async get_user_location function (mocked HTTP)."""

    @pytest.mark.asyncio
    async def test_successful_italian_location(self):
        """Happy path: valid Italian IP returns properly formatted dict."""
        mock_response = MagicMock()
        mock_response.json.return_value = SAMPLE_SUCCESS_RESPONSE
        mock_response.raise_for_status = MagicMock()

        with patch("app.services.geolocation.httpx.AsyncClient") as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.get.return_value = mock_response
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await get_user_location("151.100.0.0")

        assert result["city"] == "Roma"
        assert result["regionName"] == "Lazio"
        assert result["countryCode"] == "IT"
        assert result["lat"] == "41.8933"
        assert result["lon"] == "12.4829"

    @pytest.mark.asyncio
    async def test_returns_defaults_for_missing_fields(self):
        """When the API returns sparse data, defaults should fill in."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "success"}
        mock_response.raise_for_status = MagicMock()

        with patch("app.services.geolocation.httpx.AsyncClient") as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.get.return_value = mock_response
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await get_user_location("8.8.8.8")

        assert result["city"] == "Sconosciuto"
        assert result["region"] == ""
        assert result["regionName"] == ""
        assert result["country"] == ""
        assert result["countryCode"] == ""
        assert result["lat"] == "0"
        assert result["lon"] == "0"

    @pytest.mark.asyncio
    async def test_raises_geolocation_error_on_api_fail_status(self):
        """When ip-api returns status='fail', we should raise GeolocationError."""
        mock_response = MagicMock()
        mock_response.json.return_value = SAMPLE_FAIL_RESPONSE
        mock_response.raise_for_status = MagicMock()

        with patch("app.services.geolocation.httpx.AsyncClient") as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.get.return_value = mock_response
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            with pytest.raises(GeolocationError, match="reserved range"):
                await get_user_location("192.168.1.1")

    @pytest.mark.asyncio
    async def test_raises_geolocation_error_on_http_error(self):
        """Network/HTTP errors should be wrapped in GeolocationError."""
        with patch("app.services.geolocation.httpx.AsyncClient") as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.get.side_effect = httpx.HTTPStatusError(
                "Server Error", request=MagicMock(), response=MagicMock(status_code=500)
            )
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            with pytest.raises(GeolocationError, match="Geo Error"):
                await get_user_location("8.8.8.8")

    @pytest.mark.asyncio
    async def test_raises_geolocation_error_on_timeout(self):
        """Timeouts should be wrapped in GeolocationError."""
        with patch("app.services.geolocation.httpx.AsyncClient") as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.get.side_effect = httpx.ReadTimeout("Connection timed out")
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            with pytest.raises(GeolocationError, match="Geo Error"):
                await get_user_location("8.8.8.8")

    @pytest.mark.asyncio
    async def test_localhost_uses_base_url_without_ip(self):
        """When IP is 127.0.0.1, the request should go to the base URL (auto-detect)."""
        mock_response = MagicMock()
        mock_response.json.return_value = SAMPLE_SUCCESS_RESPONSE
        mock_response.raise_for_status = MagicMock()

        with patch("app.services.geolocation.httpx.AsyncClient") as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.get.return_value = mock_response
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            await get_user_location("127.0.0.1")

            # Verify the URL does NOT contain the IP
            call_args = mock_client_instance.get.call_args
            assert call_args[0][0] == "http://ip-api.com/json/"

    @pytest.mark.asyncio
    async def test_normal_ip_appended_to_url(self):
        """A normal IP should be appended to the base URL."""
        mock_response = MagicMock()
        mock_response.json.return_value = SAMPLE_SUCCESS_RESPONSE
        mock_response.raise_for_status = MagicMock()

        with patch("app.services.geolocation.httpx.AsyncClient") as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.get.return_value = mock_response
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            await get_user_location("151.100.0.0")

            call_args = mock_client_instance.get.call_args
            assert call_args[0][0] == "http://ip-api.com/json/151.100.0.0"

    @pytest.mark.asyncio
    async def test_lang_it_param_is_sent(self):
        """The request must include lang='it' to get Italian names."""
        mock_response = MagicMock()
        mock_response.json.return_value = SAMPLE_SUCCESS_RESPONSE
        mock_response.raise_for_status = MagicMock()

        with patch("app.services.geolocation.httpx.AsyncClient") as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.get.return_value = mock_response
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            await get_user_location("151.100.0.0")

            call_args = mock_client_instance.get.call_args
            assert call_args[1]["params"] == {"lang": "it"}
