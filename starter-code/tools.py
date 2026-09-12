import json
import os
from typing import Any, Dict, List

RAW_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "raw-data")


def get_flight_info(
    origin: str,
    destination: str,
    max_price: int = 5_000_000,
) -> List[Dict[str, Any]]:
    """
    Tìm chuyến bay theo điểm đi, điểm đến và mức giá tối đa.
    """
    flight_file = os.path.join(RAW_DATA_DIR, "flight_data.json")

    if not os.path.exists(flight_file):
        return []

    if not isinstance(origin, str) or not isinstance(destination, str):
        return []

    try:
        max_price = int(max_price)
    except (TypeError, ValueError):
        return []

    try:
        with open(flight_file, "r", encoding="utf-8") as file:
            flights = json.load(file)
    except (OSError, json.JSONDecodeError):
        return []

    return [
        flight
        for flight in flights
        if flight.get("origin", "").upper() == origin.strip().upper()
        and flight.get("destination", "").upper() == destination.strip().upper()
        and flight.get("price_vnd", 0) <= max_price
    ]


def get_weather_forecast(city_code: str) -> Dict[str, Any]:
    """
    Lấy thông tin thời tiết và gợi ý trang phục theo mã thành phố/sân bay.
    Ví dụ: SGN, HAN, DAD.
    """
    weather_file = os.path.join(RAW_DATA_DIR, "weather_data.json")

    if not os.path.exists(weather_file):
        return {"error": "Weather data not found"}

    if not isinstance(city_code, str):
        return {"error": "Invalid city code"}

    try:
        with open(weather_file, "r", encoding="utf-8") as file:
            weather_data = json.load(file)
    except (OSError, json.JSONDecodeError):
        return {"error": "Weather data could not be loaded"}

    normalized_city_code = city_code.strip().upper()

    return weather_data.get(
        normalized_city_code,
        {"error": f"No data for {normalized_city_code}"},
    )


TOOL_DEFINITIONS = [
    {
        "name": "get_flight_info",
        "description": "Tìm chuyến bay theo điểm đi, điểm đến và giá tối đa.",
        "parameters": {
            "origin": "Mã sân bay đi (VD: HAN)",
            "destination": "Mã sân bay đến (VD: SGN)",
            "max_price": "Giá vé tối đa dạng số nguyên (VND)",
        },
    },
    {
        "name": "get_weather_forecast",
        "description": (
            "Lấy thông tin thời tiết và gợi ý trang phục theo mã sân bay/"
            "thành phố (SGN, HAN, DAD)."
        ),
        "parameters": {
            "city_code": "Mã sân bay thành phố (VD: SGN)",
        },
    },
]


TOOL_MAP = {
    "get_flight_info": get_flight_info,
    "get_weather_forecast": get_weather_forecast,
}