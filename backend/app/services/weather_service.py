import httpx
import json
import logging
import threading
import time
import unicodedata
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional
from ..config import settings
from ..models.schemas import WeatherData, ForecastDay

logger = logging.getLogger("weather_service")

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
    """Open-Meteo could not provide a usable forecast."""


WMO_CODE_MAP = {
    0: "Clear Sky",
    1: "Mainly Clear",
    2: "Partly Cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing Rime Fog",
    51: "Light Drizzle",
    53: "Moderate Drizzle",
    55: "Dense Drizzle",
    56: "Light Freezing Drizzle",
    57: "Dense Freezing Drizzle",
    61: "Slight Rain",
    63: "Moderate Rain",
    65: "Heavy Rain",
    66: "Light Freezing Rain",
    67: "Heavy Freezing Rain",
    71: "Slight Snow Fall",
    73: "Moderate Snow Fall",
    75: "Heavy Snow Fall",
    77: "Snow Grains",
    80: "Slight Rain Showers",
    81: "Moderate Rain Showers",
    82: "Violent Rain Showers",
    85: "Slight Snow Showers",
    86: "Heavy Snow Showers",
    95: "Thunderstorm",
    96: "Thunderstorm with Slight Hail",
    99: "Thunderstorm with Heavy Hail"
}


