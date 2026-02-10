import requests

def check_url(url):
    try:
        response = requests.head(url, timeout=5)
        print(f"URL: {url} - Status: {response.status_code}")
    except Exception as e:
        print(f"URL: {url} - Error: {e}")

def check_ip_api():
    try:
        response = requests.get("http://ip-api.com/json/?fields=status,message,country,countryCode,region,regionName,city,lat,lon", timeout=5)
        print(f"IP-API Response: {response.json()}")
    except Exception as e:
        print(f"IP-API Error: {e}")

print("Checking MIMIT URLs...")
check_url("https://www.mimit.gov.it/images/export/prezzo_alle_8.csv")
check_url("https://www.mimit.gov.it/images/export/anagrafica_impianti_attivi.csv")
check_url("https://www.mise.gov.it/images/export/prezzo_alle_8.csv")

print("\nChecking IP-API...")
check_ip_api()
