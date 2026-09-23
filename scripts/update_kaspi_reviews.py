#!/usr/bin/env python3
"""Refresh the OKEY review count from Kaspi.kz once a day.

Writes {"total", "rating", "updatedAt"} to the JSON file served at
https://okeystaydry.com/data/kaspi-reviews.json. The site shows the number baked in
at build time and replaces it with this file when it is available.

Kaspi does not answer requests from the web server's hosting IP range, so the
direct fetch runs in GitHub Actions (repo valerarelax-art/okey-kaspi-reviews). On the
server, set OKEY_KASPI_MIRROR_URL to that repo's raw kaspi-reviews.json and the script
copies the checked numbers from there instead.

Safety: the file is replaced atomically and only when Kaspi returns a sane answer
(an integer total that is not less than half of the previous one). Any failure
keeps the previous file, so the site never shows a broken or zero value.
"""
import json
import os
import sys
import tempfile
import urllib.request
from datetime import datetime, timezone

PRODUCT_ID = "135402917"
API = f"https://kaspi.kz/yml/review-view/api/v1/reviews/product/{PRODUCT_ID}?limit=1&withAgg=true"
MIRROR = os.environ.get("OKEY_KASPI_MIRROR_URL", "")
OUT = os.environ.get("OKEY_KASPI_REVIEWS_OUT", "/opt/okeystaydry-site/data/kaspi-reviews.json")


def fetch_mirror():
    request = urllib.request.Request(MIRROR, headers={"User-Agent": "okeystaydry.com review count"})
    with urllib.request.urlopen(request, timeout=20) as response:
        data = json.load(response)
    total, rating = data.get("total"), data.get("rating")
    if not isinstance(total, int) or total <= 0:
        raise ValueError(f"unexpected total: {total!r}")
    if not isinstance(rating, (int, float)) or not 0 < rating <= 5:
        raise ValueError(f"unexpected rating: {rating!r}")
    return total, round(float(rating), 1)


def fetch():
    if MIRROR:
        return fetch_mirror()
    request = urllib.request.Request(API, headers={
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (okeystaydry.com daily review count)",
        "Referer": "https://kaspi.kz/shop/",
    })
    with urllib.request.urlopen(request, timeout=20) as response:
        data = json.load(response)
    total = next((g.get("total") for g in data.get("groupSummary", []) if g.get("id") == "ALL"), None)
    rating = data.get("summary", {}).get("global")
    if not isinstance(total, int) or total <= 0:
        raise ValueError(f"unexpected total: {total!r}")
    if not isinstance(rating, (int, float)) or not 0 < rating <= 5:
        raise ValueError(f"unexpected rating: {rating!r}")
    return total, round(float(rating), 1)


def main():
    try:
        total, rating = fetch()
    except Exception as error:  # keep the previous file on any failure
        print(f"{datetime.now(timezone.utc).isoformat()} kaspi fetch failed: {error}", file=sys.stderr)
        return 1
    try:
        with open(OUT, encoding="utf-8") as current:
            previous = json.load(current).get("total", 0)
    except (OSError, ValueError):
        previous = 0
    if previous and total < previous * 0.5:
        print(f"refusing suspicious drop {previous} -> {total}", file=sys.stderr)
        return 1
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    payload = {"total": total, "rating": rating, "updatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(OUT), prefix=".kaspi-reviews-")
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False)
    os.chmod(tmp, 0o644)
    os.replace(tmp, OUT)
    print(f"{payload['updatedAt']} total={total} rating={rating}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
