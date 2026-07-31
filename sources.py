"""
Automatic lead sourcing.

You give it a place ("Loughborough" or "Leeds, UK") and it finds the estate /
letting agents there, with their websites, automatically -- no manual list.

It uses OpenStreetMap's public business data (the same map data behind loads of
apps), NOT Google search-result scraping. Google actively blocks automated
scraping of its results and it's against their terms, so it would break fast and
get us throttled. OpenStreetMap is free, has no API key, and is built to be
queried like this -- the honest, reliable way to do it.

Flow:
  1. Nominatim geocodes the place name to a map area (bounding box).
  2. Overpass returns businesses tagged as estate agents in that box.
  3. We pull out each one's name + website and hand them to the scanner.

Coverage note: OpenStreetMap is community-mapped, so it catches most high-street
agents but not every single one. It's a great free first pass. If you ever want
fuller coverage we can add Google's official Places API (needs a key + small
cost) as a second source -- same pipeline.
"""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request

UA = "AegisLeadFinder/1.0 (business exposure outreach; contact via aegis)"
NOMINATIM = "https://nominatim.openstreetmap.org/search"
OVERPASS = "https://overpass-api.de/api/interpreter"


def _get_json(url: str, timeout: int = 40) -> object:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read(8_000_000))


def _post_json(url: str, data: str, timeout: int = 90) -> dict:
    req = urllib.request.Request(
        url, data=data.encode(), headers={"User-Agent": UA, "Content-Type": "text/plain"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read(20_000_000))


def geocode_bbox(place: str) -> tuple[float, float, float, float] | None:
    """Return (south, north, west, east) for a place name, or None."""
    q = urllib.parse.urlencode({"q": place, "format": "json", "limit": 1, "countrycodes": "gb"})
    try:
        data = _get_json(f"{NOMINATIM}?{q}")
    except Exception:
        return None
    if not data:
        # retry without country lock, in case it's outside GB
        q = urllib.parse.urlencode({"q": place, "format": "json", "limit": 1})
        try:
            data = _get_json(f"{NOMINATIM}?{q}")
        except Exception:
            return None
    if not data:
        return None
    bb = data[0].get("boundingbox")  # [south, north, west, east] as strings
    if not bb or len(bb) != 4:
        return None
    s, n, w, e = (float(x) for x in bb)
    return s, n, w, e


def _domain_from(url: str) -> str | None:
    if not url:
        return None
    url = url.strip()
    if not url.startswith("http"):
        url = "http://" + url
    try:
        host = urllib.parse.urlparse(url).netloc.lower()
    except Exception:
        return None
    host = host.split(":")[0]
    if host.startswith("www."):
        host = host[4:]
    # skip social / directory links -- we want the agent's own site
    bad = ("facebook.", "instagram.", "twitter.", "x.com", "rightmove.", "zoopla.",
           "onthemarket.", "linkedin.", "youtube.", "google.")
    if not host or "." not in host or any(b in host for b in bad):
        return None
    return host


def find_agents(place: str, limit: int = 60) -> list[dict]:
    """Return [{name, domain, email}] of estate/letting agents in a place."""
    box = geocode_bbox(place)
    if not box:
        return []
    s, n, w, e = box
    time.sleep(1)  # be polite between OSM services
    query = (
        "[out:json][timeout:80];"
        "("
        f'nwr["office"="estate_agent"]({s},{w},{n},{e});'
        f'nwr["shop"="estate_agent"]({s},{w},{n},{e});'
        f'nwr["office"="estate_agent"]["website"]({s},{w},{n},{e});'
        ");"
        "out center tags;"
    )
    try:
        data = _post_json(OVERPASS, "data=" + urllib.parse.quote(query))
    except Exception:
        return []

    seen: dict[str, dict] = {}
    for el in data.get("elements", []):
        tags = el.get("tags", {}) or {}
        website = tags.get("website") or tags.get("contact:website") or tags.get("url") or ""
        domain = _domain_from(website)
        if not domain:
            continue
        name = tags.get("name") or tags.get("brand") or ""
        email = tags.get("email") or tags.get("contact:email") or ""
        if domain not in seen:
            seen[domain] = {"name": name, "domain": domain, "email": email.lower()}
        if len(seen) >= limit:
            break
    return list(seen.values())


def find_agents_google(place: str, api_key: str, limit: int = 60) -> list[dict]:
    """
    Use Google's OFFICIAL Places API (not search-result scraping) for fuller
    coverage. Needs a Google Places API key (env GOOGLE_PLACES_KEY). This is the
    proper, allowed way to pull business listings from Google's own data.
    """
    base = "https://maps.googleapis.com/maps/api/place"
    seen: dict[str, dict] = {}
    for term in ("estate agents", "letting agents"):
        q = urllib.parse.urlencode({"query": f"{term} in {place}", "key": api_key})
        try:
            data = _get_json(f"{base}/textsearch/json?{q}")
        except Exception:
            continue
        for res in data.get("results", []):
            pid = res.get("place_id")
            if not pid:
                continue
            time.sleep(0.1)
            dq = urllib.parse.urlencode({"place_id": pid, "fields": "name,website", "key": api_key})
            try:
                det = _get_json(f"{base}/details/json?{dq}").get("result", {})
            except Exception:
                continue
            domain = _domain_from(det.get("website", ""))
            if not domain or domain in seen:
                continue
            seen[domain] = {"name": det.get("name") or res.get("name") or "", "domain": domain, "email": ""}
            if len(seen) >= limit:
                return list(seen.values())
    return list(seen.values())


def auto_find(place: str, limit: int = 60) -> list[dict]:
    """Prefer Google Places if a key is set, else free OpenStreetMap."""
    import os
    key = os.environ.get("GOOGLE_PLACES_KEY", "")
    if key:
        results = find_agents_google(place, key, limit)
        if results:
            return results
    return find_agents(place, limit)


if __name__ == "__main__":
    import sys
    place = sys.argv[1] if len(sys.argv) > 1 else "Loughborough"
    for a in auto_find(place):
        print(f"{a['domain']:<40} {a['name']}")
