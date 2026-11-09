"""Generate the fixed, illustrative district × commodity price table.

The values are synthetic reference bands, not observations or market quotes.
Run from the repository root with Python's standard library only.
"""
import csv
import hashlib
import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GEO = ROOT / "frontend/src/data/indiaAdminLgd.json"
BANDS = ROOT / "backend/app/data/crop_price_bands.csv"
OUTPUT = ROOT / "backend/app/data/district_commodity_illustrative_prices.csv"
FIELDS = ["state", "state_code", "district", "district_code", "commodity", "variety", "min_price_inr_per_kg", "modal_price_inr_per_kg", "max_price_inr_per_kg", "unit", "data_type", "provenance"]

def render_dataset() -> str:
    geo = json.loads(GEO.read_text(encoding="utf-8"))
    states = {str(row["code"]): row["name"] for row in geo["states"]}
    with BANDS.open(encoding="utf-8", newline="") as stream:
        bands = list(csv.DictReader(stream))
    out = io.StringIO(newline="")
    writer = csv.DictWriter(out, fieldnames=FIELDS, lineterminator="\n")
    writer.writeheader()
    for district in sorted(geo["districts"], key=lambda row: (int(row["stateCode"]), int(row["lgdCode"]))):
        state_code = str(district["stateCode"])
        state = states[state_code]
        for band in bands:
            low = float(band["base_min_inr_per_kg"])
            base = float(band["base_modal_inr_per_kg"])
            high = float(band["base_max_inr_per_kg"])
            key = f'{state_code}:{district["lgdCode"]}:{band["crop"].casefold()}'.encode()
            digest = hashlib.sha256(key).digest()
            span = high - low
            modal = low + (int.from_bytes(digest[:4], "big") / 0xFFFFFFFF) * span
            # Blend a stable district-specific position with the configured band midpoint.
            modal = min(high, max(low, (modal * 0.65) + (base * 0.35)))
            spread = max(0.5, span * (0.08 + digest[4] / 2550))
            minimum = max(low, modal - spread)
            maximum = min(high, modal + spread)
            writer.writerow({
                "state": state, "state_code": state_code,
                "district": district["name"], "district_code": district["lgdCode"],
                "commodity": band["crop"], "variety": "",
                "min_price_inr_per_kg": f"{minimum:.2f}",
                "modal_price_inr_per_kg": f"{modal:.2f}",
                "max_price_inr_per_kg": f"{maximum:.2f}",
                "unit": "INR/kg", "data_type": "illustrative",
                "provenance": "Synthetic reference generated deterministically from the project's crop price bands and LGD district codes; not a market observation.",
            })
    return out.getvalue()

if __name__ == "__main__":
    OUTPUT.write_text(render_dataset(), encoding="utf-8", newline="")
    print(f"Wrote {sum(1 for _ in OUTPUT.open(encoding='utf-8')) - 1} illustrative rows to {OUTPUT}")
