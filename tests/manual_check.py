import asyncio
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from app.services.geolocation import get_user_location
from app.services.fuel import MimitFuelPriceService

async def test_geolocation():
    print("--- Testing Geolocation ---")
    try:
        # Test with a known Italian IP (e.g., Google Italy or a random ISP IP)
        # Using 8.8.8.8 often maps to US, lets try a generic one or just rely on local
        # actually 151.100.0.0 is often Italy (GARR)
        ip = "151.100.0.0" 
        loc = await get_user_location(ip)
        print(f"IP {ip} -> {loc['city']}, {loc['regionName']} ({loc['countryCode']})")
        assert loc['countryCode'] == 'IT'
    except Exception as e:
        print(f"Geolocation failed: {e}")

async def test_fuel_price_service():
    print("\n--- Testing Fuel Price Service ---")
    service = MimitFuelPriceService()
    
    # Force load (this triggers the fetch)
    print("Fetching data (this might take a moment)...")
    try:
        # Rome Coordinates
        lat, lon = 41.9028, 12.4964
        prices = await service.get_nearby_prices(lat, lon)
        print(f"Prices near Rome: {prices}")
        assert prices['gasoline'] > 0
        
        # Test Regional
        print("\nTesting Regional (Lazio)...")
        regional = await service.get_regional_average("Lazio")
        print(f"Lazio: {regional}")
        assert regional['prices']['gasoline'] > 0
        
        # Test National
        print("\nTesting National...")
        national = await service.get_national_average()
        print(f"National: {national}")
        assert national['prices']['gasoline'] > 0
        
    except Exception as e:
        print(f"Fuel Price Service failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_geolocation())
    asyncio.run(test_fuel_price_service())
