import httpx
import json
import logging
import math
import threading
import time
import unicodedata
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional
from urllib.parse import urlparse
from ..config import settings
from ..models.schemas import WeatherData, ForecastDay

logger = logging.getLogger("weather_service")
WEATHERAPI_BASE_URL = "https://api.weatherapi.com/v1"

_GEO_DIRECTORY_PATH = Path(__file__).resolve().parents[3] / "frontend" / "src" / "data" / "indiaAdminLgd.json"
with _GEO_DIRECTORY_PATH.open(encoding="utf-8") as _geo_file:
    _GEO_DIRECTORY = json.load(_geo_file)
_STATES = _GEO_DIRECTORY["states"]
_DISTRICTS = _GEO_DIRECTORY["districts"]


class WeatherCoverageUnavailable(RuntimeError):
    """Valid directory location, but no verifiable administrative coordinates."""


class WeatherGeocodingUnavailable(RuntimeError):
    """Geocoding service/network could not verify coordinates."""


class WeatherProviderUnavailable(RuntimeError):
    """WeatherAPI.com could not provide a usable forecast."""


class WeatherConfigurationMissing(WeatherProviderUnavailable):
    """Required backend-only WeatherAPI configuration is absent."""


class WeatherLocationNotFound(RuntimeError):
    """WeatherAPI search did not find the requested location."""


class WeatherLocationAmbiguous(RuntimeError):
    """WeatherAPI search returned multiple plausible locations."""


