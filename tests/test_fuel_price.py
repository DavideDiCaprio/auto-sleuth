import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from app.services.fuel import (
    MimitFuelPriceService,
    FuelPriceError,
    get_fuel_price_service,
    PROVINCE_TO_REGION,
)


# ---------------------------------------------------------------------------
# Realistic mock CSV data matching the MIMIT format
# ---------------------------------------------------------------------------

# Registry CSV format (pipe-delimited):
# Line 1: Header row
# Line 2: Extraction date
# Line 3+: idImpianto|Gestore|Bandiera|Tipo Impianto|Nome Impianto|Indirizzo|Comune|Provincia|Latitudine|Longitudine

MOCK_REGISTRY_CSV = """\
idImpianto;Gestore;Bandiera;Tipo Impianto;Nome Impianto;Indirizzo;Comune;Provincia;Latitudine;Longitudine
csv_aggiornato_al_11_02_2026
1001|Mario Rossi|ENI|Stradale|Stazione ENI Roma|Via Appia, 1|Roma|RM|41,9028|12,4964
1002|Luigi Verdi|Q8|Stradale|Stazione Q8 Milano|Corso Buenos Aires, 10|Milano|MI|45,4642|9,1900
1003|Paolo Bianchi|IP|Stradale|Stazione IP Napoli|Via Toledo, 50|Napoli|NA|40,8518|14,2681
9999|Invalid Coords|Shell|Stradale|Bad Station|Via Errore|Errore|XX|not_a_number|12,0000
"""

# Price CSV format (pipe-delimited):
# Line 1: Header row
# Line 2: Extraction date
# Line 3+: idImpianto|descCarburante|prezzo|isSelf|dtComu

MOCK_PRICES_CSV = """\
idImpianto;descCarburante;prezzo;isSelf;dtComu
csv_aggiornato_al_11_02_2026
1001|Benzina|1.789|1|11/02/2026 08:00:00
1001|Gasolio|1.649|1|11/02/2026 08:00:00
1001|GPL|0.729|1|11/02/2026 08:00:00
1002|Benzina|1.819|1|11/02/2026 08:00:00
1002|Gasolio|1.679|1|11/02/2026 08:00:00
1002|Metano|1.399|1|11/02/2026 08:00:00
1003|Benzina|1.759|1|11/02/2026 08:00:00
1003|Gasolio|1.629|1|11/02/2026 08:00:00
8888|Benzina|1.999|1|11/02/2026 08:00:00
"""
# Note: station 8888 is in prices but NOT in registry → should be skipped
# Note: station 9999 has invalid coordinates → should be skipped during registry parsing


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def service():
    """Fresh service instance for each test (no shared cache)."""
    return MimitFuelPriceService()


@pytest.fixture
def parsed_stations(service):
    """Pre-parsed station data from mock CSVs."""
    return service._parse_and_join_data(MOCK_PRICES_CSV, MOCK_REGISTRY_CSV)


# ---------------------------------------------------------------------------
# Tests for singleton pattern
# ---------------------------------------------------------------------------

class TestSingleton:

    def test_get_fuel_price_service_returns_same_instance(self):
        s1 = get_fuel_price_service()
        s2 = get_fuel_price_service()
        assert s1 is s2

    def test_returns_mimit_service_instance(self):
        assert isinstance(get_fuel_price_service(), MimitFuelPriceService)


# ---------------------------------------------------------------------------
# Tests for _parse_and_join_data
# ---------------------------------------------------------------------------

