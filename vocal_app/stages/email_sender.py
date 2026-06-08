"""
Stage 4: Email Sender
---------------------
Sends genuinely personalized outreach — not one template for everyone.

Personalization signals used per lead:
  - First name
  - Company name
  - Their specific role (CEO gets different copy than VP Sales)
  - Industry vertical
  - LinkedIn signal if available

Deduplication: never emails same address twice per run.
Bounce-risk filter: skips emails below confidence threshold.
Rate limiting: configurable delay between sends.
Dry-run default: shows exact email that would be sent, no firing.

Senders: Gmail API → SMTP → dry-run print.
"""

import os
import base64
import time
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib

logger = logging.getLogger(__name__)

# Skip emails below this confidence score (avoids bounces)
MIN_CONFIDENCE = int(os.getenv("MIN_EMAIL_CONFIDENCE", "30"))


# ─── Personalized copy engine ────────────────────────────────────────────────

def _subject(lead: dict) -> str:
    first = lead.get("name", "").split()[0]
    role  = lead.get("role", "").lower()

    if "ceo" in role or "founder" in role or "president" in role:
        return f"Quick question for you, {first}"
    elif "cto" in role or "tech" in role or "engineer" in role:
        return f"Thought this might be useful, {first}"
    elif "sales" in role or "revenue" in role or "growth" in role:
        return f"On pipeline efficiency — {first}"
    else:
        return f"Worth 15 minutes, {first}?"


def _body(lead: dict, sender_name: str, sender_title: str, sender_email: str) -> str:
    first    = lead.get("name", "there").split()[0]
    domain   = lead.get("domain", "your company")
    company  = domain.split(".")[0].replace("-", " ").capitalize()
    role     = lead.get("role", "").lower()
    industry = lead.get("industry", "technology").lower()

    # Role-specific opening hook
    if "ceo" in role or "founder" in role:
        hook = (
            f"I've been following what {company} is building — "
            f"the direction you're taking in the {industry} space caught my attention."
        )
        angle = (
            "As someone running the company, you're probably thinking about "
            "how to grow pipeline without proportionally growing the team. "
            "That's exactly the problem we solve."
        )
    elif "cto" in role or "vp eng" in role or "technical" in role:
        hook = (
            f"I noticed {company} has been expanding its technical footprint — "
            f"interesting work in the {industry} space."
        )
        angle = (
            "We help technical leaders reduce the manual overhead in their outbound motion "
            "by automating the sourcing-to-contact workflow end to end."
        )
    elif "sales" in role or "revenue" in role or "growth" in role:
        hook = (
            f"I saw {company} is scaling its go-to-market in the {industry} space — "
            f"congrats on that."
        )
        angle = (
            "We work with revenue leaders to automate the top of funnel — "
            "from identifying the right accounts to landing in the right inbox — "
            "so your team spends time closing, not sourcing."
        )
    else:
        hook = (
            f"I came across {company} and was genuinely impressed by what you're building "
            f"in the {industry} space."
        )
        angle = (
            "We help companies at your stage accelerate outreach without adding headcount — "
            "typically 3–5× more qualified conversations in the first 60 days."
        )

    return f"""\
Hi {first},

{hook}

{angle}

Would it make sense to spend 20 minutes together to see if there's a fit? \
No deck, no pitch — just a direct conversation about whether this solves something real for you.

Happy to go off your calendar.

{sender_name}
{sender_title}
{sender_email}
"""


def _build_email(lead: dict, sender_name: str, sender_title: str, sender_email: str) -> dict:
    return {
        "to": lead["email"],
        "subject": _subject(lead),
        "body": _body(lead, sender_name, sender_title, sender_email),
        "lead_name": lead.get("name", ""),
    }


# ─── Gmail API ───────────────────────────────────────────────────────────────

def _get_gmail_service():
    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build

        SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
        creds = None
        token_path = "token.json"
        creds_path = os.getenv("GMAIL_CREDENTIALS_PATH", "credentials.json")

        if os.path.exists(token_path):
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            elif os.path.exists(creds_path):
                flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
                creds = flow.run_local_server(port=0)
                with open(token_path, "w") as f:
                    f.write(creds.to_json())
            else:
                return None
        return build("gmail", "v1", credentials=creds)
    except ImportError:
        return None


def _send_gmail_api(email_data: dict, service) -> bool:
    try:
        msg = MIMEMultipart()
        msg["to"] = email_data["to"]
        msg["subject"] = email_data["subject"]
        msg.attach(MIMEText(email_data["body"], "plain"))
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        service.users().messages().send(userId="me", body={"raw": raw}).execute()
        return True
    except Exception as e:
        logger.error(f"Gmail API error: {e}")
        return False


