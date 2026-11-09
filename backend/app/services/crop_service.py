from typing import List, Dict, Any, Optional
from ..models.schemas import CropRecommendation, CropAdvisorResponse

# =========================================================================
# Realistic Regional Demonstration & Reference Crop Dataset
# Covers key Indian crops across various soil types, irrigation levels,
# and seasons with specific support for Andhra Pradesh (Nellore, Guntur, Rayalaseema)
# and Telangana agronomic zones.
# Clearly marked as reference/demo agronomic guidelines.
# =========================================================================

DEMO_CROP_REFERENCE_DATA: List[Dict[str, Any]] = [
    {
        "crop_name": "Bengal Gram (Chickpea)",
        "variety": "JG-11 / NBeG-3 (Wilt Resistant)",
        "suitable_soils": ["black cotton soil", "clay soil", "loamy soil", "black soil", "heavy loamy soil"],
        "suitable_seasons": ["rabi (winter)", "winter", "rabi"],
        "water_levels": ["good irrigation", "limited irrigation", "rain-dependent"],
        "duration_days": "95–105 Days",
        "water_requirement": "Low to Moderate / Residual (Thrives on stored moisture)",
        "soil_suitability": "Utilizes residual black soil moisture effectively following early Kharif harvests without requiring heavy flood irrigation.",
        "limitations": "Sensitive to collar rot if sown in warm soil; pod borer (Helicoverpa) damage during flowering requires timely scouting.",
        "next_steps": "Treat seed with Trichoderma viride before sowing; sow after soil temperature cools in late October to November.",
        "citation": "ICAR-Indian Institute of Pulses Research (IIPR) & ANGRAU/PJTSAU Package of Practices",
        "publication_date": "2025-2026 University Reference Compendium",
        "applicable_regions": ["Nellore", "Andhra Pradesh", "Telangana", "Karnataka", "Rayalaseema"],
        "suitable_season": "Rabi (Winter)",
        "suitability_score": "High Suitability (Demo Reference)",
        "cultivation_guidance": "Sow at 30 cm x 10 cm spacing. Apply 20 kg N and 50 kg P2O5 per hectare. One irrigation at branching and one at pod development."
    },
    {
        "crop_name": "Black Gram (Urad Dal)",
        "variety": "LBG-752 / TBG-104 / PU-31",
        "suitable_soils": ["black cotton soil", "clay soil", "loamy soil", "black soil"],
        # This Nellore reference entry is specifically for Rabi rice fallows;
        # do not surface its rice-fallow operations as a Kharif suggestion.
        "suitable_seasons": ["rabi (winter)", "winter", "rabi"],
        "water_levels": ["good irrigation", "limited irrigation"],
        "duration_days": "75–85 Days",
        "water_requirement": "Moderate (Ideal for rice fallows)",
        "soil_suitability": "Excellent for Nellore and coastal AP black soils and rice-fallow systems with residual moisture.",
        "limitations": "Susceptible to yellow mosaic virus transmitted by whiteflies; waterlogging during early seedling stage causes damping off.",
        "next_steps": "Seed treatment with Imidacloprid (5 ml/kg) and Rhizobium culture; broadcast in rice fallows 2-3 days before paddy harvest.",
        "citation": "ANGRAU Regional Agricultural Research Station, Lam & Nellore Pulse Advisory",
        "publication_date": "2025-2026 ANGRAU Agronomy Compendium",
        "applicable_regions": ["Nellore", "Andhra Pradesh", "Guntur", "Krishna", "Coastal Andhra"],
        "suitable_season": "Rabi / Rice Fallow",
        "suitability_score": "High Suitability (Nellore Coastal Reference)",
        "cultivation_guidance": "Seed rate 40 kg/ha for rice fallow broadcasting. Apply foliar DAP (2%) spray at 30 and 45 days after sowing."
    },
    {
        "crop_name": "Chilli",
        "variety": "LCA-334 / Teja / Guntur Hope",
        "suitable_soils": ["black cotton soil", "red soil", "loamy soil", "black soil"],
        "suitable_seasons": ["kharif (monsoon)", "rabi (winter)", "monsoon", "kharif", "rabi"],
        "water_levels": ["good irrigation"],
        "duration_days": "150–180 Days",
        "water_requirement": "High / Controlled (Regular drip or furrow moisture)",
        "soil_suitability": "Deep, well-drained black cotton and loamy soils support continuous flowering and high dry-pod capsaicin yields.",
        "limitations": "Vulnerable to thrips, mites, and leaf curl complex; excessive standing water causes collar rot and wilt.",
        "next_steps": "Transplant 35-40 day old seedlings on raised beds; install yellow and blue sticky traps (20 each/acre); maintain ridge drainage.",
        "citation": "Dr. YSR Horticultural University & Spices Board India Regional Advisory",
        "publication_date": "2025-2026 Dr. YSRHU & Spices Board Bulletin",
        "applicable_regions": ["Andhra Pradesh", "Guntur", "Nellore", "Khammam", "Telangana", "Warangal"],
        "suitable_season": "Kharif & Rabi",
        "suitability_score": "High Suitability (Commercial Cash Crop)",
        "cultivation_guidance": "Transplant at 60 cm x 45 cm. Apply balanced NPK 120:60:60 kg/ha with micronutrient sprays at 45 and 75 DAP."
    },
    {
        "crop_name": "Paddy (Rice)",
        "variety": "BPT-5204 (Samba Mahsuri) / Telangana Sona (RNR-15048) / MTU-1010",
        "suitable_soils": ["clay soil", "black cotton soil", "heavy loamy soil", "black soil"],
        "suitable_seasons": ["kharif (monsoon)", "rabi (winter)", "monsoon", "kharif", "rabi"],
        "water_levels": ["good irrigation"],
        "duration_days": "125–140 Days",
        "water_requirement": "High (Submerged / Alternate Wetting and Drying)",
        "soil_suitability": "Heavy black cotton and clay soils in canal and borewell irrigated command areas retain water with minimal percolation loss.",
        "limitations": "Susceptible to blast disease and brown planthopper (BPH) under dense planting and excessive nitrogen.",
        "next_steps": "Transplant 25-day seedlings with 2-3 seedlings per hill; practice Alternate Wetting and Drying (AWD) to save 25% water.",
        "citation": "PJTSAU Rice Research Station, Rajendranagar & ICAR-IIRR Hyderabad",
        "publication_date": "2025-2026 State Agriculture University Compendium",
        "applicable_regions": ["Nellore", "Andhra Pradesh", "Telangana", "Coastal Andhra", "Nizamabad"],
        "suitable_season": "Kharif & Rabi",
        "suitability_score": "High Suitability (Staple Command Area Crop)",
        "cultivation_guidance": "Maintain 20 cm x 15 cm spacing. Apply 100:60:40 kg/ha NPK with split nitrogen applications at tillering and panicle initiation."
    },
    {
        "crop_name": "Cotton",
        "variety": "Bt Hybrid / Non-Bt Desi Varieties",
        "suitable_soils": ["black cotton soil", "clay soil", "deep loamy soil", "black soil"],
        "suitable_seasons": ["kharif (monsoon)", "monsoon", "kharif"],
        "water_levels": ["good irrigation", "limited irrigation"],
        "duration_days": "150–180 Days",
        "water_requirement": "Moderate (Critical during flowering and boll formation)",
        "soil_suitability": "Deep black soils offer high water retention capacity essential for deep taproot anchorage and steady boll development.",
        "limitations": "Susceptible to waterlogging in poorly drained flat fields; requires monitoring for pink bollworm and sucking pests.",
        "next_steps": "Establish ridge-and-furrow planting for drainage; install pheromone traps at 45 days after sowing.",
        "citation": "PJTSAU Kharif Crop Production Guide & RARS Warangal Cotton Advisory",
        "publication_date": "2025-2026 PJTSAU University Compendium",
        "applicable_regions": ["Telangana", "Andhra Pradesh", "Maharashtra (Vidarbha)", "Karnataka"],
        "suitable_season": "Kharif (Monsoon)",
        "suitability_score": "High Suitability (Rainfed/Irrigated Commercial)",
        "cultivation_guidance": "Sow at 90 cm x 60 cm. Intercrop with red gram (1:4 ratio) for risk hedging and soil fertility enhancement."
    },
    {
        "crop_name": "Groundnut",
        "variety": "Kadiri-6 (K-6) / Dharani / TAG-24",
        "suitable_soils": ["red soil", "sandy soil", "loamy soil", "red sandy loam"],
        "suitable_seasons": ["rabi (winter)", "kharif (monsoon)", "winter", "kharif"],
        "water_levels": ["good irrigation", "limited irrigation"],
        "duration_days": "105–115 Days",
        "water_requirement": "Moderate (Peg penetration & pod development stages)",
        "soil_suitability": "Loose, friable red sandy soils and light loams allow easy gynophore (peg) penetration and clean pod lifting during harvest.",
        "limitations": "Calcium deficiency in light soils causes empty pods ('pops'); leaf spot (Tikka disease) during humid spells.",
        "next_steps": "Apply gypsum at 500 kg/ha at pegging stage (40-45 DAS); inspect foliage regularly for leaf miner and tikka spots.",
        "citation": "ICAR-Directorate of Groundnut Research & RARS Tirupati",
        "publication_date": "2025-2026 ICAR-DGR & ANGRAU Regional Recommendations",
        "applicable_regions": ["Andhra Pradesh", "Nellore", "Rayalaseema", "Telangana", "Tamil Nadu"],
        "suitable_season": "Rabi & Kharif",
        "suitability_score": "High Suitability (Oilseed Reference)",
        "cultivation_guidance": "Sow at 30 cm x 10 cm. Treat seeds with Trichoderma viride (10 g/kg) and Rhizobium culture."
    },
    {
        "crop_name": "Maize (Corn)",
        "variety": "DHM-117 / Pioneer Hybrid / Kaveri 50",
        "suitable_soils": ["loamy soil", "black cotton soil", "red soil", "clay soil", "black soil"],
        "suitable_seasons": ["kharif (monsoon)", "rabi (winter)", "monsoon", "kharif", "rabi"],
        "water_levels": ["good irrigation", "limited irrigation"],
        "duration_days": "100–115 Days",
        "water_requirement": "Moderate (Critical at knee-high, tasseling, and grain filling)",
        "soil_suitability": "Fertile, well-drained loamy and black soils with good aeration promote high cob weight and grain filling.",
        "limitations": "Fall armyworm (Spodoptera frugiperda) damage in early whorl stage; sensitive to water stagnation.",
        "next_steps": "Apply neem-based formulations or pheromone traps for fall armyworm; ensure field drainage channels.",
        "citation": "ICAR-Indian Institute of Maize Research & ANGRAU/PJTSAU Package of Practices",
        "publication_date": "2025-2026 University Package of Practices",
        "applicable_regions": ["Andhra Pradesh", "Telangana", "Karnataka", "Nellore", "Warangal"],
        "suitable_season": "Kharif & Rabi",
        "suitability_score": "High Suitability (Cereal & Fodder)",
        "cultivation_guidance": "Sow at 60 cm x 20 cm spacing. Balanced fertilizer 120:60:50 kg/ha NPK with zinc sulfate at 25 kg/ha."
    },
    {
        "crop_name": "Red Gram (Pigeonpea)",
        "variety": "PRG-176 / Asha (ICPL-87119) / LRG-52",
        "suitable_soils": ["red soil", "loamy soil", "sandy soil", "black cotton soil", "red sandy loam"],
        "suitable_seasons": ["kharif (monsoon)", "monsoon", "kharif"],
        "water_levels": ["limited irrigation", "rain-dependent"],
        "duration_days": "160–180 Days",
        "water_requirement": "Low to Moderate (Drought hardy deep taproot)",
        "soil_suitability": "Deep red sandy loams and light black soils allow deep root penetration without water-logging risk.",
        "limitations": "Sterility mosaic disease and pod borer; prolonged cloudy weather during pod formation reduces set.",
        "next_steps": "Intercrop with cotton or maize (1:4 ratio); nip terminal shoots at 45-50 days to encourage profuse branching.",
        "citation": "PJTSAU Pulse Research Center & ICAR-CRIDA Rainfed Farming Guide",
        "publication_date": "2025-2026 Rainfed Pulses Guide",
        "applicable_regions": ["Telangana", "Andhra Pradesh", "Karnataka"],
        "suitable_season": "Kharif (Monsoon)",
        "suitability_score": "High Suitability (Drought Hardy Legume)",
        "cultivation_guidance": "Sow at 90-120 cm x 20 cm spacing. Apply 20 kg N and 50 kg P2O5 at sowing time."
    },
    {
        "crop_name": "Soybean",
        "variety": "JS-335 / JS-9305 / DSb-21",
        "suitable_soils": ["black cotton soil", "loamy soil", "clay soil", "black soil"],
        "suitable_seasons": ["kharif (monsoon)", "monsoon", "kharif"],
        "water_levels": ["good irrigation", "limited irrigation", "rain-dependent"],
        "duration_days": "90–100 Days",
        "water_requirement": "Moderate (Sensitive during flowering and pod filling)",
        "soil_suitability": "Well-drained black and loamy soils with neutral pH facilitate effective Rhizobium nodulation and rapid vegetative growth.",
        "limitations": "Short harvest window; prolonged rains at maturity may cause pod shattering and seed quality degradation.",
        "next_steps": "Inoculate seeds with Rhizobium and PSB culture; maintain broad-bed furrow system for drainage.",
        "citation": "ICAR-Indian Institute of Soybean Research (IISR) & State Dept of Agriculture",
        "publication_date": "2025-2026 Annual Package of Practices",
        "applicable_regions": ["Telangana", "Maharashtra", "Madhya Pradesh", "Karnataka"],
        "suitable_season": "Kharif (Monsoon)",
        "suitability_score": "High Suitability (Short Duration Legume)",
        "cultivation_guidance": "Sow at 45 cm x 5-7 cm. Inoculate with Rhizobium culture. Harvest when 90% leaves turn yellow and drop."
    },
    {
        "crop_name": "Tomato",
        "variety": "Arka Rakshak / Pusa Ruby / US-618",
        "suitable_soils": ["red soil", "loamy soil", "sandy soil", "red sandy loam"],
        "suitable_seasons": ["rabi (winter)", "kharif (monsoon)", "winter", "kharif", "zaid (summer)"],
        "water_levels": ["good irrigation"],
        "duration_days": "110–130 Days",
        "water_requirement": "High / Controlled (Regular drip irrigation)",
        "soil_suitability": "Well-aerated fertile red sandy loam with good organic matter and slightly acidic to neutral pH.",
        "limitations": "Susceptible to bacterial wilt and tomato leaf curl virus; requires staking and fruit protection.",
        "next_steps": "Raise nursery under net house; transplant 25-day seedlings on raised beds with silver-black mulch.",
        "citation": "ICAR-Indian Institute of Horticultural Research (IIHR) Bengaluru",
        "publication_date": "2025-2026 IIHR Commercial Vegetable Guide",
        "applicable_regions": ["Andhra Pradesh", "Karnataka", "Telangana", "Tamil Nadu"],
        "suitable_season": "Rabi & Kharif",
        "suitability_score": "High Suitability (High-Value Horticulture)",
        "cultivation_guidance": "Transplant at 75 cm x 45 cm with bamboo/trellis staking. Fertigate NPK weekly through drip."
    },
    {
        "crop_name": "Watermelon",
        "variety": "Sugar Baby / Arka Manik / Black Boss",
        "suitable_soils": ["sandy soil", "loamy soil", "red soil", "red sandy loam"],
        "suitable_seasons": ["zaid (summer)", "summer", "zaid", "rabi (winter)"],
        "water_levels": ["good irrigation"],
        "duration_days": "80–95 Days",
        "water_requirement": "Moderate to High (Critical at fruit enlargement)",
        "soil_suitability": "Deep, loose sandy loams and riverbed soils warm up quickly and promote early root expansion and high sugar accumulation.",
        "limitations": "Susceptible to powdery mildew and fruit fly attack; excess nitrogen causes fruit cracking.",
        "next_steps": "Sow on raised beds with drip irrigation and plastic mulching; install fruit fly pheromone traps.",
        "citation": "ICAR-IIHR Vegetable Crops Compendium & AP Horticulture Dept",
        "publication_date": "2025-2026 Commercial Melons Bulletin",
        "applicable_regions": ["Andhra Pradesh", "Nellore", "Telangana", "Tamil Nadu", "Karnataka"],
        "suitable_season": "Zaid (Summer)",
        "suitability_score": "High Suitability (Summer Cash Crop)",
        "cultivation_guidance": "Pit or channel sowing at 2m x 1m. Stop watering 5-7 days before harvest to enhance sweetness."
    },
    {
        "crop_name": "Sesame (Til)",
        "variety": "Swetha / YLM-66 / Rajeswari",
        "suitable_soils": ["sandy soil", "red soil", "loamy soil", "red sandy loam"],
        "suitable_seasons": ["zaid (summer)", "summer", "zaid", "rabi (winter)", "kharif"],
        "water_levels": ["limited irrigation", "rain-dependent", "good irrigation"],
        "duration_days": "80–90 Days",
        "water_requirement": "Low (Drought tolerant after establishment)",
        "soil_suitability": "Light sandy and well-drained loamy soils prevent water stagnation and root rot.",
        "limitations": "Extremely sensitive to waterlogging even for a few hours; capsule borer damage during maturation.",
        "next_steps": "Sow with fine sand mixture for uniform stand; ensure surface field drains are open.",
        "citation": "ANGRAU Oilseeds Research Station, Yellamanchili & PJTSAU Bulletin",
        "publication_date": "2025-2026 Oilseeds Agronomy Compendium",
        "applicable_regions": ["Andhra Pradesh", "Nellore", "Telangana", "Coastal Andhra"],
        "suitable_season": "Summer (Zaid) & Rabi",
        "suitability_score": "High Suitability (Low Water Requirement)",
        "cultivation_guidance": "Sow at 30 cm x 10 cm. Mix seed with sand (1:4 ratio) for even sowing. One weeding at 20 DAS."
    }
]

