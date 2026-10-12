# scraping-bot: an automatic repricing bot for Kaspi.kz sellers

A Python bot that keeps a seller's prices competitive on [Kaspi.kz](https://kaspi.kz), Kazakhstan's
largest marketplace. It signs in to the seller cabinet with a headless browser, walks through every
active product, looks up the lowest competitor price on the product page, and lowers the seller's
price to match, but never below a minimum price set per product.

I built it in spring 2025 as my first Kaspi automation.

## How it works

1. **Signs in** to the Kaspi seller cabinet (`kaspi.kz/mc`) with Playwright.
2. **Collects products.** It pages through the active product list and reads each product's name,
   SKU, current price and link.
3. **Checks the competition.** It opens each product's public page and reads the best offer price.
4. **Reprices.** If a competitor is cheaper, it opens the offer editor in the cabinet and sets the
   new price, respecting the product's minimum price and price step.
5. **Stores state.** Each product's current price, minimum price, step and price decrease are kept
   in a database, so the rules can be tuned per product.

## Versions in this repository

The scripts show how the storage evolved:

| Storage | Scripts |
|---|---|
| Excel workbook | `kaspi-price.py`, `kaspi-price-cur.py`, `kaspi_price_adjustment.py`, `kaspu-bot-check.py` |
| PostgreSQL | `kaspi_bot_sql.py`, `gpt_sql_sec.py`, `gpt_sql_fir.py` (the most complete SQL version) |
| MongoDB | `py_bot_mongo.py`: the latest version (April 2025) |

## Stack

Python 3.10 · asyncio · Playwright (Chromium) · PostgreSQL (psycopg2) · MongoDB (pymongo) · openpyxl

## Running it

```bash
python3.10 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
cp .env.example .env              # Kaspi cabinet login and database password
set -a; source .env; set +a
python py_bot_mongo.py            # needs MongoDB on localhost:27017
```

It needs a real Kaspi seller account. Selectors target the Kaspi cabinet as it was in 2025 and may
need updating.

## Author

**Ratmir Akimov**: [github.com/AkimovRatmir](https://github.com/AkimovRatmir)

## License

All rights reserved. The code is published for viewing only. See [LICENSE](LICENSE).
