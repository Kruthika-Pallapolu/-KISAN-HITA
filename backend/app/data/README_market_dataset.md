# Illustrative market price dataset

`district_commodity_illustrative_prices.csv` is generated locally by
`backend/scripts/generate_market_price_dataset.py` from `crop_price_bands.csv`
and the project's `frontend/src/data/indiaAdminLgd.json` directory. The bands
are prototype reference values, not sourced from mandi observations. Stable
state code, district LGD code and commodity name feed SHA-256-based generation,
so regeneration is deterministic. The file contains one row per directory
district and supported commodity, in INR/kg.

These values must always be presented as DEMO / illustrative data. They have no
real mandi identity, market reporting date, official attribution or live status.
The backend reads this checked-in local CSV and performs no market-price
network requests.
