"""
fetch_go_prices.py — Parse les mails Commerg Market Week et appende dans go_prices.csv
Usage : python fetch_go_prices.py
"""
import os
import re
import json
import base64
import csv
from datetime import datetime, date
from pathlib import Path

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# ── Config ────────────────────────────────────────────────────────────────────
SCOPES          = ["https://www.googleapis.com/auth/gmail.readonly"]
SUBJECT_FILTER  = "Commerg Market Week"
OUTPUT_CSV      = Path("ppa_dashboard/data/go_prices.csv")
TOKEN_ENV       = "GO_TOKEN_JSON"
CREDS_ENV       = "GO_CREDENTIALS_JSON"

CSV_HEADERS = [
    "parsed_date", "mail_date", "week_num", "source",
    "product", "year", "bid", "ask", "delta",
]

# ── Auth ──────────────────────────────────────────────────────────────────────
def get_service():
    token_json = os.environ.get(TOKEN_ENV)
    creds_json = os.environ.get(CREDS_ENV)

    if not token_json:
        # Local fallback
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    else:
        creds = Credentials.from_authorized_user_info(json.loads(token_json), SCOPES)

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())

    return build("gmail", "v1", credentials=creds)


# ── Mail fetching ─────────────────────────────────────────────────────────────
def get_commerg_emails(service, max_results=10):
    query = f"from:{SENDER_FILTER} subject:{SUBJECT_FILTER!r}"
    result = service.users().messages().list(
        userId="me", q=query, maxResults=max_results
    ).execute()
    return result.get("messages", [])


def get_email_body(service, msg_id):
    msg = service.users().messages().get(
        userId="me", id=msg_id, format="full"
    ).execute()

    # Extract date from headers
    headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
    mail_date_str = headers.get("Date", "")
    try:
        from email.utils import parsedate_to_datetime
        mail_date = parsedate_to_datetime(mail_date_str).date()
    except Exception:
        mail_date = date.today()

    # Extract text/plain body
    def extract_body(payload):
        if payload.get("mimeType") == "text/plain":
            data = payload.get("body", {}).get("data", "")
            if data:
                return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
        for part in payload.get("parts", []):
            result = extract_body(part)
            if result:
                return result
        return ""

    body = extract_body(msg["payload"])
    return mail_date, body


# ── Parsing ───────────────────────────────────────────────────────────────────
def parse_week_number(subject_or_body):
    """Extract week number from subject like 'Commerg Market Week #2'"""
    m = re.search(r"Week\s*#?(\d+)", subject_or_body, re.IGNORECASE)
    return int(m.group(1)) if m else None


def parse_go_block(block_text, product_name):
    """
    Parse a GO price block like:
    2025
    0.1800
    0.2200
    -0.0500
    2026
    0.5000
    ...
    Returns list of dicts with year/bid/ask/delta
    """
    rows = []
    lines = [l.strip() for l in block_text.strip().splitlines() if l.strip()]

    i = 0
    while i < len(lines):
        line = lines[i]
        # Year line
        if re.match(r"^20\d{2}$", line):
            year = int(line)
            try:
                bid   = float(lines[i+1].replace(",", "."))
                ask   = float(lines[i+2].replace(",", "."))
                delta = float(lines[i+3].replace(",", "."))
                rows.append({"product": product_name, "year": year,
                             "bid": bid, "ask": ask, "delta": delta})
                i += 4
            except (IndexError, ValueError):
                i += 1
        else:
            i += 1
    return rows


def parse_email_body(body):
    """Main parser — returns list of price rows."""
    rows = []

    # Extract week number from header line
    week_num = parse_week_number(body)

    # Block patterns — find each product section
    block_patterns = [
        (r"GO AIB Hydro/Wind/Solar.*?(?=GO AIB|\Z)", "GO AIB HWS"),
        (r"GO AIB Renewable.*?(?=GO AIB|\Z)",         "GO AIB Renewable"),
        (r"GO AIB Wind.*?(?=GO AIB|\Z)",              "GO AIB Wind"),
        (r"GO AIB Solar.*?(?=GO AIB|\Z)",             "GO AIB Solar"),
    ]

    for pattern, product_name in block_patterns:
        match = re.search(pattern, body, re.DOTALL | re.IGNORECASE)
        if not match:
            continue
        block = match.group(0)

        # Skip header lines (PRODUCT, BID, ASK, + / -)
        block_clean = re.sub(
            r"GO AIB[^\n]*\n|PRODUCT[^\n]*\n|BID\n|ASK\n|\+\s*/\s*-\n",
            "", block
        )
        parsed = parse_go_block(block_clean, product_name)
        if parsed:
            rows.extend(parsed)
            # Once we found HWS rows, skip Renewable if it's a subset
            # (Commerg notes Renewable includes HWS — keep both for completeness)

    return week_num, rows


# ── CSV management ────────────────────────────────────────────────────────────
def load_existing(csv_path):
    """Return set of (mail_date, product, year) already in CSV."""
    existing = set()
    if not csv_path.exists():
        return existing
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            existing.add((row["mail_date"], row["product"], row["year"]))
    return existing


def append_rows(csv_path, rows):
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not csv_path.exists()
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        if write_header:
            writer.writeheader()
        writer.writerows(rows)
    print(f"  → {len(rows)} ligne(s) ajoutée(s) dans {csv_path}")


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print("=== fetch_go_prices.py ===")
    service  = get_service()
    existing = load_existing(OUTPUT_CSV)
    messages = get_commerg_emails(service, max_results=20)

    if not messages:
        print("Aucun mail Commerg trouvé.")
        return

    print(f"{len(messages)} mail(s) trouvé(s).")
    new_rows = []

    for msg_meta in messages:
        mail_date, body = get_email_body(service, msg_meta["id"])
        week_num, parsed = parse_email_body(body)

        if not parsed:
            print(f"  [{mail_date}] Aucune donnée parsée — format inattendu ?")
            continue

        print(f"  [{mail_date}] Semaine #{week_num} — {len(parsed)} produit(s)/année(s)")

        for r in parsed:
            key = (str(mail_date), r["product"], str(r["year"]))
            if key in existing:
                continue  # déjà en base
            new_rows.append({
                "parsed_date": date.today().isoformat(),
                "mail_date":   str(mail_date),
                "week_num":    week_num,
                "source":      "Commerg",
                "product":     r["product"],
                "year":        r["year"],
                "bid":         r["bid"],
                "ask":         r["ask"],
                "delta":       r["delta"],
            })
            existing.add(key)

    if new_rows:
        append_rows(OUTPUT_CSV, new_rows)
    else:
        print("Aucune nouvelle ligne à ajouter.")

    print("Done.")


if __name__ == "__main__":
    main()
