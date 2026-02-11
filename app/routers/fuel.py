from fastapi import APIRouter, Request, HTTPException
from app.services.geolocation import get_user_location, GeolocationError, get_client_ip
from app.services.fuel import get_fuel_price_service, FuelPriceError

router = APIRouter()

@router.get("/fuel-price")
async def get_fuel_price_endpoint(request: Request):
    """
    Get the current fuel price based on the user's location.
    Attempts to determine location from IP address.
    Returns:
        JSON object with location and fuel price data.
    Raises:
        HTTPException(503): If geolocation or fuel price service is unavailable.
    """
    # 1. Get User IP
    client_host = get_client_ip(request)
        
    try:
        # 2. Get Location
        location = await get_user_location(client_host)
        
        # Check if user is from Italy
        if location.get("countryCode") != "IT":
             raise HTTPException(
                status_code=403, 
                detail=f"Your country is not currently aviable for this app. Current location: {location.get('country', 'Unknown')}"
            )
            
        region_code = location.get("region")
    except GeolocationError as e:
        raise HTTPException(status_code=503, detail=f"Geolocation service unavailable: {str(e)}")
    
    try:
        # 3. Get Gas Price
        service = get_fuel_price_service()
        
        # Parse lat/lon
        lat = float(location.get("lat", 0))
        lon = float(location.get("lon", 0))
        
        nearby_data = await service.get_nearby_prices(lat, lon)
        
        # Get Regional & National
        regional_data = None
        region_name = location.get("regionName")
        if region_name:
             regional_data = await service.get_regional_average(region_name)
             
        national_data = await service.get_national_average()
    except FuelPriceError as e:
        raise HTTPException(status_code=503, detail=f"Fuel price service unavailable: {str(e)}")
    
    
    return { 
        "location": location, 
        "fuel_price": nearby_data,
        "price_data": {
            "nearby": nearby_data,
            "regional": regional_data,
            "national": national_data
        }
    }