class TestParseAndJoinData:
    """Tests for CSV parsing and joining logic."""

    def test_parses_correct_number_of_stations(self, parsed_stations):
        """Only stations with valid coords AND at least one price should appear."""
        # Stations 1001, 1002, 1003 are valid. 9999 has bad coords. 8888 not in registry.
        assert len(parsed_stations) == 3

    def test_station_has_expected_fields(self, parsed_stations):
        station = parsed_stations[0]
        expected_keys = {"lat", "lon", "brand", "name", "province", "region", "prices"}
        assert set(station.keys()) == expected_keys

    def test_coordinates_parsed_with_comma_to_dot(self, parsed_stations):
        """Italian CSVs use comma as decimal separator → must be converted."""
        roma = next(s for s in parsed_stations if s["name"] == "Stazione ENI Roma")
        assert roma["lat"] == pytest.approx(41.9028, abs=0.001)
        assert roma["lon"] == pytest.approx(12.4964, abs=0.001)

    def test_province_mapped_to_correct_region(self, parsed_stations):
        roma = next(s for s in parsed_stations if s["province"] == "RM")
        assert roma["region"] == "Lazio"

        milano = next(s for s in parsed_stations if s["province"] == "MI")
        assert milano["region"] == "Lombardia"

        napoli = next(s for s in parsed_stations if s["province"] == "NA")
        assert napoli["region"] == "Campania"

    def test_unknown_province_maps_to_unknown(self, service):
        """A province code not in PROVINCE_TO_REGION should map to 'Unknown'."""
        registry = """\
header
date
5555|Test|TestBrand|Stradale|TestStation|Via Test|TestCity|ZZ|45,0|9,0
"""
        prices = """\
header
date
5555|Benzina|1.800|1|11/02/2026 08:00:00
"""
        stations = service._parse_and_join_data(prices, registry)
        assert stations[0]["region"] == "Unknown"

    def test_prices_joined_correctly(self, parsed_stations):
        roma = next(s for s in parsed_stations if s["name"] == "Stazione ENI Roma")
        assert roma["prices"]["Benzina"] == pytest.approx(1.789)
        assert roma["prices"]["Gasolio"] == pytest.approx(1.649)
        assert roma["prices"]["GPL"] == pytest.approx(0.729)

    def test_station_without_matching_price_is_excluded(self, service):
        """A station in the registry but with no prices should not appear."""
        registry = """\
header
date
7777|Gestore|Brand|Stradale|No Price Station|Via X|City|RM|41,9|12,5
"""
        prices = """\
header
date
"""
        stations = service._parse_and_join_data(prices, registry)
        assert len(stations) == 0

    def test_price_for_unknown_station_is_ignored(self, parsed_stations):
        """Station 8888 is in prices but not registry → should be silently ignored."""
        ids_in_result = [s["name"] for s in parsed_stations]
        assert all("8888" not in name for name in ids_in_result)

    def test_invalid_coords_station_is_skipped(self, parsed_stations):
        """Station 9999 has 'not_a_number' as latitude → should be skipped."""
        names = [s["name"] for s in parsed_stations]
        assert "Bad Station" not in names

    def test_zero_price_is_excluded(self, service):
        """Prices with value 0 should not be added."""
        registry = """\
header
date
6001|Gestore|Brand|Stradale|Zero Price|Via X|City|RM|41,9|12,5
"""
        prices = """\
header
date
6001|Benzina|0|1|11/02/2026 08:00:00
6001|Gasolio|1.650|1|11/02/2026 08:00:00
"""
        stations = service._parse_and_join_data(prices, registry)
        assert len(stations) == 1
        assert "Benzina" not in stations[0]["prices"]
        assert "Gasolio" in stations[0]["prices"]

    def test_empty_lines_are_skipped(self, service):
        """Blank lines in the CSV should not cause errors."""
        registry = """\
header
date
6002|Gestore|Brand|Stradale|Station|Via X|City|RM|41,9|12,5

"""
        prices = """\
header
date
6002|Benzina|1.800|1|11/02/2026 08:00:00

"""
        stations = service._parse_and_join_data(prices, registry)
        assert len(stations) == 1


# ---------------------------------------------------------------------------
# Tests for _calculate_average
# ---------------------------------------------------------------------------

