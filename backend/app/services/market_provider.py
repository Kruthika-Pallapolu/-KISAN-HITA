"""Read-only provider for the locally maintained illustrative price table.

This provider performs no network requests and never represents the rows as
reported mandi observations.
"""
import csv
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional


class MarketProviderError(RuntimeError):
    def __init__(self, code: str, message: str, http_status: int = 503):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status


DATASET_PATH = Path(__file__).resolve().parents[1] / "data/district_commodity_illustrative_prices.csv"
ILLUSTRATIVE_PROVENANCE = (
    "Synthetic reference generated deterministically from project crop price bands and the in-project LGD district directory; "
    "not an actual market observation, auction result, or official price."
)


@lru_cache(maxsize=1)
def _load_rows() -> tuple[dict[str, str], ...]:
    with DATASET_PATH.open(encoding="utf-8", newline="") as stream:
        return tuple(dict(row) for row in csv.DictReader(stream))


class LocalIllustrativeMarketProvider:
    async def fetch(self, filters: dict[str, Optional[str]]) -> tuple[list[dict[str, Any]], dict[str, str]]:
        rows = list(_load_rows())
        district_filter = " ".join((filters.get("district") or "").casefold().split())
        state_filter = " ".join((filters.get("state") or "").casefold().split())
        if district_filter and not state_filter:
            matching_states = {row["state"] for row in rows if " ".join(row["district"].casefold().split()) == district_filter}
            # Resolve a district-only request only when the authoritative
            # directory makes it unambiguous; duplicate names require a state.
            if len(matching_states) != 1:
                return [], {"provenance": ILLUSTRATIVE_PROVENANCE}
            state_filter = next(iter(matching_states)).casefold()
        for field in ("state", "district", "commodity", "variety", "mandi"):
            wanted = " ".join((filters.get(field) or "").casefold().split())
            if field == "state" and state_filter:
                wanted = state_filter
            if not wanted:
                continue
            if field == "mandi":
                # There are district-level estimates, not fabricated mandi identities.
                return [], {"provenance": ILLUSTRATIVE_PROVENANCE}
            if field == "commodity":
                aliases = {"chilli": "chilli (dry)", "chili": "chilli (dry)", "mirchi": "chilli (dry)", "bengal gram": "gram (chana)", "chana": "gram (chana)"}
                wanted = aliases.get(wanted, wanted)
                field = "commodity"
            rows = [row for row in rows if " ".join((row.get(field) or "").casefold().split()) == wanted]
        return rows, {"provenance": ILLUSTRATIVE_PROVENANCE}
