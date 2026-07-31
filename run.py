"""
Aegis lead engine -- command line.

  python3 run.py scan  <domain>                 # just show the exposure snapshot
  python3 run.py lead  <domain> [Business Name] # snapshot + public email + ready email
  python3 run.py batch <websites.txt>           # one domain per line -> leads.csv + emails/

Value-first: every generated email leads with the free findings, not a pitch.
Nothing is sent here -- see send.py for low-volume sending from your own inbox.
"""

from __future__ import annotations

import csv
import json
import os
import sys

import scanner
import snapshot as snap_mod
import outreach
import leads as leads_mod


def cmd_scan(domain: str) -> None:
    snap = snap_mod.build(scanner.scan(domain))
    print(snap_mod.to_text(snap))


def cmd_lead(domain: str, name: str | None) -> None:
    raw = scanner.scan(domain)
    snap = snap_mod.build(raw)
    email_addr = leads_mod.find_public_email(domain)
    mail = outreach.build_email(snap, name)
    print(snap_mod.to_text(snap))
    print("\n--- contact (public) ---")
    print(email_addr or "(no public email found on site)")
    print("\n--- ready-to-send email ---")
    print(f"To: {email_addr or '<add manually>'}")
    print(f"Subject: {mail['subject']}\n")
    print(mail["body"])


def cmd_batch(path: str) -> None:
    with open(path) as f:
        domains = [ln.strip() for ln in f if ln.strip() and not ln.startswith("#")]
    os.makedirs("emails", exist_ok=True)
    rows = []
    for i, entry in enumerate(domains, 1):
        parts = entry.split(",", 1)
        domain = parts[0].strip()
        name = parts[1].strip() if len(parts) > 1 else None
        sys.stderr.write(f"[{i}/{len(domains)}] scanning {domain} ...\n")
        try:
            raw = scanner.scan(domain)
            snap = snap_mod.build(raw)
            email_addr = leads_mod.find_public_email(domain)
            mail = outreach.build_email(snap, name)
        except Exception as e:
            sys.stderr.write(f"    skipped ({e})\n")
            continue
        safe = domain.replace("/", "_")
        with open(f"emails/{safe}.txt", "w") as out:
            out.write(f"To: {email_addr or ''}\nSubject: {mail['subject']}\n\n{mail['body']}\n")
        rows.append({
            "domain": domain,
            "business": name or "",
            "email": email_addr or "",
            "grade": snap["grade"],
            "high": snap["counts"]["high"],
            "medium": snap["counts"]["medium"],
            "low": snap["counts"]["low"],
            "top_finding": snap["findings"][0]["headline"] if snap["findings"] else "",
        })
    with open("leads.csv", "w", newline="") as out:
        w = csv.DictWriter(out, fieldnames=["domain", "business", "email", "grade", "high", "medium", "low", "top_finding"])
        w.writeheader()
        w.writerows(rows)
    sys.stderr.write(f"\nDone. {len(rows)} leads -> leads.csv, emails in emails/\n")


def main() -> None:
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    cmd, arg = sys.argv[1], sys.argv[2]
    if cmd == "scan":
        cmd_scan(arg)
    elif cmd == "lead":
        cmd_lead(arg, sys.argv[3] if len(sys.argv) > 3 else None)
    elif cmd == "batch":
        cmd_batch(arg)
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