class TestCalculateAverage:

    def test_averages_computed_correctly(self, service, parsed_stations):
        averages = service._calculate_average(parsed_stations)

        # Benzina: (1.789 + 1.819 + 1.759) / 3 = 1.789
        assert averages["Benzina"] == pytest.approx(1.789, abs=0.001)

        # Gasolio: (1.649 + 1.679 + 1.629) / 3 = 1.6523
        assert averages["Gasolio"] == pytest.approx(1.6523, abs=0.001)

    def test_missing_fuel_type_returns_zero(self, service, parsed_stations):
        averages = service._calculate_average(parsed_stations)
        # Not all stations have all fuel types, but the result should still have the key
        assert "GPL" in averages
        assert "Metano" in averages

    def test_empty_station_list_returns_all_zeros(self, service):
        averages = service._calculate_average([])
        assert averages["Benzina"] == 0.0
        assert averages["Gasolio"] == 0.0
        assert averages["GPL"] == 0.0
        assert averages["Metano"] == 0.0

    def test_single_station_average_equals_its_price(self, service):
        stations = [{"prices": {"Benzina": 1.850, "Gasolio": 1.700}}]
        averages = service._calculate_average(stations)
        assert averages["Benzina"] == pytest.approx(1.850)
        assert averages["Gasolio"] == pytest.approx(1.700)


# ---------------------------------------------------------------------------
# Tests for _fetch_csv
# ---------------------------------------------------------------------------

class TestFetchCsv:

    @pytest.mark.asyncio
    async def test_returns_response_text_on_success(self, service):
        mock_response = MagicMock()
        mock_response.text = "csv,content,here"
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response

        result = await service._fetch_csv(mock_client, "http://example.com/data.csv")
        assert result == "csv,content,here"

    @pytest.mark.asyncio
    async def test_raises_fuel_price_error_on_http_failure(self, service):
        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.HTTPStatusError(
            "Not Found", request=MagicMock(), response=MagicMock(status_code=404)
        )

        with pytest.raises(FuelPriceError, match="Failed to fetch data"):
            await service._fetch_csv(mock_client, "http://example.com/bad.csv")

    @pytest.mark.asyncio
    async def test_raises_fuel_price_error_on_timeout(self, service):
        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.ReadTimeout("Timeout")

        with pytest.raises(FuelPriceError):
            await service._fetch_csv(mock_client, "http://example.com/slow.csv")


# ---------------------------------------------------------------------------
# Tests for get_nearby_prices
# ---------------------------------------------------------------------------

class TestGetNearbyPrices:

    @pytest.mark.asyncio
    async def test_returns_prices_for_nearby_stations(self, service):
        """Pre-load the cache with mock data, then query near Rome."""
        service._cache_data = service._parse_and_join_data(MOCK_PRICES_CSV, MOCK_REGISTRY_CSV)
        service._cache_timestamp = 9999999999  # Far future → no refresh

        # Query near Rome (41.90, 12.50) with 10km radius → should include station 1001
        result = await service.get_nearby_prices(41.90, 12.50, radius_km=10.0)

        assert result["currency"] == "EUR"
        assert result["gasoline"] > 0
        assert result["diesel"] > 0
        assert result["station_count"] >= 1
        assert "MIMIT" in result["source"]

    @pytest.mark.asyncio
    async def test_no_stations_in_range_returns_zeros(self, service):
        """Query from middle of the ocean → no stations nearby."""
        service._cache_data = service._parse_and_join_data(MOCK_PRICES_CSV, MOCK_REGISTRY_CSV)
        service._cache_timestamp = 9999999999

        result = await service.get_nearby_prices(0.0, 0.0, radius_km=1.0)

        assert result["station_count"] == 0
        assert result["gasoline"] == 0.0
        assert result["diesel"] == 0.0

    @pytest.mark.asyncio
    async def test_large_radius_includes_all_stations(self, service):
        service._cache_data = service._parse_and_join_data(MOCK_PRICES_CSV, MOCK_REGISTRY_CSV)
        service._cache_timestamp = 9999999999

        # 2000km radius from center of Italy should capture all 3 test stations
        result = await service.get_nearby_prices(42.0, 12.5, radius_km=2000.0)
        assert result["station_count"] == 3

    @pytest.mark.asyncio
    async def test_triggers_refresh_when_cache_is_empty(self, service):
        """When cache is None, get_nearby_prices should call _refresh_data."""
        assert service._cache_data is None

        with patch.object(service, "_refresh_data", new_callable=AsyncMock) as mock_refresh:
            # After refresh, set some data so the method can proceed
            async def fake_refresh():
                service._cache_data = []
                service._cache_timestamp = 9999999999

            mock_refresh.side_effect = fake_refresh

            await service.get_nearby_prices(41.9, 12.5)
            mock_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_response_includes_gpl_and_methane(self, service):
        service._cache_data = service._parse_and_join_data(MOCK_PRICES_CSV, MOCK_REGISTRY_CSV)
        service._cache_timestamp = 9999999999

        result = await service.get_nearby_prices(42.0, 12.5, radius_km=2000.0)

        assert "gpl" in result
        assert "methane" in result


