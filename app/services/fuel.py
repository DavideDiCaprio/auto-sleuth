import httpx
import time
import asyncio
import math
from typing import Dict, Any, Optional, List, Tuple
from collections import defaultdict

PROVINCE_TO_REGION = {
    'AG': 'Sicilia', 'AL': 'Piemonte', 'AN': 'Marche', 'AO': 'Valle d\'Aosta', 'AQ': 'Abruzzo', 'AR': 'Toscana', 'AP': 'Marche', 'AT': 'Piemonte', 'AV': 'Campania',
    'BA': 'Puglia', 'BT': 'Puglia', 'BL': 'Veneto', 'BN': 'Campania', 'BG': 'Lombardia', 'BI': 'Piemonte', 'BO': 'Emilia-Romagna', 'BZ': 'Trentino-Alto Adige', 'BS': 'Lombardia', 'BR': 'Puglia',
    'CA': 'Sardegna', 'CL': 'Sicilia', 'CB': 'Molise', 'CI': 'Sardegna', 'CE': 'Campania', 'CT': 'Sicilia', 'CZ': 'Calabria', 'CH': 'Abruzzo', 'CO': 'Lombardia', 'CS': 'Calabria', 'CR': 'Lombardia', 'KR': 'Calabria', 'CN': 'Piemonte',
    'EN': 'Sicilia', 'FM': 'Marche', 'FE': 'Emilia-Romagna', 'FI': 'Toscana', 'FG': 'Puglia', 'FC': 'Emilia-Romagna', 'FR': 'Lazio', 'GE': 'Liguria', 'GO': 'Friuli-Venezia Giulia', 'GR': 'Toscana',
    'IM': 'Liguria', 'IS': 'Molise', 'SP': 'Liguria', 'LT': 'Lazio', 'LE': 'Puglia', 'LC': 'Lombardia', 'LI': 'Toscana', 'LO': 'Lombardia', 'LU': 'Lombardia', 
    'MC': 'Marche', 'MN': 'Lombardia', 'MS': 'Toscana', 'MT': 'Basilicata', 'VS': 'Sardegna', 'ME': 'Sicilia', 'MI': 'Lombardia', 'MO': 'Emilia-Romagna', 'MB': 'Lombardia', 'NA': 'Campania', 'NO': 'Piemonte', 'NU': 'Sardegna', 'OG': 'Sardegna',
    'OT': 'Sardegna', 'OR': 'Sardegna', 'PD': 'Veneto', 'PA': 'Sicilia', 'PR': 'Emilia-Romagna', 'PV': 'Lombardia', 'PG': 'Umbria', 'PU': 'Marche', 'PE': 'Abruzzo', 'PC': 'Emilia-Romagna', 'PI': 'Toscana', 'PT': 'Toscana', 'PN': 'Friuli-Venezia Giulia', 'PZ': 'Basilicata', 'PO': 'Toscana',
    'RG': 'Sicilia', 'RA': 'Emilia-Romagna', 'RC': 'Calabria', 'RE': 'Emilia-Romagna', 'RI': 'Lazio', 'RN': 'Emilia-Romagna', 'RM': 'Lazio', 'RO': 'Veneto', 'SA': 'Campania', 'SS': 'Sardegna', 'SV': 'Liguria', 'SI': 'Toscana', 'SR': 'Sicilia', 'SO': 'Lombardia',
    'TA': 'Puglia', 'TE': 'Abruzzo', 'TR': 'Umbria', 'TO': 'Piemonte', 'TP': 'Sicilia', 'TN': 'Trentino-Alto Adige', 'TV': 'Veneto', 'TS': 'Friuli-Venezia Giulia', 'UD': 'Friuli-Venezia Giulia', 'VA': 'Lombardia', 'VE': 'Veneto', 'VB': 'Piemonte', 'VC': 'Piemonte', 'VR': 'Veneto', 'VV': 'Calabria', 'VI': 'Veneto', 'VT': 'Lazio'
}

class FuelPriceError(Exception):
    pass

