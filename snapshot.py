"""
Turn a raw scan into a plain-English exposure snapshot a non-technical
business owner can understand in ten seconds. No jargon.

Each finding has: severity, a headline in human words, and a one-line
'what this means for you'. We deliberately keep it calm and non-scary --
we're offering help, not fear-selling.
"""

from __future__ import annotations


def _dmarc_policy(dmarc: list[str]) -> str | None:
    for t in dmarc:
        for part in t.split(";"):
            part = part.strip().lower()
            if part.startswith("p="):
                return part[2:]
    return None


def build(scan: dict) -> dict:
    dns = scan["dns"]
    web = scan["web"]
    files = scan["files"]
    subs = scan["subdomains"]

    findings = []  # each: (severity, headline, meaning)

    # --- Email spoofing protection (the single most relatable finding) ---
    has_spf = bool(dns.get("spf"))
    dmarc = dns.get("dmarc") or []
    policy = _dmarc_policy(dmarc)
    if dns.get("has_mx"):
        if not dmarc:
            findings.append((
                "high",
                "Your email can be faked",
                "There is nothing stopping a scammer sending emails that look like they come from your address. "
                "This is how fake invoices and 'the boss needs a payment' scams start.",
            ))
        elif policy in (None, "none"):
            findings.append((
                "medium",
                "Email protection is switched to 'watch only'",
                "You have the start of anti-spoofing set up, but it is only monitoring -- it isn't actually blocking "
                "fake emails yet. One setting change closes this.",
            ))
        if not has_spf:
            findings.append((
                "medium",
                "No sender list on file for your email",
                "Mail systems can't confirm which servers are allowed to send as you, so more of your genuine email "
                "lands in spam too.",
            ))

    # --- HTTPS / certificate ---
    days = web.get("cert_days_left")
    if web.get("https_ok") is False:
        findings.append((
            "high",
            "Your website security padlock isn't working",
            "Visitors may see a 'not secure' warning, which scares off customers and hurts your Google ranking.",
        ))
    elif isinstance(days, int):
        if days < 0:
            findings.append((
                "high",
                "Your website security certificate has expired",
                "Visitors will get a red warning screen when they try to reach you.",
            ))
        elif days <= 21:
            findings.append((
                "medium",
                f"Your website certificate expires in {days} days",
                "If it lapses, visitors get a scary warning. Worth a quick renew.",
            ))

    if web.get("http_forces_https") is False:
        findings.append((
            "medium",
            "Your site still opens on an unsecured link",
            "Someone typing your address without 'https' isn't automatically moved to the safe version.",
        ))

    # --- Version disclosure ---
    server = (web.get("server") or "")
    powered = (web.get("powered_by") or "")
    disclosed = []
    if any(ch.isdigit() for ch in server):
        disclosed.append(server)
    if powered:
        disclosed.append(powered)
    if disclosed:
        findings.append((
            "low",
            "Your website tells strangers what software it runs",
            "It's advertising exact version numbers (" + ", ".join(disclosed[:2]) + "). Attackers use this to look up "
            "known weaknesses. Easy to hide.",
        ))

    # --- Missing protective headers (kept as one friendly line) ---
    hdrs = web.get("headers") or {}
    missing = [k for k in ("hsts", "x_frame_options", "x_content_type_options") if not hdrs.get(k)]
    if len(missing) >= 2:
        findings.append((
            "low",
            "A few standard website safety settings are switched off",
            "These are the digital equivalent of locking the back windows -- quick to turn on, and they stop common "
            "tricks like your site being framed inside a fake page.",
        ))

    # --- Exposed .git ---
    if files.get("git_exposed"):
        findings.append((
            "high",
            "Your website's source code may be downloadable",
            "A developer folder has been left open to the public, which can leak passwords and the inner workings of "
            "your site. This one matters -- worth fixing today.",
        ))

    # --- Forgotten subdomains ---
    interesting = subs.get("interesting") or []
    if interesting:
        findings.append((
            "medium",
            "Forgotten 'back door' web addresses are visible",
            "Public records show extra addresses like " + ", ".join(interesting[:3]) + ". Old test or admin pages like "
            "these are a favourite way in if they've been left unpatched.",
        ))

    order = {"high": 0, "medium": 1, "low": 2}
    findings.sort(key=lambda f: order[f[0]])

    highs = sum(1 for f in findings if f[0] == "high")
    meds = sum(1 for f in findings if f[0] == "medium")
    if highs:
        grade, headline = "RED", "A few things need attention"
    elif meds:
        grade, headline = "AMBER", "Mostly good, a couple of easy wins"
    elif findings:
        grade, headline = "AMBER", "Solid, with minor tidy-ups"
    else:
        grade, headline = "GREEN", "Looking tidy from the outside"

    return {
        "domain": scan["domain"],
        "grade": grade,
        "headline": headline,
        "counts": {"high": highs, "medium": meds, "low": len(findings) - highs - meds},
        "findings": [{"severity": s, "headline": h, "meaning": m} for s, h, m in findings],
    }


def to_text(snap: dict) -> str:
    lines = [f"Exposure snapshot for {snap['domain']}  [{snap['grade']}] -- {snap['headline']}", ""]
    icon = {"high": "!!", "medium": " *", "low": "  "}
    for f in snap["findings"]:
        lines.append(f"{icon[f['severity']]} {f['headline']}")
        lines.append(f"     {f['meaning']}")
    if not snap["findings"]:
        lines.append("  No obvious public exposure found. Nice.")
    return "\n".join(lines)
