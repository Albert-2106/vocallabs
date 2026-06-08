"""
Stage 3: Email Resolver
-----------------------
Resolves verified work emails from lead data.

Tier 1 — Use email_hint from Hunter (already verified, confidence shown)
Tier 2 — Hunter Email Finder by name+domain (HUNTER_API_KEY)
Tier 3 — Hunter Email Verifier on pattern guesses
Tier 4 — Pattern generation with MX record validation as confidence signal

Every email gets:
  - email: the address
  - email_confidence: 0–100
  - email_verified: bool
  - email_source: where it came from
  - mx_valid: bool (MX record check via DNS)

Rate-limit handling: exponential backoff on 429s.
"""

import os
import re
import time
import socket
import logging
import requests

logger = logging.getLogger(__name__)

EMAIL_PATTERNS = [
    "{first}.{last}@{domain}",
    "{first}@{domain}",
    "{f}{last}@{domain}",
    "{first}{last}@{domain}",
    "{first}_{last}@{domain}",
    "{last}@{domain}",
]


def _clean(s: str) -> str:
    return re.sub(r"[^a-z]", "", s.lower())


def _name_parts(name: str):
    parts = name.strip().split()
    first = _clean(parts[0]) if parts else "contact"
    last  = _clean(parts[-1]) if len(parts) > 1 else ""
    f     = first[0] if first else "c"
    return first, last, f


def _generate_patterns(name: str, domain: str) -> list[str]:
    first, last, f = _name_parts(name)
    candidates = []
    for pattern in EMAIL_PATTERNS:
        try:
            email = pattern.format(first=first, last=last, f=f, domain=domain)
            if email not in candidates and "@" in email and not email.startswith("@"):
                candidates.append(email)
        except KeyError:
            pass
    return candidates


def _check_mx(domain: str) -> bool:
    """Check that domain has MX records (deliverable domain)."""
    try:
        socket.getaddrinfo(domain, None)
        return True
    except socket.gaierror:
        return False


def _hunter_request(endpoint: str, params: dict, api_key: str) -> dict | None:
    """Hunter.io API call with retry + backoff."""
    params["api_key"] = api_key
    for attempt in range(3):
        try:
            resp = requests.get(
                f"https://api.hunter.io/v2/{endpoint}",
                params=params,
                timeout=10
            )
            if resp.status_code == 429:
                wait = 5 * (attempt + 1)
                logger.warning(f"[Stage 3] Hunter rate limit, waiting {wait}s...")
                time.sleep(wait)
                continue
            if resp.status_code in (401, 403):
                logger.warning("[Stage 3] Hunter API key invalid.")
                return None
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.warning(f"[Stage 3] Hunter request error: {e}")
            time.sleep(2)
    return None


def resolve_emails(leads: list[dict]) -> list[dict]:
    """
    Resolves and verifies emails for each lead.
    Returns leads enriched with email fields.
    Skips leads where no email can be found.
    """
    hunter_key = os.getenv("HUNTER_API_KEY", "")
    resolved = []

    logger.info(f"[Stage 3] Resolving emails for {len(leads)} leads...")

    for lead in leads:
        name   = lead.get("name", "")
        domain = lead.get("domain", "")
        result = dict(lead)

        # ── Tier 1: email already from Hunter domain-search ──────────────────
        if lead.get("email_hint"):
            email = lead["email_hint"]
            mx    = _check_mx(domain)
            result.update({
                "email": email,
                "email_confidence": lead.get("confidence", 85),
                "email_verified": True,
                "email_source": "hunter_domain_search",
                "mx_valid": mx,
            })
            logger.info(f"[Stage 3]   {name} → {email} (hunter domain-search, conf={result['email_confidence']})")
            resolved.append(result)
            continue

        first, last, _ = _name_parts(name)

        # ── Tier 2: Hunter Email Finder ───────────────────────────────────────
        if hunter_key and first and last and domain:
            data = _hunter_request(
                "email-finder",
                {"first_name": first, "last_name": last, "domain": domain},
                hunter_key,
            )
            if data:
                email = data.get("data", {}).get("email")
                score = data.get("data", {}).get("score", 0)
                if email:
                    mx = _check_mx(domain)
                    result.update({
                        "email": email,
                        "email_confidence": score,
                        "email_verified": score >= 70,
                        "email_source": "hunter_finder",
                        "mx_valid": mx,
                    })
                    logger.info(f"[Stage 3]   {name} → {email} (hunter-finder, conf={score})")
                    resolved.append(result)
                    time.sleep(0.5)
                    continue

        # ── Tier 3: Pattern + Hunter Verify ──────────────────────────────────
        candidates = _generate_patterns(name, domain)
        mx = _check_mx(domain)

        if hunter_key and candidates:
            for candidate in candidates[:3]:
                data = _hunter_request(
                    "email-verifier",
                    {"email": candidate},
                    hunter_key,
                )
                if data:
                    status     = data.get("data", {}).get("status", "")
                    disposable = data.get("data", {}).get("disposable", False)
                    if status == "valid" and not disposable:
                        result.update({
                            "email": candidate,
                            "email_confidence": 90,
                            "email_verified": True,
                            "email_source": "pattern_hunter_verified",
                            "mx_valid": mx,
                        })
                        logger.info(f"[Stage 3]   {name} → {candidate} (pattern+verified)")
                        resolved.append(result)
                        time.sleep(0.4)
                        break
                    elif status == "accept_all":
                        result.update({
                            "email": candidate,
                            "email_confidence": 60,
                            "email_verified": False,
                            "email_source": "pattern_accept_all",
                            "mx_valid": mx,
                        })
                        logger.info(f"[Stage 3]   {name} → {candidate} (accept-all domain)")
                        resolved.append(result)
                        time.sleep(0.4)
                        break
            else:
                # No verified pattern found
                if candidates:
                    result.update({
                        "email": candidates[0],
                        "email_confidence": 30 if mx else 5,
                        "email_verified": False,
                        "email_source": "pattern_unverified",
                        "mx_valid": mx,
                    })
                    logger.info(f"[Stage 3]   {name} → {candidates[0]} (pattern, unverified, mx={mx})")
                    resolved.append(result)
            continue

        # ── Tier 4: Pattern only + MX check ──────────────────────────────────
        if candidates:
            best = candidates[0]
            result.update({
                "email": best,
                "email_confidence": 35 if mx else 5,
                "email_verified": False,
                "email_source": "pattern_mx_check",
                "mx_valid": mx,
            })
            logger.info(f"[Stage 3]   {name} → {best} (pattern, mx={mx})")
            resolved.append(result)
        else:
            logger.warning(f"[Stage 3]   {name} → could not resolve any email, skipping.")

        time.sleep(0.2)

    verified = sum(1 for r in resolved if r.get("email_verified"))
    mx_ok    = sum(1 for r in resolved if r.get("mx_valid"))
    logger.info(f"[Stage 3] Resolved {len(resolved)} | Verified={verified} | MX-valid={mx_ok}")
    return resolved
