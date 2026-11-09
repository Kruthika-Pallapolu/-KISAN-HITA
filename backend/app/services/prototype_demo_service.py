"""Deterministic, visibly synthetic data used for the Kisan Hita prototype demo.

No network access, geocoding, or live agricultural observation is used here.
Location validation still uses the shared Indian LGD directory via WeatherService.
"""

from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta, timezone

from ..models.schemas import ForecastDay, WeatherData


def _stable_number(key: str, low: int, high: int) -> int:
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    return low + int.from_bytes(digest[:4], "big") % (high - low + 1)


def _location(district: str, state: str) -> tuple[str, str]:
    # Import lazily to avoid a module cycle; this is the same canonical validator
    # used by the live weather path and checks district membership in its state.
    from .weather_service import WeatherService

    selected_state, selected_district = WeatherService._canonical_location(district, state)
    return selected_state["name"], selected_district["name"]


def weather(district: str, state: str, language: str):
    from .weather_service import get_localized_weather_advice, get_wmo_condition

    canonical_state, canonical_district = _location(district, state)
    today = date.today()
    key = f"{canonical_state}|{canonical_district}|{today.isoformat()}"
    # Broad seasonal ranges keep values plausible across India's climate zones,
    # while the stable key ensures a district/date does not flicker on rerender.
    month = today.month
    seasonal_base = 27 if month in (11, 12, 1, 2) else 31 if month in (3, 4, 5, 6) else 28
    temperature = _stable_number(key + "|temp", seasonal_base - 4, seasonal_base + 4)
    humidity = _stable_number(key + "|humidity", 48, 88)
    wind_speed = _stable_number(key + "|wind", 4, 19)
    rain_probability = _stable_number(key + "|rain", 5, 80)
    rainfall = round((rain_probability / 100) * _stable_number(key + "|rainfall", 0, 18), 1)
    condition_code = 61 if rain_probability >= 65 else 3 if rain_probability >= 42 else 2 if rain_probability >= 20 else 1
    condition = get_wmo_condition(condition_code)
    irrigation, advisory, _, produce = get_localized_weather_advice(rain_probability, wind_speed, language)
    localized_spray = {
        "en": "Illustrative demo only: check local hourly weather and the product label before spraying.",
        "te": "డెమో సమాచారం మాత్రమే: పిచికారీకి ముందు స్థానిక గంటవారీ వాతావరణం, ఉత్పత్తి లేబుల్‌ను తనిఖీ చేయండి.",
        "hi": "केवल डेमो: छिड़काव से पहले स्थानीय घंटेवार मौसम और उत्पाद का लेबल जाँचें।",
        "ta": "டெமோ தகவல் மட்டும்: தெளிப்பதற்கு முன் உள்ளூர் மணிநேர வானிலை மற்றும் தயாரிப்பு லேபிளைச் சரிபார்க்கவும்.",
        "kn": "ಡೆಮೋ ಮಾಹಿತಿ ಮಾತ್ರ: ಸಿಂಪಡಿಸುವ ಮೊದಲು ಸ್ಥಳೀಯ ಗಂಟೆಗಂಟೆಯ ಹವಾಮಾನ ಮತ್ತು ಉತ್ಪನ್ನದ ಲೇಬಲ್ ಪರಿಶೀಲಿಸಿ.",
        "ml": "ഡെമോ വിവരം മാത്രം: തളിക്കുന്നതിന് മുമ്പ് പ്രാദേശിക മണിക്കൂർ കാലാവസ്ഥയും ഉൽപ്പന്ന ലേബലും പരിശോധിക്കുക.",
        "mr": "फक्त डेमो: फवारणीपूर्वी स्थानिक तासानुसार हवामान आणि उत्पादनाचे लेबल तपासा.",
    }
    forecast = []
    for offset in range(7):
        forecast_date = today + timedelta(days=offset)
        day_key = f"{key}|day|{offset}"
        max_temp = temperature + _stable_number(day_key + "|max", 0, 4)
        min_temp = temperature - _stable_number(day_key + "|min", 4, 9)
        probability = _stable_number(day_key + "|rain", 0, 85)
        code = 61 if probability >= 65 else 3 if probability >= 42 else 2 if probability >= 20 else 1
        forecast.append(ForecastDay(
            day_name="Today" if offset == 0 else forecast_date.strftime("%a"),
            date=forecast_date.isoformat(), temp_max=float(max_temp), temp_min=float(min_temp),
            condition=get_wmo_condition(code), precipitation_probability=probability,
            icon="cloud-rain" if probability >= 55 else "cloud-sun",
        ))
    return WeatherData(
        district=canonical_district, state=canonical_state, temperature=float(temperature),
        feels_like=float(temperature + (2 if humidity >= 70 else 1)), condition=condition,
        humidity=humidity, wind_speed=float(wind_speed), rain_probability=rain_probability,
        rainfall_mm=rainfall, advisory=advisory, irrigation_advice=irrigation,
        spray_suitability=localized_spray.get(language[:2], localized_spray["en"]),
        produce_protection=produce, is_official_alert=False,
        source="DEMO DATA — deterministic illustrative values; not observed weather or a live forecast.",
        coordinate_source="Shared district directory validation; no coordinates or geocoding used.",
        retrieval_timestamp=datetime.now(timezone.utc).isoformat(), forecast=forecast,
    )