# ---------------------------------------------------------------------------
# Tests for get_regional_average
# ---------------------------------------------------------------------------

class TestGetRegionalAverage:

    @pytest.mark.asyncio
    async def test_returns_average_for_region(self, service):
        service._cache_data = service._parse_and_join_data(MOCK_PRICES_CSV, MOCK_REGISTRY_CSV)
        service._cache_timestamp = 9999999999

        result = await service.get_regional_average("Lazio")

        assert result["region"] == "Lazio"
        assert result["station_count"] == 1  # Only station 1001 is in RM → Lazio
        assert result["prices"]["gasoline"] == pytest.approx(1.789)
        assert result["prices"]["diesel"] == pytest.approx(1.649)

    @pytest.mark.asyncio
    async def test_case_insensitive_region_match(self, service):
        service._cache_data = service._parse_and_join_data(MOCK_PRICES_CSV, MOCK_REGISTRY_CSV)
        service._cache_timestamp = 9999999999

        result = await service.get_regional_average("lazio")
        assert result["station_count"] == 1

    @pytest.mark.asyncio
    async def test_unknown_region_returns_zero_stations(self, service):
        service._cache_data = service._parse_and_join_data(MOCK_PRICES_CSV, MOCK_REGISTRY_CSV)
        service._cache_timestamp = 9999999999

        result = await service.get_regional_average("Atlantide")
        assert result["station_count"] == 0
        assert result["prices"]["gasoline"] == 0.0


# ---------------------------------------------------------------------------
# Tests for get_national_average
# ---------------------------------------------------------------------------

class TestGetNationalAverage:

    @pytest.mark.asyncio
    async def test_returns_average_across_all_stations(self, service):
        service._cache_data = service._parse_and_join_data(MOCK_PRICES_CSV, MOCK_REGISTRY_CSV)
        service._cache_timestamp = 9999999999

        result = await service.get_national_average()

        assert result["country"] == "Italy"
        assert result["station_count"] == 3
        assert result["prices"]["gasoline"] > 0
        assert result["prices"]["diesel"] > 0

    @pytest.mark.asyncio
    async def test_national_average_values_are_correct(self, service):
        service._cache_data = service._parse_and_join_data(MOCK_PRICES_CSV, MOCK_REGISTRY_CSV)
        service._cache_timestamp = 9999999999

        result = await service.get_national_average()

        # Benzina average: (1.789 + 1.819 + 1.759) / 3
        expected_benzina = round((1.789 + 1.819 + 1.759) / 3, 3)
        assert result["prices"]["gasoline"] == pytest.approx(expected_benzina, abs=0.001)


# ---------------------------------------------------------------------------
# Tests for PROVINCE_TO_REGION mapping
# ---------------------------------------------------------------------------

class TestProvinceMapping:

    def test_all_major_provinces_are_mapped(self):
        """Spot-check some key province codes."""
        assert PROVINCE_TO_REGION["RM"] == "Lazio"
        assert PROVINCE_TO_REGION["MI"] == "Lombardia"
        assert PROVINCE_TO_REGION["NA"] == "Campania"
        assert PROVINCE_TO_REGION["TO"] == "Piemonte"
        assert PROVINCE_TO_REGION["PA"] == "Sicilia"
        assert PROVINCE_TO_REGION["FI"] == "Toscana"
        assert PROVINCE_TO_REGION["BO"] == "Emilia-Romagna"
        assert PROVINCE_TO_REGION["BA"] == "Puglia"

    def test_mapping_has_no_empty_values(self):
        for code, region in PROVINCE_TO_REGION.items():
            assert region, f"Province '{code}' maps to an empty region"