def get_localized_weather_advice(rain_prob: int, wind_speed: float, language: str) -> tuple[str, str, str, str]:
    lang = language[:2].lower()

    if lang == "te":
        if rain_prob > 50:
            irrigation = "వర్షం పడే అవకాశం ఉంది (50% కంటే ఎక్కువ). నీరు నిల్వ ఉండకుండా నీటిపారుదలని తాత్కాలికంగా ఆపండి."
            adv = "భారీ వర్ష సూచన ఉంది. పొలాల్లో మురుగు నీటి కాలువలను శుభ్రం చేసుకోండి."
        elif rain_prob > 30:
            irrigation = "తుంపర జల్లులు పడే అవకాశం ఉంది. నేల పైభాగం పొడిగా ఉంటేనే తక్కువ నీరు పెట్టండి."
            adv = "పాక్షికంగా మేఘావృతమైన వాతావరణం. అడపాదడపా వర్షం పడవచ్చు."
        else:
            irrigation = "పొడి వాతావరణం ఉంటుంది. పంట దశకు తగినట్లు సాధారణ నీటిపారుదల కొనసాగించండి."
            adv = "సాధారణ వ్యవసాయ వాతావరణం. పొలం పనులకు అనుకూల సమయం."

        if wind_speed < 15:
            spray = "అనుకూల గాలి వేగం (గాలి తీవ్రత తక్కువ). 4-6 గంటల్లో వర్షం లేకపోవడం నిర్ధారించుకొని, మందు లేబుల్ నిబంధనల ప్రకారం పిచికారీ చేయండి."
        elif wind_speed < 25:
            spray = "జాగ్రత్త (గాలి వేగం 15-25 km/h, మందు కొట్టుకుపోయే ప్రమాదం ఉంది — ఉదయం వేళ మాత్రమే పిచికారీ చేయండి)"
        else:
            spray = "అనుకూలం కాదు (తీవ్రమైన గాలి వల్ల మందు వ్యర్థమవుతుంది, పిచికారీ వాయిదా వేయండి)"

        produce = "వర్ష ప్రమాదం: కోసిన ధాన్యం, పత్తి, ఎండబెట్టిన మిర్చిని టార్పాలిన్లతో భద్రపరచండి." if rain_prob > 50 else "సాధారణ జాగ్రత్తలు: పగటిపూట ఎండబెట్టుకోవడానికి అనుకూలం."

    elif lang == "hi":
        if rain_prob > 50:
            irrigation = "बारिश की अधिक संभावना (>50%) है। खेत में जलभराव रोकने के लिए सिंचाई रोक दें।"
            adv = "भारी बारिश का पूर्वानुमान। खेतों में जल निकासी नाली की जांच करें।"
        elif rain_prob > 30:
            irrigation = "छिटपुट बारिश की संभावना। केवल ऊपरी मिट्टी सूखने पर ही हल्की सिंचाई करें।"
            adv = "आंशिक रूप से बादल छाए रहेंगे। हल्की बारिश का जोखिम।"
        else:
            irrigation = "मौसम शुष्क रहेगा। फसल चक्र अनुसार नियमित सिंचाई जारी रखें।"
            adv = "सामान्य कृषि मौसम। दैनिक कृषि कार्यों के लिए उत्तम समय।"

        if wind_speed < 15:
            spray = "अनुकूल हवा की गति (बहाव का जोखिम कम)। छिड़काव से पहले 4-6 घंटे बारिश न होने की पुष्टि करें और उत्पाद लेबल का पालन करें।"
        elif wind_speed < 25:
            spray = "सावधानी (मध्यम हवा 15-25 किमी/घंटा — केवल सुबह शांत समय छिड़काव करें)"
        else:
            spray = "अनुपयुक्त (तेज हवा के कारण छिड़काव का नुकसान होगा, छिड़काव टालें)"

        produce = "बारिश का जोखिम: कटी फसल और सूख रही उपज को तिरपाल से ढकें।" if rain_prob > 50 else "सामान्य निगरानी: दिन में खुले खलिहान में सुखाना सुरक्षित है।"

    elif lang == "ta":
        if rain_prob > 50:
            irrigation = "மழை வாய்ப்பு அதிகம் (>50%). நீர் தேங்குவதை தவிர்க்க பாசனத்தை நிறுத்துங்கள்."
            adv = "மழை முன்னறிவிப்பு. வடிகால் வாய்க்கால்களை தயார் நிலையில் வையுங்கள்."
        else:
            irrigation = "வறண்ட வானிலை. பயிர் நிலைக்கு ஏற்ப வழக்கமான பாசனம் செய்யவும்."
            adv = "இயல்பான வேளாண் வானிலை. களப்பணிகளுக்கு ஏற்றது."
        spray = "சாதகமான காற்று வேகம். தெளிப்பதற்கு முன் 4-6 மணி நேரத்திற்குள் மழை இல்லை என்பதை உறுதி செய்து லேபிளை பின்பற்றவும்." if wind_speed < 15 else "எச்சரிக்கை (அதிக காற்று — தெளிப்பதை தவிர்க்கவும்)"
        produce = "விளைபொருட்களை தார்பாயால் மூடி பாதுகாக்கவும்." if rain_prob > 50 else "தானியங்களை உலர்த்த பாதுகாப்பானது."

    elif lang == "kn":
        if rain_prob > 50:
            irrigation = "ಮಳೆ ಸಂಭವನೀಯತೆ ಹೆಚ್ಚಿದೆ (>50%). ನೀರು ನಿಲ್ಲದಂತೆ ನೀರಾವರಿಯನ್ನು ನಿಲ್ಲಿಸಿ."
            adv = "ಮಳೆಯ ಮುನ್ಸೂಚನೆ. ಹೊಲಗಳಲ್ಲಿ ನೀರು ಹರಿದುಹೋಗುವ ಚರಂಡಿಗಳನ್ನು ಪರಿಶೀಲಿಸಿ."
        else:
            irrigation = "ಒಣ ಹವಾಮಾನ. ಬೆಳೆ ಹಂತಕ್ಕೆ ತಕ್ಕಂತೆ ನಿಯಮಿತ ನೀರಾವರಿ ಮಾಡಿ."
            adv = "ಸಾಮಾನ್ಯ ಕೃಷಿ ಹವಾಮಾನ. ಕೃಷಿ ಕೆಲಸಗಳಿಗೆ ಉತ್ತಮ."
        spray = "ಅನುಕೂಲಕರ ಗಾಳಿ ವೇಗ. ಸಿಂಪಡಿಸುವ ಮೊದಲು 4-6 ಗಂಟೆಗಳಲ್ಲಿ ಮಳೆ ಇಲ್ಲದಿರುವುದನ್ನು ಖಚಿತಪಡಿಸಿಕೊಳ್ಳಿ ಮತ್ತು ಲೇಬಲ್ ಸೂಚನೆ ಪಾಲಿಸಿ." if wind_speed < 15 else "ಎಚ್ಚರಿಕೆ (ಗಾಳಿ ಬೀಸುವಿಕೆ — ಸಿಂಪಡಣೆ ಮುಂದೂಡಿ)"
        produce = "ಬೆಳೆ ಉತ್ಪನ್ನಗಳನ್ನು ತಾಡಪಾಲಿನಿಂದ ಮುಚ್ಚಿ ರಕ್ಷಿಸಿ." if rain_prob > 50 else "ಒಣಗಿಸಲು ಸುರಕ್ಷಿತವಾಗಿದೆ."

    elif lang == "ml":
        if rain_prob > 50:
            irrigation = "മഴ സാധ്യത കൂടുതൽ (>50%). വെള്ളക്കെട്ട് ഒഴിവാക്കാൻ നനയ്ക്കൽ ഒഴിവാക്കുക."
            adv = "മഴ മുന്നറിയിപ്പ്. കൃഷിയിടത്തിൽ നീർവാർച്ച ഉറപ്പാക്കുക."
        else:
            irrigation = "വരണ്ട കാലാവസ്ഥ. പതിവുപോലെ നനയ്ക്കുക."
            adv = "സാധാരണ കാർഷിക കാലാവസ്ഥ."
        spray = "അനുകൂലമായ കാറ്റിന്റെ വേഗത. തളിക്കുന്നതിന് മുൻപ് 4-6 മണിക്കൂറിനുള്ളിൽ മഴയില്ലെന്ന് ഉറപ്പാക്കുക." if wind_speed < 15 else "ശ്രദ്ധിക്കുക (കാറ്റ് കൂടുതൽ — തളിക്കുന്നത് ഒഴിവാക്കുക)"
        produce = "ഉൽപ്പന്നങ്ങൾ ടാർപോളിൻ ഉപയോഗിച്ച് മൂടുക." if rain_prob > 50 else "ഉണക്കാൻ അനുയോജ്യമായ സമയം."

    elif lang == "mr":
        if rain_prob > 50:
            irrigation = "पावसाची दाट शक्यता (>50%). पाणी साचू नये म्हणून सिंचन थांबवा."
            adv = "पावसाचा अंदाज. शेतातील पाण्याचा निचरा व्यवस्थित करा."
        else:
            irrigation = "कोरडे हवामान. पिकाच्या अवस्थेनुसार नियमित पाणी द्या."
            adv = "सर्वसाधारण कृषी हवामान. दैनंदिन शेतीकामासाठी अनुकूल."
        spray = "अनुकूल वाऱ्याचा वेग (वाहून जाण्याचा धोका कमी). फवारणीपूर्वी ४-६ तासांत पाऊस नसल्याची खात्री करा आणि लेबलचे पालन करा." if wind_speed < 15 else "सावधगिरी (वारा अधिक — फवारणी पुढे ढकला)"
        produce = "पावसाचा धोका: काढणी केलेले धान्य व शेतमाल ताडपत्रीने झाकून ठेवा." if rain_prob > 50 else "वाळवण्यासाठी सुरक्षित हवामान."

    else:
        if rain_prob > 50:
            irrigation = "Rain expected (probability > 50%). Hold off on flood or deep irrigation today to avoid waterlogging."
            adv = "High rain probability in forecast. Check drainage channels in fields."
        elif rain_prob > 30:
            irrigation = "Moderate chance of scattered showers. Light irrigation only if soil top layer is dry."
            adv = "Partly cloudy conditions with scattered precipitation risk."
        else:
            irrigation = "Dry weather expected. Maintain regular irrigation schedule according to crop stage."
            adv = "Normal agricultural weather. Good window for standard farm activities."

        if wind_speed < 15:
            spray = "Favorable wind conditions (low drift risk). Verify absence of rain within 4–6 hours and follow product label before spraying."
        elif wind_speed < 25:
            spray = "Caution (Moderate wind 15–25 km/h — elevated drift risk. Spray only during early calm morning hours using low-drift nozzles)"
        else:
            spray = "Unsuitable (High wind gusts >25 km/h — spray drift will cause chemical loss and uneven coverage. Postpone spraying)"

        produce = "High rain risk: Keep harvested grains, cotton pods, and dried chillies securely under waterproof tarpaulins." if rain_prob > 50 else "Standard precautions: Safe for yard drying under normal daytime supervision."

    return irrigation, adv, spray, produce


