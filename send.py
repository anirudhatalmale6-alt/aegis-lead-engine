"""
Low-and-steady sender -- run this on YOUR machine with YOUR inbox.

Deliverability rule of thumb for an established Gmail:
  * Start small: 15-25 a day for the first week, then ease up.
  * Space them out (this script waits between each).
  * Personalised + a real reason to reply (which our emails have) = low spam risk.
  * One spammy blast can get an account limited, so we cap per run.

Your password is read from the environment and never stored or printed.
Create a Gmail App Password (Google account -> Security -> App passwords) and:

  export GMAIL_USER="you@gmail.com"
  export GMAIL_APP_PASSWORD="the 16-char app password"
  python3 send.py emails/           # sends every emails/*.txt, then stops

Add --dry-run to preview without sending.
"""

from __future__ import annotations

import os
import smtplib
import sys
import time
from email.mime.text import MIMEText
from pathlib import Path

DAILY_CAP = 25          # hard stop per run -- protects the account
GAP_SECONDS = 90        # wait between sends


def parse_email_file(path: Path) -> dict | None:
    lines = path.read_text().splitlines()
    to = subject = ""
    body_start = 0
    for i, ln in enumerate(lines):
        if ln.lower().startswith("to:"):
            to = ln.split(":", 1)[1].strip()
        elif ln.lower().startswith("subject:"):
            subject = ln.split(":", 1)[1].strip()
        elif ln.strip() == "" and to and subject:
            body_start = i + 1
            break
    body = "\n".join(lines[body_start:]).strip()
    if not to or "@" not in to:
        return None
    return {"to": to, "subject": subject, "body": body}


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry = "--dry-run" in sys.argv
    folder = Path(args[0]) if args else Path("emails")
    files = sorted(folder.glob("*.txt"))
    if not files:
        print(f"No .txt emails found in {folder}/")
        return

    user = os.environ.get("GMAIL_USER", "")
    pw = os.environ.get("GMAIL_APP_PASSWORD", "")
    if not dry and (not user or not pw):
        print("Set GMAIL_USER and GMAIL_APP_PASSWORD first (see top of this file). Or use --dry-run.")
        sys.exit(1)

    server = None
    if not dry:
        server = smtplib.SMTP("smtp.gmail.com", 587, timeout=30)
        server.starttls()
        server.login(user, pw)

    sent = 0
    for path in files:
        if sent >= DAILY_CAP:
            print(f"Reached the {DAILY_CAP}-per-run cap. Run again tomorrow for the rest.")
            break
        mail = parse_email_file(path)
        if not mail:
            print(f"skip {path.name} (no recipient)")
            continue
        if dry:
            print(f"[dry] would send to {mail['to']}: {mail['subject']}")
            continue
        msg = MIMEText(mail["body"], "plain", "utf-8")
        msg["From"] = user
        msg["To"] = mail["to"]
        msg["Subject"] = mail["subject"]
        try:
            server.sendmail(user, [mail["to"]], msg.as_string())
            sent += 1
            print(f"sent {sent}/{DAILY_CAP} -> {mail['to']}")
        except Exception as e:
            print(f"FAILED {mail['to']}: {e}")
        if sent < DAILY_CAP and path != files[-1]:
            time.sleep(GAP_SECONDS)

    if server:
        server.quit()
    if not dry:
        print(f"\nDone. {sent} sent this run.")


if __name__ == "__main__":
    main()
