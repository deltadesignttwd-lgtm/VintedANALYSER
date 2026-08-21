# VintedANALYSER

A small script that samples a Vinted catalog category and reports basic
market stats: average price, price range, and the top listings by
favourite count.

## Setup

```bash
pip install -r requirements.txt
```

## Usage

```bash
python vinted_analyser.py
```

Options:

```
--domain        Vinted domain to query (default: www.vinted.co.uk)
--category-id   Catalog category ID (default: 2320, Books > Non-fiction)
--per-page      Number of items to fetch (default: 20)
--order         Sort order (default: favourite_count_desc)
--top-n         Number of top items to include in the report (default: 10)
--save FILE     Also write the summary as JSON to FILE
```

Example, a different category and saving output:

```bash
python vinted_analyser.py --category-id 1904 --save results.json
```

## Notes / known limitations

- **Anti-bot protection**: Vinted fronts its site with bot detection
  (DataDome). Requests from datacenter/cloud IPs — including CI runners,
  cloud VMs, and most hosted dev environments — are frequently blocked
  even with a realistic `User-Agent` and a warm-up request to the
  homepage. If you get no results, check the stderr output: the script
  distinguishes an explicit 401/403 block from a "200 OK but HTML instead
  of JSON" challenge page. Running from a residential IP / your own
  machine has a much higher success rate.
- **`price` field shape**: Vinted's catalog API has returned `price` as
  either a plain number or a `{"amount": ..., "currency_code": ...}`
  object depending on API version/region. The script handles both.
- This uses an undocumented, unofficial endpoint. It can change or break
  without notice — this is not a supported Vinted API integration.