def get_wmo_condition(code: int) -> str:
    return WMO_CODE_MAP.get(code, "Variable Conditions")


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
        district_aliases = {
            "chhatrapati sambhajinagar": {"aurangabad"},
        }
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

        params = {
            "q": f"{district_name}, {state_name}, India",
            "format": "jsonv2", "addressdetails": "1", "countrycodes": "in", "limit": "10",
        }
        try:
            async with httpx.AsyncClient(timeout=settings.WEATHER_TIMEOUT_SECONDS, headers={
                "User-Agent": "KisanHita/1.0 (district weather lookup)", "Accept": "application/json",
            }) as client:
                response = await client.get("https://nominatim.openstreetmap.org/search", params=params)
                if response.status_code != 200:
                    logger.warning(
                        "weather_geocode_search_failed district=%r state=%r http_status=%d",
                        district_name, state_name, response.status_code,
                    )
                    raise WeatherGeocodingUnavailable(f"District geocoder returned HTTP {response.status_code}.")
                candidates = response.json()
                candidate_count = len(candidates) if isinstance(candidates, list) else 0
                logger.info(
                    "weather_geocode_search district=%r state=%r http_status=%d candidates=%d",
                    district_name, state_name, response.status_code, candidate_count,
                )
        except httpx.TimeoutException:
            logger.warning("weather_geocode_timeout district=%r state=%r", district_name, state_name)
            raise WeatherGeocodingUnavailable("District geocoding timed out. Live weather is currently unavailable.")
        except httpx.RequestError as exc:
            logger.warning(
                "weather_geocode_request_error district=%r state=%r error_type=%s",
                district_name, state_name, type(exc).__name__,
            )
            raise WeatherGeocodingUnavailable(f"District geocoding network error ({exc}). Live weather is currently unavailable.")
        except WeatherGeocodingUnavailable:
            raise
        except Exception as exc:
            raise WeatherGeocodingUnavailable(f"District geocoding failed: {exc}")

        matches = []
        wanted_districts = {WeatherService._normalize_name(district_name)}
        wanted_districts.update(WeatherService._normalize_name(a) for a in canonical_district.get("aliases", []))
        if district_name == "Chhatrapati Sambhajinagar":
            wanted_districts.add("aurangabad")

        administrative_fields = (
            "state_district", "district", "county", "municipality", "city_district", "locality"
        )
        for index, item in enumerate(candidates if isinstance(candidates, list) else []):
            address = item.get("address") or {}
            administrative_address = {
                field: str(address[field])[:100]
                for field in ("state", *administrative_fields)
                if address.get(field)
            }
            logger.info(
                "weather_geocode_candidate district=%r state=%r index=%d name=%r category=%r type=%r country=%r administrative_address=%s",
                district_name,
                state_name,
                index,
                str(item.get("name") or "")[:120],
                item.get("category", item.get("class", "")),
                item.get("type", ""),
                address.get("country_code", ""),
                json.dumps(administrative_address, ensure_ascii=False, separators=(",", ":")),
            )

            if str(address.get("country_code", "")).casefold() != "in":
                logger.info(
                    "weather_geocode_candidate_rejected district=%r state=%r index=%d reason=country_mismatch",
                    district_name, state_name, index,
                )
                continue
            actual_state = str(address.get("state") or "")
            if not actual_state or not WeatherService._same_state(actual_state, state_name):
                logger.info(
                    "weather_geocode_candidate_rejected district=%r state=%r index=%d reason=state_mismatch",
                    district_name, state_name, index,
                )
                continue

            category = item.get("category", item.get("class", ""))
            item_type = item.get("type", "")
            if category != "boundary" or item_type != "administrative":
                logger.info(
                    "weather_geocode_candidate_rejected district=%r state=%r index=%d reason=boundary_type_mismatch",
                    district_name, state_name, index,
                )
                continue

            administrative_names = [address.get(field) for field in administrative_fields]
            administrative_names.append(item.get("name"))
            result_names = {
                WeatherService._normalize_name(str(value))
                for value in administrative_names if value
            }
            if not result_names.intersection(wanted_districts):
                logger.info(
                    "weather_geocode_candidate_rejected district=%r state=%r index=%d reason=district_name_mismatch",
                    district_name, state_name, index,
                )
                continue

            try:
                lat, lon = float(item["lat"]), float(item["lon"])
            except (KeyError, TypeError, ValueError):
                logger.info(
                    "weather_geocode_candidate_rejected district=%r state=%r index=%d reason=invalid_coordinates",
                    district_name, state_name, index,
                )
                continue
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                logger.info(
                    "weather_geocode_candidate_rejected district=%r state=%r index=%d reason=invalid_coordinates",
                    district_name, state_name, index,
                )
                continue

            # Prefer the district-level boundary over nested county/local boundaries.
            # For Kangra, this selects OSM relation 364074 rather than 9971196.
            is_district_level = (
                bool(address.get("state_district"))
                and not any(address.get(field) for field in (
                    "county", "municipality", "city_district", "locality"
                ))
            )

            logger.info(
                "weather_geocode_candidate_accepted district=%r state=%r index=%d district_level=%s",
                district_name, state_name, index, is_district_level,
            )
            matches.append((lat, lon, district_name, state_name, is_district_level))

        preferred = [item for item in matches if item[4]]
        logger.info(
            "weather_geocode_candidates_filtered district=%r state=%r matching=%d preferred_district_level=%d",
            district_name, state_name, len(matches), len(preferred),
        )
        if preferred:
            matches = preferred

        unique = {
            (
                round(item[0], 5),
                round(item[1], 5),
                WeatherService._normalize_name(item[3])
            ): item
            for item in matches
        }

        if len(unique) != 1:
            if unique:
                logger.warning(
                    "weather_geocode_ambiguous district=%r state=%r unique_matches=%d",
                    district_name, state_name, len(unique),
                )
                raise ValueError(f"District '{district}' is ambiguous in {state or 'India'}. Select a state and district that match.")
            logger.warning(
                "weather_geocode_unverified district=%r state=%r candidates=%d matching=0 preferred_district_level=%d",
                district_name, state_name, candidate_count, len(preferred),
            )
            raise WeatherCoverageUnavailable(f"Weather coverage is currently unavailable for {district_name}, {state_name}; its location could not be verified.")

        lat, lon, resolved_district, resolved_state = next(iter(unique.values()))[:4]

        with WeatherService._cache_lock:
            WeatherService._geocode_cache[key] = (
                time.monotonic() + WeatherService._cache_ttl_seconds,
                lat,
                lon,
                resolved_district,
                resolved_state,
                "Nominatim administrative boundary; country/state/district verified"
            )
            WeatherService._geocode_cache.move_to_end(key)
            while len(WeatherService._geocode_cache) > WeatherService._cache_limit:
                WeatherService._geocode_cache.popitem(last=False)

        return lat, lon, resolved_district, resolved_state, "Nominatim administrative boundary; country/state/district verified"

    @staticmethod
    async def get_coordinate_weather(latitude: float, longitude: float, language: str = "en") -> WeatherData:
        try:
            lat, lon = float(latitude), float(longitude)
        except (TypeError, ValueError):
            raise ValueError("Valid latitude and longitude are required.")
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError("Coordinates are outside the valid latitude/longitude range.")

        try:
            async with httpx.AsyncClient(timeout=settings.WEATHER_TIMEOUT_SECONDS, headers={
                "User-Agent": "KisanHita/1.0 (GPS weather lookup)", "Accept": "application/json",
            }) as client:
                response = await client.get("https://nominatim.openstreetmap.org/reverse", params={
                    "format": "jsonv2", "lat": str(lat), "lon": str(lon), "zoom": "10", "addressdetails": "1", "accept-language": "en",
                })
                if response.status_code != 200:
                    raise WeatherGeocodingUnavailable(f"GPS location verification returned HTTP {response.status_code}.")
                address = response.json().get("address") or {}
        except httpx.TimeoutException:
            raise WeatherGeocodingUnavailable("GPS location verification timed out. Live weather is currently unavailable.")
        except httpx.RequestError as exc:
            raise WeatherGeocodingUnavailable(f"GPS location verification network error ({exc}). Live weather is currently unavailable.")

        country = str(address.get("country_code", "")).casefold()
        state_name = str(address.get("state") or "")
        district_name = str(address.get("state_district") or address.get("district") or address.get("county") or "")
        if country != "in":
            raise ValueError("GPS coordinates could not be verified as a location in India.")
        if not state_name or not district_name:
            raise ValueError("GPS coordinates did not resolve to a verified Indian state and district.")

        return await WeatherService._fetch_forecast(
            lat, lon, district_name, state_name, language,
            "Nominatim reverse geocoding; country/state/district verified"
        )

    @staticmethod
    async def get_district_weather(district_query: str, state_query: Optional[str] = None, language: str = "en") -> WeatherData:
        district_name = (district_query or "").strip()
        state_name = (state_query or "").strip()
        if not district_name:
            raise ValueError("A district is required for district-based weather.")

        selected_state, selected_district = WeatherService._canonical_location(district_name, state_name or None)

        if settings.DEMO_DATA_ENABLED:
            from .prototype_demo_service import weather as demo_weather
            return demo_weather(selected_district["name"], selected_state["name"], language)

        lat, lon, district_name, state_name, coordinate_source = await WeatherService._resolve_district(
            selected_district["name"], selected_state["name"]
        )

        return await WeatherService._fetch_forecast(
            lat, lon, district_name, state_name, language, coordinate_source
        )

    @staticmethod
    async def _fetch_forecast(lat: float, lon: float, district_name: str, state_name: str, language: str, coordinate_source: str = "") -> WeatherData:
        cache_key = (round(lat, 2), round(lon, 2), language, district_name.casefold(), state_name.casefold())
        now = time.monotonic()

        with WeatherService._cache_lock:
            cached = WeatherService._forecast_cache.get(cache_key)
            if cached and cached[0] > now:
                WeatherService._forecast_cache.move_to_end(cache_key)
                return cached[1]
            if cached:
                del WeatherService._forecast_cache[cache_key]

        url = (
            f"https://api.open-meteo.com/v1/forecast?"
            f"latitude={lat}&longitude={lon}&"
            f"current=temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m&"
            f"daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max&"
            f"timezone=auto"
        )

        try:
            async with httpx.AsyncClient(timeout=settings.WEATHER_TIMEOUT_SECONDS) as client:
                res = await client.get(url)
                if res.status_code == 200:
                    data = res.json()
                    curr = data.get("current", {})
                    daily = data.get("daily", {})

                    required_current = ("temperature_2m", "relative_humidity_2m", "wind_speed_10m", "weather_code")
                    if any(curr.get(field) is None for field in required_current):
                        raise RuntimeError("Weather provider returned incomplete current measurements; live weather is unavailable.")

                    temp = float(curr["temperature_2m"])
                    apparent = curr.get("apparent_temperature")
                    feels_like = float(apparent) if apparent is not None else None
                    humidity = int(curr["relative_humidity_2m"])
                    wind_speed = float(curr["wind_speed_10m"])
                    wmo_code = int(curr["weather_code"])

                    if not 0 <= humidity <= 100 or wind_speed < 0:
                        raise RuntimeError("Weather provider returned invalid current measurements; live weather is unavailable.")

                    cond = get_wmo_condition(wmo_code)

                    daily_probs = daily.get("precipitation_probability_max")
                    if not daily_probs or daily_probs[0] is None:
                        raise RuntimeError("Weather provider returned no current-day rain probability; live weather is unavailable.")

                    rain_prob = int(daily_probs[0])
                    if not 0 <= rain_prob <= 100:
                        raise RuntimeError("Weather provider returned an invalid rain probability; live weather is unavailable.")

                    forecast_list = []
                    dates = daily.get("time", [])
                    maxs = daily.get("temperature_2m_max", [])
                    mins = daily.get("temperature_2m_min", [])
                    codes = daily.get("weather_code", [])
                    probs = daily.get("precipitation_probability_max", [])

                    if not dates or any(len(values) < min(7, len(dates)) for values in (maxs, mins, codes, probs)):
                        raise RuntimeError("Weather provider returned an incomplete forecast; live forecast is unavailable.")

                    for i in range(min(7, len(dates))):
                        if any(values[i] is None for values in (maxs, mins, codes, probs)):
                            raise RuntimeError("Weather provider returned missing forecast measurements.")

                        dt = datetime.strptime(dates[i], "%Y-%m-%d")
                        day_name = dt.strftime("%a") if i > 0 else "Today"
                        day_cond = get_wmo_condition(int(codes[i]))

                        forecast_list.append(ForecastDay(
                            day_name=day_name,
                            date=dates[i],
                            temp_max=float(maxs[i]),
                            temp_min=float(mins[i]),
                            condition=day_cond,
                            precipitation_probability=int(probs[i]),
                            icon="cloud-sun"
                        ))

                    irrigation_advice, advisory, spray_suitability, produce_protection = get_localized_weather_advice(
                        rain_prob=rain_prob,
                        wind_speed=wind_speed,
                        language=language
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
                    spray_suitability = safe_spray.get(language, safe_spray["en"])

                    weather = WeatherData(
                        district=district_name,
                        state=state_name,
                        temperature=temp,
                        feels_like=feels_like,
                        condition=cond,
                        humidity=humidity,
                        wind_speed=wind_speed,
                        rain_probability=rain_prob,
                        rainfall_mm=float(curr.get("precipitation") or 0.0),
                        advisory=advisory,
                        irrigation_advice=irrigation_advice,
                        spray_suitability=spray_suitability,
                        produce_protection=produce_protection,
                        is_official_alert=False,
                        source="Open-Meteo.com under CC BY 4.0. Numerical weather prediction; not an official IMD meteorological warning.",
                        coordinate_source=coordinate_source or None,
                        retrieval_timestamp=datetime.now(timezone.utc).isoformat(),
                        forecast=forecast_list
                    )

                    with WeatherService._cache_lock:
                        WeatherService._forecast_cache[cache_key] = (
                            time.monotonic() + WeatherService._forecast_cache_ttl_seconds,
                            weather
                        )
                        WeatherService._forecast_cache.move_to_end(cache_key)
                        while len(WeatherService._forecast_cache) > WeatherService._forecast_cache_limit:
                            WeatherService._forecast_cache.popitem(last=False)

                    return weather
                else:
                    raise WeatherProviderUnavailable(f"Open-Meteo API returned HTTP {res.status_code} for {district_name}")

        except httpx.TimeoutException:
            raise WeatherProviderUnavailable(f"Weather API request timed out ({settings.WEATHER_TIMEOUT_SECONDS}s) for {district_name}. Live weather is currently unavailable.")
        except httpx.RequestError as exc:
            raise WeatherProviderUnavailable(f"Weather API network error ({exc}) for {district_name}. Live weather is currently unavailable.")
        except ValueError:
            raise
        except RuntimeError:
            raise
        except Exception as exc:
            raise WeatherProviderUnavailable(f"Unable to retrieve weather for {district_name}: {exc}")