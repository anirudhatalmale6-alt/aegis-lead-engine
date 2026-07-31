"""
Value-first outreach email builder.

The email LEADS WITH VALUE: it hands the recipient two or three real findings
about their own public exposure, in plain English, for free -- before ever
mentioning a product or a price. That is what earns the reply.

Tone: a helpful human who noticed something, not a sales blast. Short.
Permission-respecting: we only ever mention what is publicly visible, and we
offer to stop ('reply STOP').
"""

from __future__ import annotations


def _top_points(snap: dict, n: int = 3) -> list[str]:
    pts = []
    for f in snap["findings"]:
        pts.append(f"- {f['headline']}: {f['meaning']}")
        if len(pts) >= n:
            break
    return pts


def build_email(snap: dict, business_name: str | None = None) -> dict:
    name = business_name or snap["domain"]
    points = _top_points(snap)

    if not points:
        # Nothing to alarm them with -- still lead with a genuine compliment + offer.
        subject = f"Quick note on {name}'s online security"
        body = (
            f"Hi,\n\n"
            f"I run Aegis, a small UK service that shows businesses what a stranger can already see about them "
            f"online -- the stuff hackers look for first.\n\n"
            f"I had a quick look at {name} and honestly it's tidier than most. A couple of tiny tune-ups aside, "
            f"you're in good shape.\n\n"
            f"If it'd be useful, I can send you the full free snapshot so you've got it on record. No cost, no catch. "
            f"Just reply 'yes' and I'll fire it over.\n\n"
            f"Cheers,\nJamie\nAegis\n\n"
            f"(Everything I looked at is public info. Not interested? Reply STOP and I won't message again.)"
        )
        return {"subject": subject, "body": body}

    lead = points[0].split(":", 1)[0].replace("- ", "").lower()
    subject = f"Noticed something about {name} online ({lead})"
    body = (
        f"Hi,\n\n"
        f"I run Aegis -- we show UK businesses what a stranger can already see about them online, so they can "
        f"close the gaps before someone else finds them.\n\n"
        f"I ran a quick, free check on {name} (public info only -- nothing private, nothing intrusive) and a few "
        f"things stood out:\n\n"
        + "\n".join(points)
        + "\n\n"
        f"None of it is a disaster and most are quick fixes. I've got the full plain-English snapshot ready if you "
        f"want it -- just reply 'yes' and I'll send it over, free.\n\n"
        f"If it's helpful after that, Aegis keeps an eye on this for you year-round for a flat 495 pounds a year. "
        f"But honestly, take the free snapshot first and see if it's useful.\n\n"
        f"Cheers,\nJamie\nAegis\n\n"
        f"(Everything above is publicly visible information. Not for you? Reply STOP and I'll leave you be.)"
    )
    return {"subject": subject, "body": body}
