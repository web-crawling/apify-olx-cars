"""QA #72: verify owner_type filter actually works after the fix.

Reproduces the exact INPUT from failing run d1qLJP2l5HXf59VYe and hits OLX
with both the OLD (broken) param shape and the NEW (fixed) param shape to
confirm the patch resolves the HTTP 400.
"""
import json
import urllib.parse
import urllib.request

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


def hit(url):
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "Accept-Language": "ro-RO,ro;q=0.9,en;q=0.8",
            "User-Agent": UA,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            body = json.loads(r.read())
            return (
                r.status,
                len(body.get("data") or []),
                (body.get("metadata") or {}).get("visible_total_count"),
            )
    except urllib.error.HTTPError as e:
        return (e.code, None, e.read().decode("utf-8", errors="replace")[:200])


# Failing run input -> spider builds: category_id=84, owner_type=private
# (parent cars category on RO, because startUrls has no category_id and
# sellerType=private).
COUNTRY_PARENT = {"ro": 84, "pl": 84, "bg": 1117, "pt": 378, "ua": 108, "kz": 108}


def url_for(country, owner_type_value):
    params = {
        "category_id": COUNTRY_PARENT[country],
        "limit": 50,
        "offset": 0,
        "sort_by": "created_at:desc",
        "owner_type": owner_type_value,
    }
    return (
        f"https://www.olx.{country if country != 'ua' else 'ua'}/api/v1/offers/"
        + "?"
        + urllib.parse.urlencode(params)
    )


print("=== BEFORE fix (filter_enum_business=0 — expected HTTP 400) ===")
old_params = {
    "category_id": 84,
    "limit": 50,
    "offset": 0,
    "sort_by": "created_at:desc",
    "filter_enum_business": 0,
}
old_url = (
    "https://www.olx.ro/api/v1/offers/?" + urllib.parse.urlencode(old_params)
)
print(f"GET {old_url}")
print(f"  -> {hit(old_url)}")

print("\n=== AFTER fix: owner_type=private on every country ===")
ok_all = True
for country in ("ro", "pl", "bg", "pt", "ua", "kz"):
    domain = f"www.olx.{country}"
    params = {
        "category_id": COUNTRY_PARENT[country],
        "limit": 50,
        "offset": 0,
        "sort_by": "created_at:desc",
        "owner_type": "private",
    }
    url = f"https://{domain}/api/v1/offers/?" + urllib.parse.urlencode(params)
    status, n, total = hit(url)
    ok = status == 200 and (n or 0) > 0
    ok_all = ok_all and ok
    print(
        f"  {country} cat={COUNTRY_PARENT[country]} -> HTTP {status} "
        f"({n} items, visible_total={total}) {'OK' if ok else 'FAIL'}"
    )

print("\n=== AFTER fix: owner_type=business on every country ===")
for country in ("ro", "pl", "bg", "pt", "ua", "kz"):
    domain = f"www.olx.{country}"
    params = {
        "category_id": COUNTRY_PARENT[country],
        "limit": 50,
        "offset": 0,
        "sort_by": "created_at:desc",
        "owner_type": "business",
    }
    url = f"https://{domain}/api/v1/offers/?" + urllib.parse.urlencode(params)
    status, n, total = hit(url)
    ok = status == 200 and (n or 0) > 0
    ok_all = ok_all and ok
    print(
        f"  {country} cat={COUNTRY_PARENT[country]} -> HTTP {status} "
        f"({n} items, visible_total={total}) {'OK' if ok else 'FAIL'}"
    )

print("\nRESULT:", "PASS" if ok_all else "FAIL")
import sys as _sys

_sys.exit(0 if ok_all else 1)