class WeatherService:
    _geocode_cache: "OrderedDict[tuple[str, str], tuple[float, float, float, str, str, str]]" = OrderedDict()
    _cache_lock = threading.Lock()
    _cache_ttl_seconds = 30 * 24 * 60 * 60
    _cache_limit = 1024
    _forecast_cache: OrderedDict = OrderedDict()
    _forecast_cache_ttl_seconds = 600
    _forecast_cache_limit = 256
    _supported_condition_languages = {"en", "te", "hi", "ta", "mr"}

    @staticmethod
    def _normalize_name(value: str) -> str:
        value = unicodedata.normalize("NFKD", (value or "").strip().casefold())
        value = "".join(ch for ch in value if not unicodedata.combining(ch))
        value = value.replace("&", " and ")
        for suffix in (" district", " dist.", " dist"):
            if value.endswith(suffix):
                value = value[:-len(suffix)].strip()
        return " ".join(value.split())

    @staticmethod
    def _same_state(actual: str, requested: str) -> bool:
        aliases = {
            "orissa": "odisha", "pondicherry": "puducherry", "uttaranchal": "uttarakhand",
            "nct of delhi": "delhi", "national capital territory of delhi": "delhi",
            "dadra and nagar haveli": "dadra and nagar haveli and daman and diu",
            "daman and diu": "dadra and nagar haveli and daman and diu",
        }
        actual_name = WeatherService._normalize_name(actual)
        requested_name = WeatherService._normalize_name(requested)
        return aliases.get(actual_name, actual_name) == aliases.get(requested_name, requested_name)

    @staticmethod
    def _canonical_location(district: str, state: Optional[str]) -> tuple[dict, dict]:
        norm_state = WeatherService._normalize_name(state or "")
        state_aliases = {
            "orissa": "odisha", "pondicherry": "puducherry", "uttaranchal": "uttarakhand",
            "nct of delhi": "delhi", "national capital territory of delhi": "delhi",
            "dadra and nagar haveli": "dadra and nagar haveli and daman and diu",
            "daman and diu": "dadra and nagar haveli and daman and diu",
        }
        norm_state = state_aliases.get(norm_state, norm_state)
        wanted = WeatherService._normalize_name(district)
        district_aliases = {"chhatrapati sambhajinagar": {"aurangabad"}}
        candidates = [d for d in _DISTRICTS if (
            WeatherService._normalize_name(d["name"]) == wanted
            or any(WeatherService._normalize_name(a) == wanted for a in d.get("aliases", []))
            or wanted in district_aliases.get(WeatherService._normalize_name(d["name"]), set())
        )]
        if state:
            matching_states = [s for s in _STATES if WeatherService._same_state(s["name"], state)]
            if not matching_states:
                raise ValueError(f"'{state}' is not a recognized Indian state or union territory.")
            if len(matching_states) != 1:
                raise ValueError("Please select a specific state or union territory.")
            selected_state = matching_states[0]
            candidates = [d for d in candidates if d["stateCode"] == selected_state["code"]]
            if not candidates:
                raise ValueError(f"'{district}' is not a district in {selected_state['name']}. Select a district from {selected_state['name']}.")
        else:
            state_codes = {d["stateCode"] for d in candidates}
            if not candidates:
                raise ValueError(f"'{district}' is not present in the Indian district directory.")
            if len(state_codes) != 1:
                raise ValueError(f"'{district}' exists in more than one state. Select a state to identify the district.")
            selected_state = next(s for s in _STATES if s["code"] in state_codes)
        if not candidates:
            raise ValueError(f"'{district}' is not a district in {selected_state['name']}. Select a district from {selected_state['name']}.")
        if len(candidates) != 1:
            raise ValueError(f"'{district}' matches more than one district in {selected_state['name']}. Select a district using its full name.")
        return selected_state, candidates[0]

    @staticmethod
    def _resolve_search_result(query: str, results: Any) -> dict:
        if not isinstance(results, list):
            raise WeatherProviderUnavailable("WeatherAPI.com returned an invalid location search response.")
        valid = []
        for item in results:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            country = str(item.get("country") or "").strip()
            region = str(item.get("region") or "").strip()
            if not name or not country:
                continue
            try:
                latitude, longitude = WeatherService._valid_coordinates(item.get("lat"), item.get("lon"))
            except WeatherCoverageUnavailable:
                continue
            valid.append({**item, "name": name, "region": region, "country": country, "lat": latitude, "lon": longitude})
        if not valid:
            raise WeatherLocationNotFound("No matching location was found. Try adding a state, region, or country.")

        normalized_query = WeatherService._normalize_name(query)
        exact = []
        for item in valid:
            forms = {
                WeatherService._normalize_name(item["name"]),
                WeatherService._normalize_name(", ".join(part for part in (item["name"], item["region"]) if part)),
                WeatherService._normalize_name(", ".join(part for part in (item["name"], item["region"], item["country"]) if part)),
                WeatherService._normalize_name(", ".join(part for part in (item["name"], item["country"]) if part)),
            }
            if normalized_query in forms:
                exact.append(item)
        candidates = exact if exact else valid if len(valid) == 1 else []
        if not candidates:
            raise WeatherLocationAmbiguous("Several locations match that search. Add the region or country to narrow it down.")
        # Identical display names can still be different places; never pick the
        # first provider result silently.
        unique = {(item["name"].casefold(), item["region"].casefold(), item["country"].casefold(), item["lat"], item["lon"]): item for item in candidates}
        if len(unique) != 1:
            raise WeatherLocationAmbiguous("Several locations match that search. Add the region or country to narrow it down.")
        return next(iter(unique.values()))

    @staticmethod
    async def get_location_weather(location_query: str, language: str = "en") -> WeatherData:
        query = (location_query or "").strip()
        if len(query) < 2:
            raise ValueError("Enter at least two characters to search for a location.")
        results = await WeatherService._weatherapi_request("search.json", {"q": query})
        result = WeatherService._resolve_search_result(query, results)
        return await WeatherService._fetch_forecast(
            result["lat"], result["lon"], result["name"], result["region"] or result["country"], language,
            "WeatherAPI.com Search API result verified against the requested location",
            expected_country=result["country"], expected_region=result["region"],
            searched_location_name=result["name"],
        )

    @staticmethod
    def _valid_coordinates(latitude: Any, longitude: Any) -> tuple[float, float]:
        try:
            lat, lon = float(latitude), float(longitude)
        except (TypeError, ValueError):
            raise WeatherCoverageUnavailable("Weather provider returned invalid location coordinates.")
        if not math.isfinite(lat) or not math.isfinite(lon) or not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise WeatherCoverageUnavailable("Weather provider returned invalid location coordinates.")
        return lat, lon

    @staticmethod
    def _verified_indian_coordinates(latitude: Any, longitude: Any) -> tuple[float, float]:
        lat, lon = WeatherService._valid_coordinates(latitude, longitude)
        # Broad bounds cover India's mainland and island territories. The
        # provider's country and region fields remain the primary validation.
        if not (6.0 <= lat <= 38.6 and 67.0 <= lon <= 98.5):
            raise WeatherCoverageUnavailable("WeatherAPI.com returned coordinates outside India for the selected district.")
        return lat, lon

    @staticmethod
    def _legacy_forecast_icon(condition_code: int) -> str:
        if condition_code == 1000:
            return "sun"
        if condition_code == 1003:
            return "cloud-sun"
        if condition_code in {1030, 1135, 1147}:
            return "cloud-fog"
        if condition_code in {1087, 1273, 1276, 1279, 1282}:
            return "cloud-lightning"
        if condition_code in {1066, 1114, 1117, 1210, 1213, 1216, 1219, 1222, 1225, 1255, 1258}:
            return "cloud-snow"
        if condition_code not in {1006, 1009}:
            return "cloud-rain"
        return "cloud"

    @staticmethod
    def _api_key() -> str:
        key = (settings.WEATHERAPI_KEY or "").strip()
        if not key:
            raise WeatherConfigurationMissing("Weather service is not configured. Add WEATHERAPI_KEY to the backend environment.")
        return key

    @staticmethod
    async def _weatherapi_request(endpoint: str, params: dict) -> Any:
        key = WeatherService._api_key()
        request_params = {**params, "key": key}
        url = f"{WEATHERAPI_BASE_URL}/{endpoint.lstrip('/')}"
        try:
            async with httpx.AsyncClient(timeout=settings.WEATHER_TIMEOUT_SECONDS) as client:
                response = await client.get(url, params=request_params)
        except httpx.TimeoutException:
            logger.warning("weatherapi_timeout endpoint=%s timeout_seconds=%s", endpoint, settings.WEATHER_TIMEOUT_SECONDS)
            if endpoint == "search.json":
                raise WeatherGeocodingUnavailable("WeatherAPI.com district search timed out. Location lookup is temporarily unavailable.")
            raise WeatherProviderUnavailable("WeatherAPI.com request timed out. Live weather is temporarily unavailable.")
        except httpx.RequestError as exc:
            logger.warning("weatherapi_network_error endpoint=%s error_type=%s", endpoint, type(exc).__name__)
            if endpoint == "search.json":
                raise WeatherGeocodingUnavailable("WeatherAPI.com could not be reached for district lookup.")
            raise WeatherProviderUnavailable("WeatherAPI.com could not be reached. Live weather is temporarily unavailable.")

        try:
            payload = response.json()
        except (ValueError, TypeError):
            payload = None

        if response.status_code != 200:
            error = payload.get("error") if isinstance(payload, dict) else None
            error_code = error.get("code") if isinstance(error, dict) else None
            logger.warning("weatherapi_http_error endpoint=%s http_status=%d provider_error_code=%s", endpoint, response.status_code, error_code)
            if error_code == 2006:
                raise WeatherProviderUnavailable("WeatherAPI.com rejected the configured API key.")
            if error_code == 2007:
                raise WeatherProviderUnavailable("WeatherAPI.com request quota is unavailable. Try again later.")
            if endpoint == "search.json":
                raise WeatherGeocodingUnavailable(f"WeatherAPI.com district search returned HTTP {response.status_code}.")
            raise WeatherProviderUnavailable(f"WeatherAPI.com returned HTTP {response.status_code}.")

        if not isinstance(payload, (dict, list)):
            logger.warning("weatherapi_malformed_response endpoint=%s", endpoint)
            if endpoint == "search.json":
                raise WeatherGeocodingUnavailable("WeatherAPI.com returned an invalid district search response.")
            raise WeatherProviderUnavailable("WeatherAPI.com returned an invalid response.")
        if isinstance(payload, dict) and isinstance(payload.get("error"), dict):
            error_code = payload["error"].get("code")
            logger.warning("weatherapi_provider_error endpoint=%s provider_error_code=%s", endpoint, error_code)
            if error_code == 1006:
                return [] if endpoint == "search.json" else payload
            if error_code == 2006:
                raise WeatherProviderUnavailable("WeatherAPI.com rejected the configured API key.")
            if error_code == 2007:
                raise WeatherProviderUnavailable("WeatherAPI.com request quota is unavailable. Try again later.")
            if endpoint == "search.json":
                raise WeatherGeocodingUnavailable("WeatherAPI.com could not search for this district.")
            raise WeatherProviderUnavailable("WeatherAPI.com could not provide weather for this location.")
        logger.debug("weatherapi_response endpoint=%s http_status=%d", endpoint, response.status_code)
        return payload

    @staticmethod
    async def _resolve_district(district: str, state: Optional[str]) -> tuple[float, float, str, str, str]:
        selected_state, canonical_district = WeatherService._canonical_location(district, state)
        district_name, state_name = canonical_district["name"], selected_state["name"]
        key = (WeatherService._normalize_name(district_name), WeatherService._normalize_name(state_name))
        now = time.monotonic()
        with WeatherService._cache_lock:
            cached = WeatherService._geocode_cache.get(key)
            if cached and cached[0] > now:
                WeatherService._geocode_cache.move_to_end(key)
                return cached[1], cached[2], cached[3], cached[4], cached[5]
            if cached:
                del WeatherService._geocode_cache[key]

        payload = await WeatherService._weatherapi_request("search.json", {
            "q": f"{district_name}, {state_name}, India",
            "lang": "en",
        })
        if not isinstance(payload, list):
            logger.warning("weatherapi_geocode_malformed district=%r state=%r", district_name, state_name)
            raise WeatherGeocodingUnavailable("WeatherAPI.com returned an invalid location search response.")

        wanted_names = {WeatherService._normalize_name(district_name)}
        wanted_names.update(WeatherService._normalize_name(alias) for alias in canonical_district.get("aliases", []))
        if district_name == "Chhatrapati Sambhajinagar":
            wanted_names.add("aurangabad")

        matches = {}
        for index, item in enumerate(payload):
            if not isinstance(item, dict):
                logger.info("weatherapi_geocode_candidate_rejected district=%r state=%r index=%d reason=invalid_candidate", district_name, state_name, index)
                continue
            country = str(item.get("country") or "").strip()
            region = str(item.get("region") or "").strip()
            name = str(item.get("name") or "").strip()
            candidate_name = WeatherService._normalize_name(name)
            if country.casefold() != "india":
                reason = "country_mismatch"
            elif not WeatherService._same_state(region, state_name):
                reason = "state_mismatch"
            elif candidate_name not in wanted_names:
                reason = "district_name_mismatch"
            else:
                reason = None
            coordinates = None
            if reason is None:
                try:
                    coordinates = WeatherService._verified_indian_coordinates(item.get("lat"), item.get("lon"))
                except WeatherCoverageUnavailable:
                    reason = "invalid_coordinates"
            if reason is not None:
                logger.info(
                    "weatherapi_geocode_candidate_rejected district=%r state=%r index=%d name=%r region=%r country=%r reason=%s",
                    district_name, state_name, index, name[:100], region[:100], country[:80], reason,
                )
                continue
            lat, lon = coordinates
            logger.info("weatherapi_geocode_candidate_accepted district=%r state=%r index=%d", district_name, state_name, index)
            matches[(round(lat, 5), round(lon, 5))] = (lat, lon)

        if not matches:
            logger.info("weatherapi_geocode_unverified district=%r state=%r candidates=%d", district_name, state_name, len(payload))
            raise WeatherCoverageUnavailable(f"Weather coverage is currently unavailable for {district_name}, {state_name}; WeatherAPI.com did not return an exact verified match.")
        if len(matches) > 1:
            logger.warning("weatherapi_geocode_ambiguous district=%r state=%r matches=%d", district_name, state_name, len(matches))
            raise WeatherCoverageUnavailable(f"WeatherAPI.com returned ambiguous locations for {district_name}, {state_name}.")

        lat, lon = next(iter(matches.values()))
        coordinate_source = "WeatherAPI.com Search API; exact district, state and country verified"
        with WeatherService._cache_lock:
            WeatherService._geocode_cache[key] = (
                time.monotonic() + WeatherService._cache_ttl_seconds,
                lat, lon, district_name, state_name, coordinate_source,
            )
            WeatherService._geocode_cache.move_to_end(key)
            while len(WeatherService._geocode_cache) > WeatherService._cache_limit:
                WeatherService._geocode_cache.popitem(last=False)
        return lat, lon, district_name, state_name, coordinate_source

    @staticmethod
    async def get_coordinate_weather(latitude: float, longitude: float, language: str = "en") -> WeatherData:
        try:
            lat, lon = float(latitude), float(longitude)
        except (TypeError, ValueError):
            raise ValueError("Valid latitude and longitude are required.")
        if not math.isfinite(lat) or not math.isfinite(lon) or not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError("Coordinates are outside the valid latitude/longitude range.")
        return await WeatherService._fetch_forecast(
            lat, lon, "", "", language,
            "WeatherAPI.com forecast location; country and state verified",
            expected_state=None, expected_district=None,
        )

    @staticmethod
    async def get_district_weather(district_query: str, state_query: Optional[str] = None, language: str = "en") -> WeatherData:
        district_name = (district_query or "").strip()
        state_name = (state_query or "").strip()
        if not district_name:
            raise ValueError("A district is required for district-based weather.")
        selected_state, selected_district = WeatherService._canonical_location(district_name, state_name or None)
        lat, lon, district_name, state_name, coordinate_source = await WeatherService._resolve_district(
            selected_district["name"], selected_state["name"]
        )
        return await WeatherService._fetch_forecast(
            lat, lon, district_name, state_name, language, coordinate_source,
            expected_state=state_name, expected_district=selected_district,
        )

    @staticmethod
    def _number(value: Any, field: str) -> float:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            raise WeatherProviderUnavailable(f"WeatherAPI.com returned invalid {field} data.")
        if not math.isfinite(parsed):
            raise WeatherProviderUnavailable(f"WeatherAPI.com returned invalid {field} data.")
        return parsed

    @staticmethod
    def _condition(condition: Any, field: str) -> tuple[str, int, str]:
        if not isinstance(condition, dict) or not str(condition.get("text") or "").strip():
            raise WeatherProviderUnavailable(f"WeatherAPI.com returned no {field} condition.")
        try:
            code = int(condition.get("code"))
        except (TypeError, ValueError):
            raise WeatherProviderUnavailable(f"WeatherAPI.com returned an invalid {field} condition code.")
        if code <= 0:
            raise WeatherProviderUnavailable(f"WeatherAPI.com returned an invalid {field} condition code.")
        icon = str(condition.get("icon") or "").strip()
        if icon.startswith("//"):
            icon = f"https:{icon}"
        try:
            parsed = urlparse(icon)
        except ValueError:
            raise WeatherProviderUnavailable(f"WeatherAPI.com returned an invalid {field} condition icon.")
        if parsed.scheme != "https" or parsed.hostname != "cdn.weatherapi.com" or not parsed.path.startswith("/weather/"):
            raise WeatherProviderUnavailable(f"WeatherAPI.com returned an invalid {field} condition icon.")
        return str(condition["text"]).strip(), code, parsed.geturl()

    @staticmethod
    async def _fetch_forecast(
        lat: float, lon: float, district_name: str, state_name: str, language: str,
        coordinate_source: str = "", expected_state: Optional[str] = None,
        expected_district: Optional[dict] = None,
        expected_country: Optional[str] = None, expected_region: Optional[str] = None,
        searched_location_name: Optional[str] = None,
    ) -> WeatherData:
        lat, lon = WeatherService._valid_coordinates(lat, lon)
        cache_district = district_name.casefold() if district_name else "coordinates"
        cache_state = state_name.casefold() if state_name else "coordinates"
        # Keep location identity precise enough that nearby farm coordinates
        # do not share another point's live forecast cache entry.
        cache_key = (round(lat, 5), round(lon, 5), language, cache_district, cache_state, (expected_country or "India").casefold())
        now = time.monotonic()
        with WeatherService._cache_lock:
            cached = WeatherService._forecast_cache.get(cache_key)
            if cached and cached[0] > now:
                WeatherService._forecast_cache.move_to_end(cache_key)
                return cached[1]
            if cached:
                del WeatherService._forecast_cache[cache_key]

        api_language = language if language in WeatherService._supported_condition_languages else "en"
        payload = await WeatherService._weatherapi_request("forecast.json", {
            "q": f"{lat},{lon}", "days": 3, "aqi": "no", "alerts": "no", "lang": api_language,
        })
        try:
            location = payload.get("location")
            current = payload.get("current")
            forecast_days = payload.get("forecast", {}).get("forecastday")
            if not isinstance(location, dict) or not isinstance(current, dict) or not isinstance(forecast_days, list) or not forecast_days:
                raise WeatherProviderUnavailable("WeatherAPI.com returned an incomplete forecast response.")

            country = str(location.get("country") or "").strip()
            provider_state = str(location.get("region") or "").strip()
            if expected_country:
                if WeatherService._normalize_name(country) != WeatherService._normalize_name(expected_country):
                    raise WeatherCoverageUnavailable("WeatherAPI.com returned a different country than the searched location.")
                if expected_region and WeatherService._normalize_name(provider_state) != WeatherService._normalize_name(expected_region):
                    raise WeatherCoverageUnavailable("WeatherAPI.com returned a different region than the searched location.")
                canonical_state = expected_region or provider_state or country
                provider_district = searched_location_name or str(location.get("name") or "").strip()
            elif country.casefold() != "india":
                if expected_state:
                    raise WeatherCoverageUnavailable("WeatherAPI.com did not return an Indian location for the selected district.")
                raise ValueError("GPS coordinates could not be verified as a location in India.")
            else:
                matching_states = [s for s in _STATES if WeatherService._same_state(s["name"], provider_state)]
                if not provider_state or len(matching_states) != 1:
                    raise WeatherCoverageUnavailable("WeatherAPI.com could not verify the Indian state for this location.")
                canonical_state = matching_states[0]["name"]
                if expected_state and not WeatherService._same_state(provider_state, expected_state):
                    raise WeatherCoverageUnavailable("WeatherAPI.com resolved the request to a different state; no alternate location was used.")
                provider_district = str(location.get("name") or "").strip()
            if expected_district:
                # The Search API already verified the requested district, state,
                # country and coordinates. Forecast's reverse label can be a
                # nearby locality at the same verified point, so preserve the
                # canonical requested district in the response instead of
                # substituting that label.
                try:
                    _forecast_state, forecast_district = WeatherService._canonical_location(provider_district, expected_state)
                except ValueError:
                    forecast_district = None
                if forecast_district and forecast_district["id"] != expected_district["id"]:
                    raise WeatherCoverageUnavailable("WeatherAPI.com resolved the request to a different district; no alternate location was used.")
                provider_district = expected_district["name"]

            provider_lat, provider_lon = WeatherService._valid_coordinates(location.get("lat"), location.get("lon"))
            if abs(provider_lat - lat) > 0.05 or abs(provider_lon - lon) > 0.05:
                raise WeatherCoverageUnavailable("WeatherAPI.com returned weather for a different location; no alternate location was used.")

            temp = WeatherService._number(current.get("temp_c"), "temperature")
            feels_like = WeatherService._number(current.get("feelslike_c"), "feels-like temperature")
            humidity = int(WeatherService._number(current.get("humidity"), "humidity"))
            wind_speed = WeatherService._number(current.get("wind_kph"), "wind speed")
            wind_direction = str(current.get("wind_dir") or "").strip()
            if not wind_direction:
                raise WeatherProviderUnavailable("WeatherAPI.com returned no current wind direction.")
            visibility = WeatherService._number(current.get("vis_km"), "visibility")
            rainfall = WeatherService._number(current.get("precip_mm"), "rainfall")
            condition, condition_code, condition_icon_url = WeatherService._condition(current.get("condition"), "current")
            if not 0 <= humidity <= 100 or wind_speed < 0 or rainfall < 0 or visibility < 0:
                raise WeatherProviderUnavailable("WeatherAPI.com returned invalid current measurements.")

            normalized_days = []
            for entry in forecast_days[:3]:
                if not isinstance(entry, dict) or not isinstance(entry.get("day"), dict):
                    raise WeatherProviderUnavailable("WeatherAPI.com returned an incomplete daily forecast.")
                day = entry["day"]
                date_text = str(entry.get("date") or "")
                try:
                    parsed_date = datetime.strptime(date_text, "%Y-%m-%d")
                except ValueError:
                    raise WeatherProviderUnavailable("WeatherAPI.com returned an invalid forecast date.")
                max_temp = WeatherService._number(day.get("maxtemp_c"), "forecast maximum temperature")
                min_temp = WeatherService._number(day.get("mintemp_c"), "forecast minimum temperature")
                rain_value = day.get("daily_chance_of_rain")
                rain_probability = int(WeatherService._number(rain_value, "forecast rain probability"))
                day_condition, day_condition_code, day_condition_icon_url = WeatherService._condition(day.get("condition"), "daily forecast")
                if max_temp < min_temp or not 0 <= rain_probability <= 100:
                    raise WeatherProviderUnavailable("WeatherAPI.com returned invalid daily forecast measurements.")
                normalized_days.append(ForecastDay(
                    day_name="Today" if not normalized_days else parsed_date.strftime("%a"),
                    date=date_text,
                    temp_max=max_temp,
                    temp_min=min_temp,
                    condition=day_condition,
                    condition_code=day_condition_code,
                    condition_icon_url=day_condition_icon_url,
                    precipitation_probability=rain_probability,
                    icon=WeatherService._legacy_forecast_icon(day_condition_code),
                ))
            rain_prob = normalized_days[0].precipitation_probability

            irrigation_advice, advisory, _spray_suitability, produce_protection = get_localized_weather_advice(
                rain_prob=rain_prob, wind_speed=wind_speed, language=language,
            )
            safe_spray = {
                "te": "పిచికారీ నిర్ణయం తీసుకునే ముందు గంటవారీ వర్ష సూచన, గాలి పరిస్థితులు, మందు లేబుల్‌ను పరిశీలించండి. ఈ రోజువారీ అంచనా ఒక్కటే సరిపోదు.",
                "hi": "छिड़काव से पहले घंटेवार बारिश का पूर्वानुमान, हवा और उत्पाद का लेबल जाँचें। केवल दैनिक पूर्वानुमान पर्याप्त नहीं है।",
                "ta": "தெளிப்பதற்கு முன் மணிநேர மழை முன்னறிவிப்பு, காற்று மற்றும் தயாரிப்பு லேபிளைச் சரிபார்க்கவும். தினசரி முன்னறிவிப்பு மட்டும் போதாது.",
                "kn": "ಸಿಂಪಡಿಸುವ ಮೊದಲು ಗಂಟೆಗಂಟೆಯ ಮಳೆ ಮುನ್ಸೂಚನೆ, ಗಾಳಿ ಮತ್ತು ಉತ್ಪನ್ನದ ಲೇಬಲ್ ಪರಿಶೀಲಿಸಿ. ದೈನಂದಿನ ಮುನ್ಸೂಚನೆ ಮಾತ್ರ ಸಾಕಾಗುವುದಿಲ್ಲ.",
                "ml": "തളിക്കുന്നതിന് മുമ്പ് മണിക്കൂർ അടിസ്ഥാനത്തിലുള്ള മഴ പ്രവചനം, കാറ്റ്, ഉൽപ്പന്ന ലേബൽ എന്നിവ പരിശോധിക്കുക. ദിവസത്തെ പ്രവചനം മാത്രം മതിയാകില്ല.",
                "mr": "फवारणीपूर्वी तासानुसार पावसाचा अंदाज, वारा आणि उत्पादनाचे लेबल तपासा. केवळ दैनिक अंदाज पुरेसा नाही.",
                "en": "Check the hourly rain forecast, wind conditions and product label before spraying. A daily forecast alone is not enough to recommend spraying.",
            }
            weather = WeatherData(
                district=provider_district or district_name or "Selected location",
                state=canonical_state,
                country=country,
                temperature=temp,
                feels_like=feels_like,
                condition=condition,
                condition_code=condition_code,
                condition_icon_url=condition_icon_url,
                humidity=humidity,
                wind_speed=wind_speed,
                wind_direction=wind_direction,
                visibility_km=visibility,
                rain_probability=rain_prob,
                rainfall_mm=rainfall,
                advisory=advisory,
                irrigation_advice=irrigation_advice,
                spray_suitability=safe_spray.get(language, safe_spray["en"]),
                produce_protection=produce_protection,
                is_official_alert=False,
                source="WeatherAPI.com forecast data; retrieved live and not an official IMD warning.",
                coordinate_source=coordinate_source or None,
                retrieval_timestamp=datetime.now(timezone.utc).isoformat(),
                forecast=normalized_days,
            )
        except (WeatherCoverageUnavailable, WeatherProviderUnavailable, ValueError):
            raise
        except (TypeError, KeyError, AttributeError) as exc:
            logger.warning("weatherapi_malformed_forecast error_type=%s", type(exc).__name__)
            raise WeatherProviderUnavailable("WeatherAPI.com returned an invalid forecast response.")

        with WeatherService._cache_lock:
            WeatherService._forecast_cache[cache_key] = (time.monotonic() + WeatherService._forecast_cache_ttl_seconds, weather)
            WeatherService._forecast_cache.move_to_end(cache_key)
            while len(WeatherService._forecast_cache) > WeatherService._forecast_cache_limit:
                WeatherService._forecast_cache.popitem(last=False)
        return weather