class MimitFuelPriceService:
    def __init__(self):
        self.prices_url = "https://www.mimit.gov.it/images/exportCSV/prezzo_alle_8.csv"
        self.registry_url = "https://www.mimit.gov.it/images/exportCSV/anagrafica_impianti_attivi.csv"
        
        self._cache_data: Optional[Dict[str, Any]] = None # Holds the JOINED data
        self._cache_timestamp: float = 0
        self._cache_duration = 3600  # 1 Hour
        self._lock = asyncio.Lock()

    async def _fetch_csv(self, client: httpx.AsyncClient, url: str) -> str:
        try:
            response = await client.get(url, timeout=60.0) # increased timeout for big files
            response.raise_for_status()
            return response.text
        except httpx.HTTPError as e:
            raise FuelPriceError(f"Failed to fetch data from {url}: {e}")

    def _parse_and_join_data(self, prices_content: str, registry_content: str) -> List[Dict[str, Any]]:
        """
        Parses and joins data from two MIMIT (Italian Ministry of Enterprises and Made in Italy) Open Data CSV files:
        
        1. Registry File (anagrafica_impianti_attivi.csv):
           - Contains metadata for all active gas stations.
           - Key fields used: 
             * idImpianto (Unique Station ID)
             * Bandiera (Brand)
             * Indirizzo, Comune, Provincia (Location details)
             * Latitudine, Longitudine (Geolocation)
        
        2. Price File (prezzo_alle_8.csv):
           - Contains the latest prices updated by 8:00 AM.
           - Linked to Registry via 'idImpianto'.
           - Key fields used:
             * idImpianto (Foreign Key)
             * descCarburante (Fuel Type: Benzina, Gasolio, GPL, Metano)
             * prezzo (Price value)
             
        Logic:
        - We first build a dictionary of stations from the Registry file, indexed by 'idImpianto'.
        - We then iterate through the Price file. If a price entry matches a known station ID, we add that price to the station's record.
        - Finally, we return a list of only those stations that have valid price data.
        
        This approach efficiently joins the static station data with dynamic price data in O(N+M) time.
        """
        # 1. Parse Registry (Location Data)
        # Format: idImpianto|Gestore|Bandiera|Tipo Impianto|Nome Impianto|Indirizzo|Comune|Provincia|Latitudine|Longitudine
        stations = {}
        registry_lines = registry_content.splitlines()[2:] # Skip header + extraction date
        
        for line in registry_lines:
            if not line.strip(): continue
            parts = line.split('|')
            if len(parts) >= 10:
                try:
                    p_id = parts[0].strip()
                    lat = float(parts[8].replace(',', '.'))
                    lon = float(parts[9].replace(',', '.'))
                    prov = parts[7].strip()
                    region = PROVINCE_TO_REGION.get(prov, 'Unknown')
                    
                    stations[p_id] = {
                        'lat': lat,
                        'lon': lon,
                        'brand': parts[2].strip(),
                        'name': parts[4].strip(),
                        'province': prov,
                        'region': region,
                        'prices': {} # To be filled
                    }
                except ValueError:
                    continue # Skip invalid coords
        
        # 2. Parse Prices
        # Format: idImpianto|descCarburante|prezzo|isSelf|dtComu
        price_lines = prices_content.splitlines()[2:]
        for line in price_lines:
            if not line.strip(): continue
            parts = line.split('|')
            if len(parts) >= 3:
                p_id = parts[0].strip()
                if p_id in stations:
                    fuel_type = parts[1].strip()
                    try:
                        price = float(parts[2].strip())
                        # We only care about the latest price, simple overwrite or keep list? 
                        # Simplifying: just take the price. MIMIT might have self/served. 
                        # Let's clean fuel names to match our schema standard
                        # Standardize keys: Gasoline -> gasoline, etc.
                        # Actually MIMIT uses 'Benzina', 'Gasolio', etc.
                        
                        # Only add if price > 0
                        if price > 0:
                            stations[p_id]['prices'][fuel_type] = price
                    except ValueError:
                        continue

        # 3. Filter out stations with no prices and return list
        return [s for s in stations.values() if s['prices']]
    
    def _calculate_average(self, stations: List[Dict[str, Any]]) -> Dict[str, float]:
        """Helper to calculate average prices from a list of stations."""
        totals = defaultdict(float)
        counts = defaultdict(int)
        
        for s in stations:
            for fuel, price in s['prices'].items():
                totals[fuel] += price
                counts[fuel] += 1
                
        results = {}
        for fuel in ['Benzina', 'Gasolio', 'GPL', 'Metano']:
            if counts[fuel] > 0:
                results[fuel] = round(totals[fuel] / counts[fuel], 3)
            else:
                results[fuel] = 0.0
        return results

    async def _refresh_data(self):
        """
        Fetches both files and updates the cache.
        """
        print("Refreshing MIMIT data (Registry + Prices)...")
        async with httpx.AsyncClient() as client:
            # Fetch in parallel
            r_prices, r_registry = await asyncio.gather(
                self._fetch_csv(client, self.prices_url),
                self._fetch_csv(client, self.registry_url)
            )
            
        loop = asyncio.get_running_loop()
        # CPU-bound parsing
        self._cache_data = await loop.run_in_executor(None, self._parse_and_join_data, r_prices, r_registry)
        self._cache_timestamp = time.time()
        print(f"Data refreshed. Loaded {len(self._cache_data)} stations.")

    async def get_nearby_prices(self, lat: float, lon: float, radius_km: float = 20.0) -> Dict[str, Any]:
        """
        Finds stations within radius_km and calculates the average price.
        """
        # check cache
        if not self._cache_data or (time.time() - self._cache_timestamp > self._cache_duration):
             async with self._lock:
                 # double check
                 if not self._cache_data or (time.time() - self._cache_timestamp > self._cache_duration):
                     await self._refresh_data()
        
        # Filter by distance (Simple Haversine or simple Euclidean for speed if small area? Haversine is safer)
        # Optimization: pre-filter by bounding box to avoid heavy math on all 20k stations? 
        # For ~20k items, simple iteration is essentially instant in Python (ms).
        
        nearby_stations = []
        
        count = 0
        
        for station in self._cache_data:
            # Simple Haversine approximation
            # deg to rad
            lat1, lon1 = math.radians(lat), math.radians(lon)
            lat2, lon2 = math.radians(station['lat']), math.radians(station['lon'])
            
            dlat = lat2 - lat1
            dlon = lon2 - lon1
            
            # a = sin^2(dlat/2) + cos(lat1) * cos(lat2) * sin^2(dlon/2)
            a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
            R = 6371.0 # Earth radius
            
            dist = R * c
            
            if dist <= radius_km:
                count += 1
                nearby_stations.append(station)

        # Calculate averages
        results = self._calculate_average(nearby_stations)

        return {
            "currency": "EUR",
            "gasoline": results.get('Benzina', 0.0),
            "diesel": results.get('Gasolio', 0.0),
            "gpl": results.get('GPL', 0.0),
            "methane": results.get('Metano', 0.0),
            "source": f"MIMIT Open Data (Avg of {count} stations within {radius_km}km)",
            "station_count": count
        }
    
    async def get_regional_average(self, region_name: str) -> Dict[str, Any]:
        """Returns average prices for the specified region."""
        # Ensure data is loaded
        if not self._cache_data:
             await self.get_nearby_prices(0, 0) # Trigger load if needed (hacky but works due to shared lock)
             
        stations_in_region = [s for s in self._cache_data if s.get('region', '').lower() == region_name.lower()]
        
        results = self._calculate_average(stations_in_region)
        return {
            "region": region_name,
            "prices": {
                 "gasoline": results.get('Benzina', 0.0),
                 "diesel": results.get('Gasolio', 0.0),
                 "gpl": results.get('GPL', 0.0),
                 "methane": results.get('Metano', 0.0),
            },
            "station_count": len(stations_in_region)
        }

    async def get_national_average(self) -> Dict[str, Any]:
        """Returns average prices for the entire country."""
        # Ensure data is loaded
        if not self._cache_data:
             await self.get_nearby_prices(0, 0) # Trigger load
             
        results = self._calculate_average(self._cache_data)
        return {
            "country": "Italy",
            "prices": {
                 "gasoline": results.get('Benzina', 0.0),
                 "diesel": results.get('Gasolio', 0.0),
                 "gpl": results.get('GPL', 0.0),
                 "methane": results.get('Metano', 0.0),
            },
            "station_count": len(self._cache_data)
        }

# --- SINGLETON PATTERN ---
_service_instance = MimitFuelPriceService()

def get_fuel_price_service() -> MimitFuelPriceService:
    return _service_instance