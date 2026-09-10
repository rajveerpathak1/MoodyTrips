import os
import time
import secrets
import hashlib
import hmac
import re
from datetime import datetime, timedelta
import requests
from dotenv import load_dotenv

load_dotenv()

API_BASE_URL = "https://railkit-api.rajivdubey.dev"
SIGNING_SECRET = "97c56e08b27b161124f88acd4f24d1bd50f48075f11dc23b9ea6c0bc9b2f8794"
RAILKIT_API_KEY = os.getenv("RAILKIT_API_KEY")

# Mapping of major Indian city names to primary Indian Railway station codes
CITY_STATION_CODES = {
    "delhi": "NDLS",
    "new delhi": "NDLS",
    "noida": "NDLS",
    "gurgaon": "NDLS",
    "mumbai": "MMCT",
    "bombay": "MMCT",
    "thane": "MMCT",
    "kolkata": "HWH",
    "calcutta": "HWH",
    "howrah": "HWH",
    "chennai": "MAS",
    "madras": "MAS",
    "bangalore": "SBC",
    "bengaluru": "SBC",
    "hyderabad": "SC",
    "secunderabad": "SC",
    "pune": "PUNE",
    "jaipur": "JP",
    "agra": "AGC",
    "ahmedabad": "ADI",
    "goa": "MAO",
    "madgaon": "MAO",
    "varanasi": "BSB",
    "amritsar": "ASR",
    "patna": "PNBE",
    "lucknow": "LKO",
    "chandigarh": "CDG",
    "dehradun": "DDN",
    "haridwar": "HW",
    "udaipur": "UDZ",
    "jodhpur": "JU",
    "shimla": "SML"
}

def get_station_code(city_name: str) -> str | None:
    """
    Returns the Indian Railway station code for a given city name.
    """
    if not city_name:
        return None
    cleaned = city_name.strip().lower()
    
    # Check exact match
    if cleaned in CITY_STATION_CODES:
        return CITY_STATION_CODES[cleaned]
        
    # Check partial match
    for city, code in CITY_STATION_CODES.items():
        if city in cleaned or cleaned in city:
            return code
            
    return None

def parse_date_to_dd_mm_yyyy(date_str: str) -> str | None:
    """
    Utility to parse typical date strings to DD-MM-YYYY format required by Railkit.
    """
    if not date_str:
        return None
    
    # Strip ordinals like 15th -> 15
    cleaned_date = re.sub(r"(\d+)(st|nd|rd|th)", r"\1", date_str, flags=re.IGNORECASE)
    normalized = re.sub(r"[-/\s.]+", "-", cleaned_date.strip())
    
    # 1. Check DD-MM-YYYY
    match1 = re.match(r"^(\d{1,2})-(\d{1,2})-(\d{4})$", normalized)
    if match1:
        day, month, year = match1.groups()
        return f"{int(day):02d}-{int(month):02d}-{year}"
        
    # 2. Check YYYY-MM-DD
    match2 = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})$", normalized)
    if match2:
        year, month, day = match2.groups()
        return f"{int(day):02d}-{int(month):02d}-{year}"
        
    # 3. Try parsing text dates like "15-Aug-2026"
    for fmt in ("%d-%b-%Y", "%d-%B-%Y", "%d-%b", "%d-%B", "%B-%d-%Y", "%b-%d-%Y"):
        try:
            dt = datetime.strptime(normalized, fmt)
            if dt.year == 1900:
                dt = dt.replace(year=datetime.now().year)
            return dt.strftime("%d-%m-%Y")
        except ValueError:
            continue
            
    return None

def make_railkit_request(path: str) -> dict:
    """
    Internal helper to construct HMAC headers and execute requests to Railkit API.
    """
    if not RAILKIT_API_KEY:
        return {"success": False, "error": "RAILKIT_API_KEY is not configured in .env file."}
        
    method = "GET"
    timestamp = str(int(time.time() * 1000))
    nonce = secrets.token_hex(32)
    payload_hash = hashlib.sha256(b"").hexdigest()
    
    # Extract only the base path to sign (exclude query parameters)
    sign_path = path.split("?")[0]
    
    # String to sign: METHOD\nPATH\nTIMESTAMP\nNONCE\nPAYLOAD_HASH\nAPI_KEY
    string_to_sign = f"{method.upper()}\n{sign_path}\n{timestamp}\n{nonce}\n{payload_hash}\n{RAILKIT_API_KEY}"
    
    sig = hmac.new(
        SIGNING_SECRET.encode("utf-8"),
        string_to_sign.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    
    headers = {
        "x-api-key": RAILKIT_API_KEY,
        "Accept": "application/json",
        "x-irctc-sdk-ts": timestamp,
        "x-irctc-sdk-nonce": nonce,
        "x-irctc-sdk-payload-sha256": payload_hash,
        "x-irctc-sdk-signature": sig,
        "x-irctc-sdk-version": "1"
    }
    
    url = f"{API_BASE_URL}{path}"
    try:
        response = requests.get(url, headers=headers, timeout=12)
        return response.json()
    except Exception as e:
        return {"success": False, "error": f"HTTP request failed: {str(e)}"}

def search_trains_between_stations(from_station: str, to_station: str, date_str: str | None = None) -> dict:
    """
    Find direct trains between two station codes or city names.
    """
    from_code = get_station_code(from_station) or from_station.upper()
    to_code = get_station_code(to_station) or to_station.upper()
    
    formatted_date = parse_date_to_dd_mm_yyyy(date_str)
    
    path = f"/api/searchTrainBetweenStations/{from_code}/{to_code}"
    if formatted_date:
        path += f"?date={formatted_date}"
        
    res = make_railkit_request(path)
    if res.get("success") and "data" in res:
        return {
            "success": True,
            "from_code": from_code,
            "to_code": to_code,
            "date": formatted_date or "any",
            "trains": res["data"]
        }
    return {
        "success": False,
        "error": res.get("error", "Failed to retrieve train schedule.")
    }

def get_seat_availability(train_no: str, from_code: str, to_code: str, date_str: str, travel_class: str = "3A", quota: str = "GN") -> dict:
    """
    Check seat availability and ticket pricing for a specific train and travel class.
    """
    formatted_date = parse_date_to_dd_mm_yyyy(date_str)
    if not formatted_date:
        # Default to 3 days from now if date is invalid/not provided
        formatted_date = (datetime.now() + timedelta(days=3)).strftime("%d-%m-%Y")
        
    path = f"/api/getAvailability/{train_no}/{from_code}/{to_code}/{formatted_date}/{travel_class}/{quota}"
    res = make_railkit_request(path)
    
    if res.get("success") and "data" in res:
        return {
            "success": True,
            "data": res["data"]
        }
    return {
        "success": False,
        "error": res.get("error", "Failed to check seat availability.")
    }
