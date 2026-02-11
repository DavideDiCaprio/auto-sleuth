import httpx
from fastapi import Request
from typing import Dict, Protocol, Optional, Any

class GeolocationError(Exception):
    pass

def get_client_ip(request: Request) -> str:
    """
    Extracts the client's IP address from the request headers or fallback.
    """
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host

async def get_user_location(ip_address: str) -> Dict[str, str]:
    """
    Get the user's location in ITALIAN based on IP.
    """
    try:
        # Added 'lang=it' to get "Lombardia" instead of "Lombardy"
        base_url = "http://ip-api.com/json/"
        target = f"{base_url}{ip_address}" if ip_address and ip_address != "127.0.0.1" else base_url
        
        # Pass lang='it' as a query parameter
        async with httpx.AsyncClient() as client:
            response = await client.get(target, params={"lang": "it"}, timeout=5.0)
            
        response.raise_for_status()
        data = response.json()
        
        if data.get("status") == "fail":
            raise GeolocationError(f"Geolocation failed: {data.get('message')}")

        return {
            "city": data.get("city", "Sconosciuto"),
            "region": data.get("region", ""),         # e.g., 'LZ'
            "regionName": data.get("regionName", ""), # e.g., 'Lazio'
            "country": data.get("country", ""),       # e.g., 'Italia'
            "countryCode": data.get("countryCode", ""), # e.g., 'IT'
            "lat": str(data.get("lat", "0")),
            "lon": str(data.get("lon", "0"))
        }

    except Exception as e:
        # Log error in production
        raise GeolocationError(f"Geo Error: {e}")