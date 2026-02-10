import requests
from typing import Dict, Protocol, Optional, Any

class GeolocationError(Exception):
    pass

def get_user_location(ip_address: str) -> Dict[str, str]:
    """
    Get the user's location in ITALIAN based on IP.
    """
    try:
        # Added 'lang=it' to get "Lombardia" instead of "Lombardy"
        base_url = "http://ip-api.com/json/"
        target = f"{base_url}{ip_address}" if ip_address and ip_address != "127.0.0.1" else base_url
        
        # Pass lang='it' as a query parameter
        response = requests.get(target, params={"lang": "it"}, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        if data.get("status") == "fail":
            raise GeolocationError(f"Geolocation failed: {data.get('message')}")

        return {
            "city": data.get("city", "Sconosciuto"),
            "region": data.get("region", ""),         # e.g., 'LZ'
            "regionName": data.get("regionName", ""), # e.g., 'Lazio' (Now in Italian!)
            "country": data.get("country", ""),       # e.g., 'Italia'
            "countryCode": data.get("countryCode", ""), # e.g., 'IT'
            "lat": str(data.get("lat", "0")),
            "lon": str(data.get("lon", "0"))
        }

    except Exception as e:
        # Log error in production
        raise GeolocationError(f"Geo Error: {e}")