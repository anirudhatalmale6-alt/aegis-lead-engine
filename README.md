# Aegis Lead Engine

Find businesses that would benefit from Aegis, show them **real value up front**,
and reach out in plain English — all from public information only.

It does three things:

1. **Scan** a business's *public* footprint (no logins, no intrusion, nothing private).
2. **Explain** what it found in plain English a non-technical owner understands.
3. **Draft** a value-first outreach email that leads with the free findings, not a pitch.

Everything it looks at is information the business has already published to the
open internet — the same things a stranger (or an attacker) can already see.
That's the whole point of Aegis: show people their open windows so they can shut them.

---

## Quick start

```bash
# 1. See what's publicly visible about one business
python3 run.py scan huntleys.net

# 2. Full lead: snapshot + their public contact email + a ready-to-send email
python3 run.py lead huntleys.net "Huntleys"

# 3. A whole list at once -> leads.csv + one email per business in emails/
python3 run.py batch websites.txt
```

`websites.txt` is one business per line. You can add a name after a comma:

```
huntleys.net, Huntleys
someagent.co.uk, Some Agent Lettings
```

## Sending (low and steady, from your own inbox)

The scan/draft steps never send anything. When you're ready, send from *your*
established inbox, slowly:

```bash
export GMAIL_USER="you@gmail.com"
export GMAIL_APP_PASSWORD="your 16-char Gmail app password"
python3 send.py emails/ --dry-run   # preview
python3 send.py emails/             # send (caps at 25 per run, spaced out)
```

Your password is read from the environment — it is never stored or printed.

## Where to get the list of businesses

Feed real websites into `batch`. Get them from a legitimate source — a directory
export, a bought data list, or pasted by hand. This tool enriches and scans them;
it does **not** bulk-scrape directories.

## What the scan checks (all public)

- Email spoofing protection (SPF / DMARC) — the #1 relatable finding
- Website security certificate (valid? expiring? forces https?)
- Software version disclosure in public response headers
- Standard website safety headers (HSTS, clickjacking protection, etc.)
- Accidentally exposed developer files (e.g. an open `.git`)
- Forgotten "back door" subdomains via public Certificate Transparency logs

## Design notes

- Pure Python standard library — no packages to install, runs anywhere.
- DNS is resolved over HTTPS, so it works even on locked-down machines.
- Findings are deliberately calm and non-scary. We offer help, not fear.
