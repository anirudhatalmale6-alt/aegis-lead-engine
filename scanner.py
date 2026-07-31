"""
Aegis passive exposure scanner.

100% passive: it only reads PUBLIC information a search engine could see too.
- Public DNS (via DNS-over-HTTPS) for mail-security records
- The target's own public website response headers and TLS certificate
- Public Certificate Transparency logs (crt.sh)
- A tiny set of well-known public files (robots.txt, /.git/HEAD)

It NEVER logs in, never guesses passwords, never port-scans infrastructure,
never touches anything private. Everything here is information the business
has already published to the open internet. That is the whole point of Aegis:
show a business what a stranger can already see, so they can close the gaps.
"""

from __future__ import annotations

import json
import socket
import ssl
import urllib.error
import urllib.request
from datetime import datetime, timezone

UA = "AegisExposureCheck/1.0 (+https://finch-ocxl.vercel.app)"
TIMEOUT = 12


def _doh(name: str, rrtype: str) -> list[str]:
    """Resolve a DNS record over HTTPS (Google public resolver). No local DNS needed."""
    url = f"https://dns.google/resolve?name={urllib.parse.quote(name)}&type={rrtype}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/dns-json"})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            data = json.loads(r.read(200_000))
    except Exception:
        return []
    out = []
    for ans in data.get("Answer", []) or []:
        val = ans.get("data", "")
        out.append(val.strip('"'))
    return out


import urllib.parse  # noqa: E402  (kept close to _doh for clarity)


def check_dns(domain: str) -> dict:
    a = _doh(domain, "A")
    mx = _doh(domain, "MX")
    txt = _doh(domain, "TXT")
    spf = [t for t in txt if t.lower().startswith("v=spf1")]
    dmarc_txt = _doh(f"_dmarc.{domain}", "TXT")
    dmarc = [t for t in dmarc_txt if "v=dmarc1" in t.lower()]
    return {
        "resolves": bool(a),
        "a": a,
        "has_mx": bool(mx),
        "mx": mx,
        "spf": spf,
        "dmarc": dmarc,
    }


def check_tls_and_headers(domain: str) -> dict:
    result = {
        "https_ok": False,
        "cert_expires": None,
        "cert_days_left": None,
        "server": None,
        "powered_by": None,
        "headers": {},
        "http_forces_https": None,
    }

    # TLS certificate (read-only handshake, public)
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((domain, 443), timeout=TIMEOUT) as sock:
            with ctx.wrap_socket(sock, server_hostname=domain) as ssock:
                cert = ssock.getpeercert()
        not_after = cert.get("notAfter")
        if not_after:
            exp = datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
            result["cert_expires"] = exp.isoformat()
            result["cert_days_left"] = (exp - datetime.now(timezone.utc)).days
        result["https_ok"] = True
    except Exception as e:
        result["tls_error"] = str(e)

    # Public HTTPS response headers
    try:
        req = urllib.request.Request(f"https://{domain}", headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            h = {k.lower(): v for k, v in r.headers.items()}
            result["headers"] = {
                "hsts": h.get("strict-transport-security"),
                "csp": h.get("content-security-policy"),
                "x_frame_options": h.get("x-frame-options"),
                "x_content_type_options": h.get("x-content-type-options"),
                "referrer_policy": h.get("referrer-policy"),
            }
            result["server"] = h.get("server")
            result["powered_by"] = h.get("x-powered-by")
            result["https_ok"] = True
    except urllib.error.HTTPError as e:
        # A response (even 403/500) still tells us headers/TLS worked
        result["https_ok"] = True
        result["http_status"] = e.code
    except Exception as e:
        result.setdefault("http_error", str(e))

    # Does plain http:// get forced up to https:// ?
    try:
        req = urllib.request.Request(f"http://{domain}", headers={"User-Agent": UA})
        opener = urllib.request.build_opener(_NoRedirect())
        with opener.open(req, timeout=TIMEOUT) as r:
            loc = r.headers.get("Location", "")
            result["http_forces_https"] = loc.lower().startswith("https://")
    except urllib.error.HTTPError as e:
        loc = e.headers.get("Location", "") if e.headers else ""
        result["http_forces_https"] = loc.lower().startswith("https://")
    except Exception:
        result["http_forces_https"] = None

    return result


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def check_public_files(domain: str) -> dict:
    """Fetch a couple of universally-public files to spot accidental exposure."""
    findings = {}
    # Exposed .git is a genuine leak; one GET to a public path is harmless
    for path, key in [("/.git/HEAD", "git_exposed"), ("/robots.txt", "robots")]:
        try:
            req = urllib.request.Request(f"https://{domain}{path}", headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                body = r.read(4000).decode("utf-8", "replace")
                if key == "git_exposed":
                    findings[key] = body.strip().startswith("ref:")
                else:
                    findings[key] = True
        except Exception:
            if key == "git_exposed":
                findings[key] = False
    return findings


def check_subdomains(domain: str) -> dict:
    """Public Certificate Transparency lookup — surfaces forgotten/exposed subdomains."""
    try:
        req = urllib.request.Request(
            f"https://crt.sh/?q=%25.{urllib.parse.quote(domain)}&output=json",
            headers={"User-Agent": UA},
        )
        with urllib.request.urlopen(req, timeout=TIMEOUT + 8) as r:
            data = json.loads(r.read(2_000_000))
        subs = set()
        for row in data:
            for nm in str(row.get("name_value", "")).split("\n"):
                nm = nm.strip().lower().lstrip("*.")
                if nm.endswith(domain) and nm != domain:
                    subs.add(nm)
        interesting = sorted(
            s for s in subs
            if any(w in s for w in ("dev", "staging", "test", "admin", "vpn", "mail", "remote", "portal", "cpanel", "webmail", "ftp"))
        )
        return {"subdomain_count": len(subs), "interesting": interesting[:12]}
    except Exception:
        return {"subdomain_count": None, "interesting": []}


def scan(domain: str) -> dict:
    domain = domain.strip().lower().replace("https://", "").replace("http://", "").strip("/")
    domain = domain.split("/")[0]
    return {
        "domain": domain,
        "dns": check_dns(domain),
        "web": check_tls_and_headers(domain),
        "files": check_public_files(domain),
        "subdomains": check_subdomains(domain),
    }


if __name__ == "__main__":
    import sys
    print(json.dumps(scan(sys.argv[1]), indent=2))