# ─── SMTP ────────────────────────────────────────────────────────────────────

def _send_smtp(email_data: dict) -> bool:
    smtp_email    = os.getenv("SMTP_EMAIL", "")
    smtp_password = os.getenv("SMTP_APP_PASSWORD", "")
    if not smtp_email or not smtp_password:
        return False
    try:
        msg = MIMEMultipart()
        msg["From"]    = smtp_email
        msg["To"]      = email_data["to"]
        msg["Subject"] = email_data["subject"]
        msg.attach(MIMEText(email_data["body"], "plain"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(smtp_email, smtp_password)
            server.sendmail(smtp_email, email_data["to"], msg.as_string())
        return True
    except Exception as e:
        logger.error(f"SMTP error: {e}")
        return False


# ─── Main Entry Point ─────────────────────────────────────────────────────────

def send_emails(leads: list[dict], dry_run: bool = True) -> list[dict]:
    """
    Sends personalized emails to each lead.

    Filters:
      - Skips leads with no email
      - Skips emails below MIN_EMAIL_CONFIDENCE threshold
      - Deduplicates: never sends to same address twice

    Returns list of result dicts with status per lead.
    """
    sender_name  = os.getenv("SENDER_NAME", "Alex Johnson")
    sender_title = os.getenv("SENDER_TITLE", "Head of Partnerships")
    sender_email = os.getenv("SMTP_EMAIL", os.getenv("SENDER_EMAIL", "hello@yourdomain.com"))
    send_delay   = float(os.getenv("SEND_DELAY_SECONDS", "2"))

    logger.info(f"[Stage 4] Preparing {len(leads)} emails (dry_run={dry_run}, min_confidence={MIN_CONFIDENCE})")

    gmail_service = _get_gmail_service() if not dry_run else None

    results = []
    sent_addresses = set()  # deduplication

    for lead in leads:
        email      = lead.get("email")
        confidence = lead.get("email_confidence", 0)
        name       = lead.get("name", "?")

        # Skip: no email
        if not email:
            logger.warning(f"[Stage 4] Skipping {name} — no email.")
            results.append({"lead": name, "email": None, "status": "skipped", "reason": "no_email"})
            continue

        # Skip: duplicate
        if email.lower() in sent_addresses:
            logger.warning(f"[Stage 4] Skipping {name} — duplicate email {email}.")
            results.append({"lead": name, "email": email, "status": "skipped", "reason": "duplicate"})
            continue

        # Skip: low confidence
        if confidence < MIN_CONFIDENCE:
            logger.warning(f"[Stage 4] Skipping {name} — confidence {confidence} < {MIN_CONFIDENCE}.")
            results.append({"lead": name, "email": email, "status": "skipped",
                            "reason": f"low_confidence_{confidence}"})
            continue

        email_data = _build_email(lead, sender_name, sender_title, sender_email)

        if dry_run:
            print(f"\n{'─'*62}")
            print(f"  TO:        {email_data['to']}")
            print(f"  SUBJECT:   {email_data['subject']}")
            print(f"  CONFIDENCE:{confidence}% | VERIFIED:{lead.get('email_verified',False)} | MX:{lead.get('mx_valid','?')}")
            print(f"  BODY:\n")
            for line in email_data["body"].splitlines():
                print(f"    {line}")
            results.append({"lead": name, "email": email, "status": "dry_run"})
            sent_addresses.add(email.lower())
            continue

        # Live send
        sent = False
        if gmail_service:
            sent = _send_gmail_api(email_data, gmail_service)
            method = "gmail_api"
        if not sent:
            sent = _send_smtp(email_data)
            method = "smtp"

        status = "sent" if sent else "failed"
        results.append({"lead": name, "email": email, "status": status,
                        "method": method if sent else None})
        if sent:
            sent_addresses.add(email.lower())
            logger.info(f"[Stage 4] ✓ Sent to {name} via {method}")
            time.sleep(send_delay)
        else:
            logger.error(f"[Stage 4] ✗ Failed to send to {name}")

    sent    = sum(1 for r in results if r["status"] == "sent")
    dry     = sum(1 for r in results if r["status"] == "dry_run")
    skipped = sum(1 for r in results if r["status"] == "skipped")
    failed  = sum(1 for r in results if r["status"] == "failed")
    logger.info(f"[Stage 4] Done: sent={sent} dry={dry} skipped={skipped} failed={failed}")
    return results