# Keep alias for backward compatibility with previous test imports
UNVERIFIED_CROP_REFERENCE_DATA = DEMO_CROP_REFERENCE_DATA

# Small, explicit district/state map used only to detect conflicting location
# inputs. It does not silently rewrite farmer-provided state or district values.
DISTRICT_STATE_MAP = {
    "nellore": "andhra pradesh",
    "guntur": "andhra pradesh",
    "warangal": "telangana",
    "khammam": "telangana",
    "adilabad": "telangana",
    "nizamabad": "telangana",
}


class CropAdvisorService:
    @staticmethod
    def get_recommendations(
        soil: str,
        water: str,
        season: str,
        district: Optional[str] = None,
        state: Optional[str] = None
    ) -> CropAdvisorResponse:
        s_norm = (soil or "").strip().lower()
        w_norm = (water or "").strip().lower()
        sea_norm = (season or "").strip().lower()
        dist_norm = (district or "").strip().lower()
        state_norm = (state or "").strip().lower()
        expected_state = DISTRICT_STATE_MAP.get(dist_norm)
        location_conflict = bool(expected_state and state_norm and state_norm != expected_state)
        # Avoid using a conflicting state to boost unrelated regional records.
        if location_conflict:
            state_norm = ""

        # Guard: Unspecified, "don't know", or "unknown" soil types
        if not s_norm or s_norm in ("don't know", "dont know", "other", "unknown"):
            return CropAdvisorResponse(
                recommendations=[],
                total_found=0,
                soil_type=soil,
                growing_season=season,
                water_availability=water,
                disclaimer=(
                    "Soil type is unknown or not specified. Agricultural universities require verified soil physical properties "
                    "(e.g., Black Cotton Soil, Red Sandy Loam, Clay Loam) to provide evidence-backed crop recommendations. "
                    "Please conduct a soil health test or consult your local Krishi Vigyan Kendra (KVK) for advice."
                )
            )

        matches = []
        for item in DEMO_CROP_REFERENCE_DATA:
            score = 0

            # 1. Soil matching
            soil_matched = False
            for s in item["suitable_soils"]:
                if s in s_norm or s_norm in s:
                    soil_matched = True
                    score += 5
                    break
                # Semantic / group matching
                if ("black" in s_norm and "black" in s) or \
                   ("clay" in s_norm and "clay" in s) or \
                   ("red" in s_norm and "red" in s) or \
                   ("sand" in s_norm and "sand" in s) or \
                   ("loam" in s_norm and "loam" in s):
                    soil_matched = True
                    score += 4
                    break

            if not soil_matched:
                continue

            # 2. Season matching
            season_matched = False
            for sea in item["suitable_seasons"]:
                if sea in sea_norm or sea_norm in sea:
                    season_matched = True
                    score += 4
                    break
                if ("rabi" in sea_norm and "rabi" in sea) or \
                   ("winter" in sea_norm and "winter" in sea) or \
                   ("kharif" in sea_norm and "kharif" in sea) or \
                   ("monsoon" in sea_norm and "monsoon" in sea) or \
                   ("zaid" in sea_norm and "zaid" in sea) or \
                   ("summer" in sea_norm and "summer" in sea):
                    season_matched = True
                    score += 3
                    break

            if not season_matched:
                continue

            # 3. Water availability matching
            water_matched = False
            for w in item["water_levels"]:
                if w in w_norm or w_norm in w:
                    water_matched = True
                    score += 3
                    break
                if ("good" in w_norm and "good" in w) or \
                   ("limited" in w_norm and ("limited" in w or "rain-dependent" in w)) or \
                   ("rain" in w_norm and ("rain-dependent" in w or "limited" in w)):
                    water_matched = True
                    score += 2
                    break

            if not water_matched:
                # Mild penalty if water isn't ideal but soil & season match
                score -= 1

            # 4. Regional / District / State relevance bonus
            if dist_norm:
                for reg in item.get("applicable_regions", []):
                    if dist_norm in reg.lower() or reg.lower() in dist_norm:
                        score += 3
                        break

            if state_norm:
                for reg in item.get("applicable_regions", []):
                    if state_norm in reg.lower() or reg.lower() in state_norm:
                        score += 2
                        break

            matches.append((score, item))

        # Sort by highest agronomic match score
        matches.sort(key=lambda x: x[0], reverse=True)
        top_items = matches[:3]

        loc_str = f" in {district}" if district and district.strip() and "Default" not in district else ""

        if top_items:
            recs = [
                CropRecommendation(
                    crop_name=item["crop_name"],
                    variety=item["variety"],
                    duration_days=item["duration_days"],
                    water_requirement=item["water_requirement"],
                    soil_suitability=item["soil_suitability"],
                    limitations=item["limitations"],
                    next_steps=item["next_steps"],
                    citation=f"Demo reference only; attribution is unverified: {item['citation']}",
                    publication_date=item.get("publication_date"),
                    applicable_regions=item.get("applicable_regions", []),
                    suitability_score=item.get("suitability_score", "High Suitability (Demo Reference)"),
                    suitable_season=item.get("suitable_season", season),
                    cultivation_guidance=item.get("cultivation_guidance", item.get("next_steps"))
                )
                for _, item in top_items
            ]
            disclaimer = (
                f"DEMO reference agronomic suggestions{loc_str}; these are not scientifically verified or guaranteed recommendations. "
                "Verify certified seed availability, sowing dates, and local soil conditions with your Mandal Agriculture Officer or local Krishi Vigyan Kendra (KVK)."
            )
            if location_conflict:
                disclaimer += (
                    f" Location check: {district} is associated with {expected_state.title()}, but the request specified {state}. "
                    "The suggestions use soil, water, season, and district matches only; confirm the correct state and local suitability."
                )
        else:
            recs = []
            disclaimer = (
                f"No specific reference crop matches found for {soil} in {season}{loc_str}. "
                "Please verify your soil parameters or consult your local Krishi Vigyan Kendra (KVK) for specialized guidance."
            )

        return CropAdvisorResponse(
            recommendations=recs,
            total_found=len(recs),
            soil_type=soil,
            growing_season=season,
            water_availability=water,
            disclaimer=disclaimer
        )
