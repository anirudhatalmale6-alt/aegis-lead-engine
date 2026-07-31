"""
Lightweight lead enrichment.

Given a business website, pull the PUBLIC contact email the business has
chosen to publish on its own site (mailto: links / plain text on the home or
contact page). This is small-scale, per-lead enrichment -- not bulk scraping.

Sourcing the raw LIST of estate/letting agents should come from a legitimate
place: a directory export, a purchased data list, or manual pasting. Feed those
websites in here and this fills in the contact email + runs the scan.
"""

from __future__ import annotations

import re
import urllib.request

UA = "AegisExposureCheck/1.0 (+https://finch-ocxl.vercel.app)"
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
# skip common junk / image-tracking / example addresses
JUNK = (
    "example.com", "sentry", "wixpress", "@2x", ".png", ".jpg", "@sentry", "godaddy",
    "@email.com", "@domain.com", "@yourdomain", "noreply", "no-reply", "@sentry.io",
    "notification@email", "@2x.png", "yourname@", "name@email", "u003e",
)


def _fetch(url: str) -> str:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=12) as r:
            return r.read(400_000).decode("utf-8", "replace")
    except Exception:
        return ""


def find_public_email(domain: str) -> str | None:
    domain = domain.strip().lower().replace("https://", "").replace("http://", "").strip("/").split("/")[0]
    seen: dict[str, int] = {}
    for path in ("", "/contact", "/contact-us", "/about", "/get-in-touch"):
        html = _fetch(f"https://{domain}{path}")
        if not html:
            continue
        for m in EMAIL_RE.findall(html):
            e = m.lower()
            if any(j in e for j in JUNK):
                continue
            # prefer addresses on the business's own domain
            score = 2 if e.endswith("@" + domain) or domain.split(".")[0] in e else 1
            seen[e] = max(seen.get(e, 0), score)
    if not seen:
        return None
    return sorted(seen, key=lambda e: (-seen[e], len(e)))[0]
