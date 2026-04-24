"""
fetch_sefe.py — Scrape FR Power forwards from SEFE/EnergyMarketPrice API
Runs daily via GitHub Actions, appends to ppa_dashboard/data/sefe_forwards.csv
"""

import requests
import pandas as pd
from datetime import datetime, timezone
import os
import sys

# ── Config ────────────────────────────────────────────────────────────────────
AUTH_URL  = "https://cockpit.energymarketprice.com/api/Emp/PublicAuthorization?customLink=daily"
TABLE_URL = "https://cockpit.energymarketprice.com/api/StatisticTable/Table"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR   = os.path.join(SCRIPT_DIR, "data")
OUTPUT     = os.path.join(DATA_DIR, "sefe_forwards.csv")

HEADERS_BASE = {
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "Origin": "https://marketinsights.sefe-energy.com",
    "Referer": "https://marketinsights.sefe-energy.com/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}

# Full payload — FR Power baseload forwards
PAYLOAD = {
    "formulas": ["D-1", "Last", "VAR D-1, %", "VAR W-1, %"],
    "excludeWeekends": True,
    "excludeHolidays": True,
    "cockpitGuid": "169b4b92-d10a-41b1-b018-898c8b78ee06",
    "fullMarketsInfo": [
        {"marketId": 39645, "marketCode": "M+1", "marketName": "FR Sep24 base",
         "marketNameCode": "FR Sep24 base M+1", "commodity": "Power", "countryName": "France",
         "resourcesCode": None, "periodName": "Month", "typeName": "Base",
         "absolut": "Absolute", "currencyCode": "EUR", "unitNameCode": "MWh",
         "isLive": False, "rowId": "a1f60b38-5f36-49c3-b4e6-156ce2230294"},
        {"marketId": 44258, "marketCode": "M+2", "marketName": "FR Oct24 base",
         "marketNameCode": "FR Oct24 base M+2", "commodity": "Power", "countryName": "France",
         "resourcesCode": None, "periodName": "Month", "typeName": "Base",
         "absolut": "Absolute", "currencyCode": "EUR", "unitNameCode": "MWh",
         "isLive": False, "rowId": "61303e67-2e4d-4a59-b429-bf6b944edf20"},
        {"marketId": 39660, "marketCode": "M+3", "marketName": "FR Nov24 base",
         "marketNameCode": "FR Nov24 base M+3", "commodity": "Power", "countryName": "France",
         "resourcesCode": None, "periodName": "Month", "typeName": "Base",
         "absolut": "Absolute", "currencyCode": "EUR", "unitNameCode": "MWh",
         "isLive": False, "rowId": "ab54f3c8-ecf4-4f9d-a0ad-627efde2f345"},
        {"marketId": 39735, "marketCode": "Q+1", "marketName": "FR Q4 24 base",
         "marketNameCode": "FR Q4 24 base Q+1", "commodity": "Power", "countryName": "France",
         "resourcesCode": None, "periodName": "Quarter", "typeName": "Base",
         "absolut": "Absolute", "currencyCode": "EUR", "unitNameCode": "MWh",
         "isLive": False, "rowId": "874da3c2-78b5-417a-95c6-f3945a8d0d2e"},
        {"marketId": 39691, "marketCode": "Q+2", "marketName": "FR Q1 25 base",
         "marketNameCode": "FR Q1 25 base Q+2", "commodity": "Power", "countryName": "France",
         "resourcesCode": None, "periodName": "Quarter", "typeName": "Base",
         "absolut": "Absolute", "currencyCode": "EUR", "unitNameCode": "MWh",
         "isLive": False, "rowId": "afffde1f-e3d6-4a73-8c80-7333122816d2"},
        {"marketId": 39706, "marketCode": "Q+3", "marketName": "FR Q2 25 base",
         "marketNameCode": "FR Q2 25 base Q+3", "commodity": "Power", "countryName": "France",
         "resourcesCode": None, "periodName": "Quarter", "typeName": "Base",
         "absolut": "Absolute", "currencyCode": "EUR", "unitNameCode": "MWh",
         "isLive": False, "rowId": "32bbaa8c-6a3b-41d9-bcb0-090e6f6a08e3"},
        {"marketId": 69271, "marketCode": "S+1", "marketName": "FR Win2024 base",
         "marketNameCode": "FR Win2024 base S+1", "commodity": "Power", "countryName": "France",
         "resourcesCode": None, "periodName": "Season", "typeName": "Base",
         "absolut": "Absolute", "currencyCode": "EUR", "unitNameCode": "MWh",
         "isLive": False, "rowId": "efa88e3c-f1ef-4c44-b8f4-2d8793cce5fe"},
        {"marketId": 69273, "marketCode": "S+2", "marketName": "FR Sum2025 base",
         "marketNameCode": "FR Sum2025 base S+2", "commodity": "Power", "countryName": "France",
         "resourcesCode": None, "periodName": "Season", "typeName": "Base",
         "absolut": "Absolute", "currencyCode": "EUR", "unitNameCode": "MWh",
         "isLive": False, "rowId": "7a860f06-1a7b-455c-bd4e-bbc64f8d4e90"},
        {"marketId": 37682, "marketCode": "Y+1", "marketName": "FR Cal2025 base",
         "marketNameCode": "FR Cal2025 base Y+1", "commodity": "Power", "countryName": "France",
         "resourcesCode": None, "periodName": "Year", "typeName": "Base",
         "absolut": "Absolute", "currencyCode": "EUR", "unitNameCode": "MWh",
         "isLive": False, "rowId": "47a30947-4c3d-4ba7-9d74-8a5180dab993"},
        {"marketId": 69248, "marketCode": "Y+2", "marketName": "FR Cal2026 base",
         "marketNameCode": "FR Cal2026 base Y+2", "commodity": "Power", "countryName": "France",
         "resourcesCode": None, "periodName": "Year", "typeName": "Base",
         "absolut": "Absolute", "currencyCode": "EUR", "unitNameCode": "MWh",
         "isLive": False, "rowId": "1613a30d-c8e7-4f99-a767-6454990720ab"},
        {"marketId": 69249, "marketCode": "Y+3", "marketName": "FR Cal2027 base",
         "marketNameCode": "FR Cal2027 base Y+3", "commodity": "Power", "countryName": "France",
         "resourcesCode": None, "periodName": "Year", "typeName": "Base",
         "absolut": "Absolute", "currencyCode": "EUR", "unitNameCode": "MWh",
         "isLive": False, "rowId": "6f1786e9-22cc-4777-8988-35f664acff63"},
    ],
}


def get_token():
    """
    Try public auth endpoint first.
    Falls back to SEFE_TOKEN env var (GitHub Secret) if it fails.
    """
    # Mode A: public token
    try:
        r = requests.get(AUTH_URL, headers=HEADERS_BASE, timeout=15)
        r.raise_for_status()
        data = r.json()
        token = (data.get("token") or data.get("accessToken") or
                 data.get("jwtToken") or data.get("jwt"))
        if token:
            print("Token obtained via PublicAuthorization.")
            return token
        print("PublicAuthorization response:", data)
    except Exception as e:
        print(f"PublicAuthorization failed: {e}")

    # Mode B: GitHub Secret fallback
    token = os.environ.get("SEFE_TOKEN")
    if token:
        print("Token obtained via SEFE_TOKEN env var.")
        return token

    print("ERROR: No token available. Set SEFE_TOKEN as GitHub Secret.")
    sys.exit(1)


def fetch_table(token):
    headers = {**HEADERS_BASE, "Authorization": f"Bearer {token}"}
    r = requests.post(TABLE_URL, headers=headers, json=PAYLOAD, timeout=30)
    r.raise_for_status()
    return r.json()


def parse_table(data):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    rows = []
    for market in data:
        market_name = market.get("marketName", "")
        market_code = market.get("marketInfo", "").split("|")[-1]  # Y+1, Q+1, etc.
        unit = market.get("marketUnit", "€/MWh")
        stats = {s["paramName"]: s["value"] for s in market.get("statisticalData", [])}
        rows.append({
            "fetch_date":  today,
            "market_name": market_name,
            "market_code": market_code,
            "unit":        unit,
            "price_d1":    stats.get("D-1"),
            "price_last":  stats.get("Last"),
            "var_d1_pct":  stats.get("VAR D-1, %"),
            "var_w1_pct":  stats.get("VAR W-1, %"),
        })
    return pd.DataFrame(rows)


def main():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] Fetching SEFE forwards...")
    os.makedirs(DATA_DIR, exist_ok=True)

    token = get_token()
    data  = fetch_table(token)
    df    = parse_table(data)

    print(f"Parsed {len(df)} markets.")
    print(df[["market_name", "market_code", "price_d1", "price_last"]].to_string(index=False))

    # Skip if already fetched today
    if os.path.exists(OUTPUT):
        existing = pd.read_csv(OUTPUT)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if today in existing["fetch_date"].values:
            print(f"Already fetched today ({today}), skipping.")
            return

    write_header = not os.path.exists(OUTPUT)
    df.to_csv(OUTPUT, mode="a", header=write_header, index=False)
    print(f"Saved to {OUTPUT}")


if __name__ == "__main__":
    main()
