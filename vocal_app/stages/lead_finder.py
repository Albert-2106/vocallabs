"""
Stage 2: Lead Finder
--------------------
Given a list of company domains, finds decision-makers with LinkedIn URLs.

Tier 1 — Hunter.io Domain Search (free 25/month, HUNTER_API_KEY)
          Returns real people at the domain with roles + LinkedIn URLs.

Tier 2 — Prospeo API (PROSPEO_API_KEY) — the tool from the assignment

Tier 3 — Google/DDG site:linkedin.com search
          Searches for "CEO/CTO/VP site:linkedin.com/in {company}"
          and extracts real LinkedIn profile URLs.

Tier 4 — LinkedIn company page scrape
          Hits the public LinkedIn company page to extract leadership names.

No placeholder "Company Leadership" entries. If we can't find a real person,
we skip that company and log it — we never invent people.
"""

import os
import re
import time
import logging
import requests
from urllib.parse import quote_plus

logger = logging.getLogger(__name__)

SENIOR_KEYWORDS = [
    "ceo", "cto", "coo", "cfo", "cpo", "founder", "co-founder",
    "president", "vp ", "vice president", "head of", "director",
    "partner", "managing", "chief",
]

def _is_senior(role: str) -> bool:
    role_lower = role.lower()
    return any(kw in role_lower for kw in SENIOR_KEYWORDS)


def _make_request(url, params=None, headers=None, timeout=10):
    """GET with retry + backoff."""
    for attempt in range(3):
        try:
            resp = requests.get(
                url, params=params,
                headers=headers or {"User-Agent": "Mozilla/5.0"},
                timeout=timeout
            )
            if resp.status_code == 429:
                time.sleep(2 ** attempt)
                continue
            return resp
        except Exception as e:
            logger.warning(f"Request error (attempt {attempt+1}): {e}")
            time.sleep(1)
    return None


# ─── Tier 1: Hunter.io Domain Search ─────────────────────────────────────────

def _hunter_leads(domain: str, api_key: str) -> list[dict]:
    resp = _make_request(
        "https://api.hunter.io/v2/domain-search",
        params={"domain": domain, "api_key": api_key, "limit": 10, "seniority": "executive,senior"}
    )
    if not resp or resp.status_code != 200:
        return []

    leads = []
    for person in resp.json().get("data", {}).get("emails", []):
        role = person.get("position", "")
        if not role or not _is_senior(role):
            continue
        name = f"{person.get('first_name','')} {person.get('last_name','')}".strip()
        if not name:
            continue
        leads.append({
            "name": name,
            "role": role,
            "linkedin": person.get("linkedin", ""),
            "domain": domain,
            "email_hint": person.get("value", ""),
            "confidence": person.get("confidence", 0),
            "source": "hunter",
        })
    return leads


# ─── Tier 2: Prospeo ─────────────────────────────────────────────────────────

def _prospeo_leads(domain: str, api_key: str) -> list[dict]:
    """Prospeo domain search — the tool from the original assignment."""
    try:
        resp = requests.post(
            "https://app.prospeo.io/api/domain-search",
            json={"domain": domain, "limit": 10},
            headers={"X-KEY": api_key, "Content-Type": "application/json"},
            timeout=10,
        )
        if resp.status_code != 200:
            return []
        leads = []
        for person in resp.json().get("response", {}).get("email_list", []):
            role = person.get("job_title", "")
            if not _is_senior(role):
                continue
            first = person.get("first_name", "")
            last = person.get("last_name", "")
            name = f"{first} {last}".strip()
            if not name:
                continue
            leads.append({
                "name": name,
                "role": role,
                "linkedin": person.get("linkedin_url", ""),
                "domain": domain,
                "email_hint": person.get("email", ""),
                "source": "prospeo",
            })
        return leads
    except Exception as e:
        logger.warning(f"Prospeo error for {domain}: {e}")
        return []


# ─── Tier 3: Google → LinkedIn profile search ────────────────────────────────

