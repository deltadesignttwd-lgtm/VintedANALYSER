#!/usr/bin/env python3
"""Vinted catalog analyser.

Fetches items from a Vinted catalog category and prints a quick
market summary (price range, average, top favourited listings).

Usage:
    python vinted_analyser.py
    python vinted_analyser.py --domain vinted.co.uk --category-id 2320 --per-page 20
    python vinted_analyser.py --save results.json
"""

import argparse
import json
import sys
import time
from typing import Any, Dict, List, Optional

import requests

DEFAULT_DOMAIN = "www.vinted.co.uk"
DEFAULT_CATEGORY_ID = 2320  # Books > Non-fiction
DEFAULT_PER_PAGE = 20
REQUEST_TIMEOUT = 15
MAX_RETRIES = 3

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-GB,en;q=0.9",
}


def extract_price(item: Dict[str, Any]) -> float:
    """Vinted's API has returned `price` as either a plain number or a
    nested object ({"amount": "12.00", "currency_code": "GBP"}) depending
    on API version/region. Handle both."""
    price = item.get("price", 0)
    if isinstance(price, dict):
        return float(price.get("amount", 0) or 0)
    try:
        return float(price)
    except (TypeError, ValueError):
        return 0.0


def extract_currency(item: Dict[str, Any], default: str = "GBP") -> str:
    price = item.get("price")
    if isinstance(price, dict) and price.get("currency_code"):
        return price["currency_code"]
    return item.get("currency", default)


def fetch_catalog_items(
    domain: str = DEFAULT_DOMAIN,
    category_id: int = DEFAULT_CATEGORY_ID,
    per_page: int = DEFAULT_PER_PAGE,
    order: str = "favourite_count_desc",
) -> Optional[List[Dict[str, Any]]]:
    """Fetch a page of catalog items. Returns None on failure."""
    session = requests.Session()
    catalog_url = (
        f"https://{domain}/api/v2/catalog/items"
        f"?category_ids[]={category_id}&order={order}&per_page={per_page}"
    )

    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            # Vinted requires a session cookie obtained from the homepage
            # before the API will accept requests.
            session.get(f"https://{domain}/", headers=HEADERS, timeout=REQUEST_TIMEOUT)

            response = session.get(catalog_url, headers=HEADERS, timeout=REQUEST_TIMEOUT)

            if response.status_code == 401 or response.status_code == 403:
                print(
                    f"[!] Request blocked (HTTP {response.status_code}). "
                    "Vinted's anti-bot protection likely rejected this request. "
                    "This can happen from datacenter/cloud IPs even with a "
                    "browser-like User-Agent.",
                    file=sys.stderr,
                )
                return None

            if response.status_code != 200:
                print(f"[!] Unexpected status code: {response.status_code}", file=sys.stderr)
                last_error = f"HTTP {response.status_code}"
                time.sleep(2 * attempt)
                continue

            content_type = response.headers.get("Content-Type", "")
            if "application/json" not in content_type:
                print(
                    "[!] Response was not JSON (Content-Type: "
                    f"{content_type!r}). Vinted likely served an anti-bot "
                    "challenge page instead of API data.",
                    file=sys.stderr,
                )
                return None

            data = response.json()
            return data.get("items", [])

        except requests.exceptions.RequestException as exc:
            last_error = str(exc)
            print(f"[!] Attempt {attempt}/{MAX_RETRIES} failed: {exc}", file=sys.stderr)
            time.sleep(2 * attempt)

    print(f"[!] All retries exhausted. Last error: {last_error}", file=sys.stderr)
    return None


def analyse(items: List[Dict[str, Any]], top_n: int = 10) -> Dict[str, Any]:
    sample = items[:top_n]
    prices = [extract_price(item) for item in sample]
    prices = [p for p in prices if p > 0]

    summary = {
        "sample_size": len(sample),
        "average_price": round(sum(prices) / len(prices), 2) if prices else 0.0,
        "min_price": round(min(prices), 2) if prices else 0.0,
        "max_price": round(max(prices), 2) if prices else 0.0,
        "items": [],
    }

    for item in sample:
        summary["items"].append(
            {
                "title": item.get("title", "Untitled"),
                "price": extract_price(item),
                "currency": extract_currency(item),
                "favourite_count": item.get("favourite_count", 0),
                "seller": item.get("user", {}).get("login", "unknown"),
                "url": item.get("url"),
            }
        )

    return summary


def print_report(summary: Dict[str, Any]) -> None:
    print("=" * 50)
    print(f"Vinted catalog sample (top {summary['sample_size']} by favourites)")
    print("=" * 50)
    print()

    for idx, item in enumerate(summary["items"], 1):
        print(f"{idx}. {item['title']}")
        print(f"   Price: {item['price']:.2f} {item['currency']}")
        print(f"   Favourites: {item['favourite_count']}")
        print(f"   Seller: {item['seller']}")
        print("-" * 40)

    print()
    print("Summary:")
    print(f"  Average price: {summary['average_price']:.2f}")
    print(f"  Price range: {summary['min_price']:.2f} - {summary['max_price']:.2f}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyse a Vinted catalog category.")
    parser.add_argument("--domain", default=DEFAULT_DOMAIN, help="Vinted domain, e.g. www.vinted.co.uk")
    parser.add_argument("--category-id", type=int, default=DEFAULT_CATEGORY_ID)
    parser.add_argument("--per-page", type=int, default=DEFAULT_PER_PAGE)
    parser.add_argument("--order", default="favourite_count_desc")
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument("--save", metavar="FILE", help="Also save the summary as JSON to this path")
    args = parser.parse_args()

    items = fetch_catalog_items(
        domain=args.domain,
        category_id=args.category_id,
        per_page=args.per_page,
        order=args.order,
    )

    if not items:
        print("[!] No items retrieved. See warnings above.", file=sys.stderr)
        return 1

    summary = analyse(items, top_n=args.top_n)
    print_report(summary)

    if args.save:
        with open(args.save, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        print(f"\nSaved summary to {args.save}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
