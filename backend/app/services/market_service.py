"""Exact filtering and response mapping for local illustrative market prices."""
import csv
from pathlib import Path
from typing import Optional

from ..models.schemas import MandiPriceItem, MarketPriceResponse
from .market_provider import ILLUSTRATIVE_PROVENANCE, LocalIllustrativeMarketProvider, MarketProviderError

_BANDS_PATH = Path(__file__).resolve().parents[1] / "data/crop_price_bands.csv"
with _BANDS_PATH.open(encoding="utf-8", newline="") as _stream:
    KNOWN_COMMODITIES = [row["crop"] for row in csv.DictReader(_stream)]

class MarketPriceService:
    """Returns deterministic local reference prices, never live mandi observations."""
    provider = LocalIllustrativeMarketProvider()

    @classmethod
    async def get_market_prices(cls, commodity: Optional[str] = None, state: Optional[str] = None,
                                district: Optional[str] = None, mandi: Optional[str] = None,
                                variety: Optional[str] = None, language: str = "en") -> MarketPriceResponse:
        query = (commodity or "").strip()
        if not query:
            raise MarketProviderError("invalid_input", "Choose a commodity before searching.", http_status=422)
        clean = lambda value: value.strip() if value and value.strip().casefold() != "all" else None
        filters = {"commodity": query, "state": clean(state), "district": clean(district),
                   "mandi": clean(mandi), "variety": clean(variety)}
        raw_records, _ = await cls.provider.fetch(filters)
        records = []
        for row in raw_records:
            try:
                low = float(row["min_price_inr_per_kg"])
                modal = float(row["modal_price_inr_per_kg"])
                high = float(row["max_price_inr_per_kg"])
                if not (0 <= low <= modal <= high):
                    continue
                records.append(MandiPriceItem(
                    commodity=row["commodity"], variety=row.get("variety") or None, grade=None,
                    market=None, district=row["district"], state=row["state"],
                    state_code=row["state_code"], district_code=row["district_code"],
                    min_price_per_kg=low, modal_price_per_kg=modal, max_price_per_kg=high,
                    currency="INR", unit="kg", reported_unit="INR/kg", data_type="illustrative",
                    record_date=None, freshness="illustrative", source=ILLUSTRATIVE_PROVENANCE,
                    source_url=None, retrieved_at=None,
                    disclaimer="Illustrative synthetic reference only; not a live, verified, official, or reported mandi price.",
                ))
            except (KeyError, TypeError, ValueError):
                continue
        resolved_state = filters["state"] or (records[0].state if records else None)
        location = ", ".join(x for x in (filters["district"], resolved_state) if x)
        if filters["mandi"]:
            explanation = "This local dataset contains district-level illustrative references and does not contain mandi-specific observations."
        elif filters["district"] and not filters["state"]:
            explanation = "Select the state as well as the district to avoid an ambiguous location."
        elif not records:
            explanation = "No illustrative reference matches these exact selections. No other district or state was substituted."
        else:
            explanation = "These deterministic synthetic values are illustrative references only, not live or verified mandi prices."
        return MarketPriceResponse(
            records=records, total_count=len(records),
            disclaimer=f"DEMO DATA — {explanation} No other district or state was substituted." + (f" Location: {location}." if location else ""),
            last_updated="Local illustrative dataset; no market reporting date",
            data_provenance=ILLUSTRATIVE_PROVENANCE, is_live_api=False,
            data_type="illustrative", retrieved_at=None, source_url=None, related_source_url=None,
        )