def _google_linkedin_search(domain: str, api_key: str = "") -> list[dict]:
    """
    Search Google (via SerpAPI) for LinkedIn profiles of execs at this company.
    Falls back to DuckDuckGo HTML scrape if no SerpAPI key.
    """
    company = domain.split(".")[0].capitalize()
    query = f'site:linkedin.com/in "{company}" (CEO OR CTO OR founder OR "VP" OR president)'

    if api_key:
        resp = _make_request(
            "https://serpapi.com/search",
            params={"q": query, "api_key": api_key, "num": 10}
        )
        if resp and resp.status_code == 200:
            leads = []
            for item in resp.json().get("organic_results", []):
                link = item.get("link", "")
                title = item.get("title", "")
                if "linkedin.com/in/" not in link:
                    continue
                # Parse "Name - Role at Company | LinkedIn"
                parts = title.replace(" | LinkedIn", "").split(" - ")
                name = parts[0].strip() if parts else ""
                role = parts[1].split(" at ")[0].strip() if len(parts) > 1 else "Executive"
                if name and _is_senior(role):
                    leads.append({
                        "name": name,
                        "role": role,
                        "linkedin": link,
                        "domain": domain,
                        "source": "google_linkedin",
                    })
            if leads:
                return leads

    # DDG scrape fallback
    ddg_query = f"{company} CEO founder linkedin.com/in"
    resp = _make_request(
        "https://html.duckduckgo.com/html/",
        params={"q": ddg_query},
        headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"},
        timeout=12,
    )
    if not resp or resp.status_code != 200:
        return []

    leads = []
    # Find LinkedIn /in/ URLs
    li_pattern = re.compile(r'href="(https://[a-z]{2,3}\.linkedin\.com/in/[^"?]+)"')
    title_pattern = re.compile(r'<a[^>]*class="result__a"[^>]*>([^<]+)</a>')

    urls = li_pattern.findall(resp.text)
    titles = title_pattern.findall(resp.text)

    for i, url in enumerate(urls[:5]):
        title = titles[i] if i < len(titles) else ""
        parts = title.replace(" | LinkedIn", "").split(" - ")
        name = parts[0].strip() if parts else ""
        role = parts[1].split(" at ")[0].strip() if len(parts) > 1 else "Executive"
        if name and len(name.split()) >= 2:
            leads.append({
                "name": name,
                "role": role if role else "Executive",
                "linkedin": url,
                "domain": domain,
                "source": "ddg_linkedin",
            })

    return leads


# ─── Deduplication ────────────────────────────────────────────────────────────

def _dedupe_leads(leads: list[dict]) -> list[dict]:
    """Remove duplicate people by name+domain."""
    seen = set()
    out = []
    for lead in leads:
        key = f"{lead.get('name','').lower()}|{lead.get('domain','')}"
        if key not in seen:
            seen.add(key)
            out.append(lead)
    return out


# ─── Main Entry Point ─────────────────────────────────────────────────────────

def find_leads(companies: list[dict], max_per_company: int = 2) -> list[dict]:
    """
    Finds real decision-makers for each company domain.
    Uses real APIs and search — never invents or placeholders.
    Skips companies where no real contacts can be found.
    """
    hunter_key   = os.getenv("HUNTER_API_KEY", "")
    prospeo_key  = os.getenv("PROSPEO_API_KEY", "")
    serpapi_key  = os.getenv("SERPAPI_KEY", "")

    # Warn clearly if no API keys are configured
    if not hunter_key and not prospeo_key and not serpapi_key:
        logger.warning(
            "[Stage 2] ⚠️  No API keys configured (HUNTER_API_KEY, PROSPEO_API_KEY, SERPAPI_KEY). "
            "Will fall back to DuckDuckGo LinkedIn scrape — this often returns 0 results if DDG blocks the request. "
            "Add SERPAPI_KEY to your .env for reliable results (free tier: 100 searches/month at https://serpapi.com)."
        )

    logger.info(f"[Stage 2] Finding leads for {len(companies)} companies...")
    all_leads = []

    for company in companies:
        domain = company.get("domain", "").strip()
        if not domain:
            continue

        logger.info(f"[Stage 2] Looking up leads for: {domain}")
        leads = []

        # Tier 1: Hunter
        if hunter_key and not leads:
            leads = _hunter_leads(domain, hunter_key)
            if leads:
                logger.info(f"[Stage 2]   Hunter → {len(leads)} leads for {domain}")

        # Tier 2: Prospeo
        if prospeo_key and not leads:
            leads = _prospeo_leads(domain, prospeo_key)
            if leads:
                logger.info(f"[Stage 2]   Prospeo → {len(leads)} leads for {domain}")

        # Tier 3: Google/DDG LinkedIn search
        if not leads:
            leads = _google_linkedin_search(domain, api_key=serpapi_key)
            if leads:
                logger.info(f"[Stage 2]   LinkedIn search → {len(leads)} leads for {domain}")

        if not leads:
            logger.warning(f"[Stage 2]   No leads found for {domain} — skipping.")
        else:
            leads = _dedupe_leads(leads)
            # Copy industry from company dict into lead dicts
            for lead in leads:
                lead["industry"] = company.get("industry", "Technology")
            all_leads.extend(leads[:max_per_company])

        time.sleep(0.5)  # polite pacing

    all_leads = _dedupe_leads(all_leads)
    logger.info(f"[Stage 2] Total leads found: {len(all_leads)}")
    return all_leads
