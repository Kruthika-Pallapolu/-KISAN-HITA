"""Offline coverage tests for the generated illustrative market dataset."""
import asyncio
import csv
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from auth_helpers import authenticated_client
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.main import app
from app.services.market_provider import DATASET_PATH, ILLUSTRATIVE_PROVENANCE, LocalIllustrativeMarketProvider
from app.services.market_service import KNOWN_COMMODITIES, MarketPriceService
from backend.scripts.generate_market_price_dataset import render_dataset

ROOT = Path(__file__).resolve().parents[2]
GEO_PATH = ROOT / "frontend/src/data/indiaAdminLgd.json"

class TestLocalIllustrativeMarketDataset(unittest.TestCase):
    def test_complete_generated_coverage_codes_and_deterministic_prices(self):
        geography = json.loads(GEO_PATH.read_text(encoding="utf-8"))
        with DATASET_PATH.open(encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
        with (ROOT / "backend/app/data/crop_price_bands.csv").open(encoding="utf-8", newline="") as stream:
            configured_bands = {row["crop"]: row for row in csv.DictReader(stream)}
        expected = len(geography["districts"]) * len(KNOWN_COMMODITIES)
        self.assertEqual((len(geography["states"]), len(geography["districts"])), (36, 784))
        self.assertEqual(len(KNOWN_COMMODITIES), 32)
        self.assertEqual(len(rows), expected)
        valid_pairs = {(s["code"], s["name"]) for s in geography["states"]}
        district_map = {(d["stateCode"], d["lgdCode"]): d["name"] for d in geography["districts"]}
        keys = set()
        values = {}
        for row in rows:
            self.assertIn((row["state_code"], row["state"]), valid_pairs)
            self.assertEqual(district_map[(row["state_code"], int(row["district_code"]))], row["district"])
            key = (row["state_code"], row["district_code"], row["commodity"])
            self.assertNotIn(key, keys)
            keys.add(key)
            low, modal, high = (float(row[k]) for k in ("min_price_inr_per_kg", "modal_price_inr_per_kg", "max_price_inr_per_kg"))
            self.assertLessEqual(low, modal); self.assertLessEqual(modal, high)
            band = configured_bands[row["commodity"]]
            self.assertGreaterEqual(low, float(band["base_min_inr_per_kg"]))
            self.assertLessEqual(high, float(band["base_max_inr_per_kg"]))
            self.assertEqual(row["unit"], "INR/kg"); self.assertEqual(row["data_type"], "illustrative")
            values[key] = modal
        self.assertEqual(len(keys), expected)
        self.assertEqual(render_dataset(), DATASET_PATH.read_text(encoding="utf-8"))
        # Stable LGD codes yield repeatable, district-specific values.
        cotton = {(r["state_code"], r["district_code"]): float(r["modal_price_inr_per_kg"]) for r in rows if r["commodity"] == "Cotton"}
        self.assertNotEqual(cotton[("28", "515")], cotton[("28", "506")])
        self.assertIn("not an actual market observation", ILLUSTRATIVE_PROVENANCE)

    def test_catalogue_retains_original_22_and_adds_requested_vegetables(self):
        self.assertEqual(len(KNOWN_COMMODITIES), 32)
        self.assertTrue({"Tomato", "Chilli (dry)", "Potato", "Cabbage", "Brinjal", "Cauliflower", "Okra", "Bottle gourd", "Bitter gourd", "Cucumber", "Pumpkin", "Spinach", "Beans", "Drumstick"}.issubset(KNOWN_COMMODITIES))

    def test_exact_state_district_commodity_filtering_and_no_substitution(self):
        async def run():
            combos = [
                ("Andhra Pradesh", "Nellore"), ("Andhra Pradesh", "Guntur"),
                ("Telangana", "Hyderabad"), ("Haryana", "Karnal"),
                ("Bihar", "Aurangabad"), ("Maharashtra", "Chhatrapati Sambhajinagar"),
            ]
            valid = [await MarketPriceService.get_market_prices("Cotton", state, district) for state, district in combos]
            wrong_state = await MarketPriceService.get_market_prices("Cotton", "Andhra Pradesh", "Hyderabad")
            wrong_district = await MarketPriceService.get_market_prices("Cotton", "Haryana", "Nellore")
            ap = await MarketPriceService.get_market_prices("Cotton", "Andhra Pradesh", "Nellore")
            other_district = await MarketPriceService.get_market_prices("Cotton", "Andhra Pradesh", "Guntur")
            state_only = await MarketPriceService.get_market_prices("Cotton", "Haryana")
            unqualified = await MarketPriceService.get_market_prices("Cotton", district="Aurangabad")
            duplicate_unqualified = await MarketPriceService.get_market_prices("Cotton", district="Bilaspur")
            duplicate_state = await MarketPriceService.get_market_prices("Cotton", "Himachal Pradesh", "Bilaspur")
            unsupported = await MarketPriceService.get_market_prices("Not a crop", "Andhra Pradesh", "Nellore")
            alias = await MarketPriceService.get_market_prices("Chilli", "Andhra Pradesh", "Nellore")
            return combos, valid, ap, wrong_state, wrong_district, other_district, state_only, unqualified, duplicate_unqualified, duplicate_state, unsupported, alias
        combos, valid, ap, wrong, wrong_district, guntur, haryana, unqualified, duplicate_unqualified, duplicate_state, unsupported, alias = asyncio.run(run())
        for (state, district), result in zip(combos, valid):
            self.assertTrue(result.records, f"missing {state}/{district}")
            self.assertEqual({(r.state, r.district) for r in result.records}, {(state, district)})
        self.assertEqual({r.district for r in ap.records}, {"Nellore"})
        self.assertEqual({r.state for r in ap.records}, {"Andhra Pradesh"})
        self.assertFalse(wrong.records); self.assertFalse(wrong_district.records)
        self.assertEqual({r.state for r in unqualified.records}, {"Bihar"}); self.assertFalse(unsupported.records)
        self.assertFalse(duplicate_unqualified.records)
        self.assertEqual({(r.state, r.district) for r in duplicate_state.records}, {("Himachal Pradesh", "Bilaspur")})
        self.assertEqual({r.district for r in guntur.records}, {"Guntur"})
        self.assertTrue(haryana.records); self.assertEqual({r.state for r in haryana.records}, {"Haryana"})
        self.assertTrue(alias.records); self.assertEqual(alias.records[0].commodity, "Chilli (dry)")

    def test_mandi_and_variety_filters_do_not_invent_market_identity(self):
        async def run():
            return await MarketPriceService.get_market_prices("Tomato", "Andhra Pradesh", "Nellore", mandi="Nellore APMC"), await MarketPriceService.get_market_prices("Tomato", "Andhra Pradesh", "Nellore", variety="Local")
        mandi, variety = asyncio.run(run())
        self.assertFalse(mandi.records); self.assertFalse(variety.records)
        self.assertIn("does not contain mandi-specific", mandi.disclaimer)

    def test_response_has_demo_metadata_and_no_fake_market_date_or_source_url(self):
        result = asyncio.run(MarketPriceService.get_market_prices("Cotton", "Andhra Pradesh", "Nellore"))
        self.assertFalse(result.is_live_api); self.assertEqual(result.data_type, "illustrative")
        self.assertIn("DEMO DATA", result.disclaimer)
        self.assertIsNone(result.source_url); self.assertIsNone(result.retrieved_at)
        self.assertTrue(result.records)
        for record in result.records:
            self.assertEqual(record.data_type, "illustrative")
            self.assertIsNone(record.market); self.assertIsNone(record.record_date)
            self.assertIsNone(record.source_url); self.assertEqual(record.unit, "kg")
            self.assertIn("not an actual market observation", record.source)

    def test_provider_does_not_make_http_requests(self):
        async def run():
            with patch("httpx.AsyncClient", side_effect=AssertionError("unexpected market network request")):
                return await LocalIllustrativeMarketProvider().fetch({"commodity":"Cotton", "state":"Andhra Pradesh", "district":"Nellore"})
        rows, metadata = asyncio.run(run())
        self.assertEqual(len(rows), 1); self.assertIn("Synthetic reference", metadata["provenance"])

    def test_authenticated_endpoints_return_all_commodities_and_local_records(self):
        client = authenticated_client(app)
        try:
            catalogue = client.get("/api/market-prices/commodities")
            self.assertEqual(catalogue.status_code, 200)
            self.assertEqual(catalogue.json()["commodities"], KNOWN_COMMODITIES)
            self.assertEqual(len(catalogue.json()["commodities"]), 32)
            response = client.get("/api/market-prices/search", params={"commodity":"Cotton", "state":"Andhra Pradesh", "district":"Nellore"})
            self.assertEqual(response.status_code, 200, response.text)
            payload = response.json()
            self.assertFalse(payload["is_live_api"]); self.assertEqual(payload["data_type"], "illustrative")
            self.assertEqual({row["district"] for row in payload["records"]}, {"Nellore"})
            self.assertIsNone(payload["records"][0]["market"])
            self.assertIn("DEMO DATA", payload["disclaimer"])
        finally:
            client.close()
