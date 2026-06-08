"""
Stage 1: Company Finder
-----------------------
Given a seed domain, finds genuinely similar companies — not a hardcoded list.

Strategy (tiered, each feeds the next on failure):

  Tier 1 — Clearbit Similarity + Enrich (free, no key)
           Fetches the seed company's category/industry, then searches
           Clearbit for other companies in that same category.

  Tier 2 — SerpAPI Google Search (free 100/month, SERPAPI_KEY)
           Searches Google for "companies like {company} competitors"
           and extracts domains from the organic results.

  Tier 3 — Tavily AI Search (free 1000/month, TAVILY_API_KEY)
           Uses Tavily's semantic search for better competitor discovery.

  Tier 4 — DuckDuckGo HTML scrape (zero API, always available)
           Scrapes DDG results for "{company} competitors alternatives"
           and parses out company domains.

No results are hardcoded. Every run discovers based on the actual seed.
"""

import os
import re
import time
import logging
import requests
from urllib.parse import urlparse, urlencode, quote_plus

logger = logging.getLogger(__name__)

# Domains to exclude from results (aggregators, social, not companies)
EXCLUDED_DOMAINS = {
    "linkedin.com", "twitter.com", "facebook.com", "instagram.com",
    "youtube.com", "reddit.com", "crunchbase.com", "wikipedia.org",
    "g2.com", "capterra.com", "trustpilot.com", "glassdoor.com",
    "techcrunch.com", "forbes.com", "bloomberg.com", "wired.com",
    "medium.com", "substack.com", "github.com", "producthunt.com",
    "alternativeto.net", "slashdot.org", "getapp.com", "sourceforge.net",
}


def _extract_domain(url: str) -> str | None:
    """Extract clean domain from a URL string."""
    try:
        parsed = urlparse(url if "://" in url else f"https://{url}")
        domain = parsed.netloc.replace("www.", "").strip()
        if "." in domain and domain not in EXCLUDED_DOMAINS:
            return domain
    except Exception:
        pass
    return None


def _make_request(url: str, params: dict = None, timeout: int = 10, headers: dict = None) -> requests.Response | None:
    """HTTP GET with retry logic (up to 3 attempts, exponential backoff)."""
    for attempt in range(3):
        try:
            resp = requests.get(url, params=params, headers=headers or {}, timeout=timeout)
            if resp.status_code == 429:
                wait = 2 ** attempt
                logger.warning(f"Rate limited at {url}, waiting {wait}s...")
                time.sleep(wait)
                continue
            return resp
        except requests.exceptions.Timeout:
            logger.warning(f"Timeout on attempt {attempt+1} for {url}")
            time.sleep(1)
        except Exception as e:
            logger.warning(f"Request error: {e}")
            break
    return None


# ─── Tier 1: Clearbit ────────────────────────────────────────────────────────

def _clearbit_discover(seed_domain: str, limit: int) -> list[dict] | None:
    """
    Uses Clearbit's free Autocomplete API.
    First looks up the seed to get its industry keyword,
    then searches for similar companies in that space.
    """
    # Step 1: get seed company metadata
    resp = _make_request(
        "https://autocomplete.clearbit.com/v1/companies/suggest",
        params={"query": seed_domain.split(".")[0]}
    )
    if not resp or resp.status_code != 200:
        return None

    suggestions = resp.json()
    seed_info = next((s for s in suggestions if seed_domain in s.get("domain", "")), None)

    # Pick search keyword from company name or category
    if seed_info:
        keyword = seed_info.get("name", seed_domain.split(".")[0])
        industry = (seed_info.get("category") or {}).get("industry", "")
    else:
        keyword = seed_domain.split(".")[0]
        industry = ""

    # Step 2: search for competitors using industry keyword.
    # If no industry found, search "{company name} competitor" to avoid getting
    # the company's own subdomains back (e.g. searching "amazon" returns mturk.com).
    company_name = seed_domain.split(".")[0]
    if industry:
        search_term = industry
    else:
        search_term = f"{keyword} competitor"

    resp2 = _make_request(
        "https://autocomplete.clearbit.com/v1/companies/suggest",
        params={"query": search_term}
    )
    if not resp2 or resp2.status_code != 200:
        return None

    results = []
    for co in resp2.json():
        domain = co.get("domain", "")
        # Filter out: seed domain itself, excluded domains, and any domain that
        # contains the seed company name (catches subdomains like mturk, amazon.it, etc.)
        if (
            domain
            and seed_domain not in domain
            and company_name not in domain
            and domain not in EXCLUDED_DOMAINS
        ):
            results.append({
                "name": co.get("name", domain.split(".")[0].capitalize()),
                "domain": domain,
                "industry": (co.get("category") or {}).get("industry", industry or "Technology"),
                "source": "clearbit",
            })

    return results[:limit] if results else None


# ─── Tier 2: SerpAPI ─────────────────────────────────────────────────────────

def _serpapi_discover(seed_domain: str, api_key: str, limit: int) -> list[dict] | None:
    """
    Google search via SerpAPI for competitor/alternative companies.
    """
    company_name = seed_domain.split(".")[0].capitalize()
    query = f"{company_name} competitors alternatives similar companies"

    resp = _make_request(
        "https://serpapi.com/search",
        params={"q": query, "api_key": api_key, "num": 20}
    )
    if not resp or resp.status_code != 200:
        return None

    data = resp.json()
    results = []
    seen = set()

    for item in data.get("organic_results", []):
        link = item.get("link", "")
        title = item.get("title", "")
        domain = _extract_domain(link)
        if domain and domain not in seen and seed_domain not in domain:
            seen.add(domain)
            results.append({
                "name": title.split("|")[0].split("-")[0].split("–")[0].strip()[:40],
                "domain": domain,
                "industry": "Technology",
                "source": "serpapi",
            })
        if len(results) >= limit:
            break

    return results if results else None


# ─── Tier 3: Tavily ──────────────────────────────────────────────────────────

def _tavily_discover(seed_domain: str, api_key: str, limit: int) -> list[dict] | None:
    """
    Uses Tavily's semantic search API (free 1000/month).
    """
    company_name = seed_domain.split(".")[0].capitalize()
    try:
        resp = requests.post(
            "https://api.tavily.com/search",
            json={
                "api_key": api_key,
                "query": f"top competitors and alternatives to {company_name}",
                "search_depth": "basic",
                "max_results": 10,
            },
            timeout=10,
        )
        if resp.status_code != 200:
            return None

        results = []
        seen = set()
        for item in resp.json().get("results", []):
            domain = _extract_domain(item.get("url", ""))
            if domain and domain not in seen and seed_domain not in domain:
                seen.add(domain)
                results.append({
                    "name": domain.split(".")[0].capitalize(),
                    "domain": domain,
                    "industry": "Technology",
                    "source": "tavily",
                })
        return results[:limit] if results else None
    except Exception as e:
        logger.warning(f"Tavily error: {e}")
        return None


# ─── Tier 4: DuckDuckGo HTML scrape ──────────────────────────────────────────

def _ddg_discover(seed_domain: str, limit: int) -> list[dict] | None:
    """
    Scrapes DuckDuckGo HTML results — zero API key needed.
    Looks for competitor/alternative result URLs.
    """
    company = seed_domain.split(".")[0]
    query = f"{company} competitors alternatives site:(.com OR .io OR .ai OR .co)"

    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    resp = _make_request(
        "https://html.duckduckgo.com/html/",
        params={"q": query},
        headers=headers,
        timeout=12,
    )
    if not resp or resp.status_code != 200:
        return None

    # Extract URLs from result snippets
    url_pattern = re.compile(
        r'href="(https?://(?!duckduckgo)[^\s"]+)"',
        re.IGNORECASE
    )
    found_urls = url_pattern.findall(resp.text)

    results = []
    seen = set()
    for url in found_urls:
        domain = _extract_domain(url)
        if (
            domain
            and domain not in seen
            and seed_domain not in domain
            and not any(x in domain for x in ["duckduck", "bing.com", "google.com"])
        ):
            seen.add(domain)
            results.append({
                "name": domain.split(".")[0].replace("-", " ").capitalize(),
                "domain": domain,
                "industry": "Technology",
                "source": "duckduckgo",
            })
        if len(results) >= limit:
            break

    return results if results else None


# ─── Deduplication ───────────────────────────────────────────────────────────

def _dedupe(companies: list[dict]) -> list[dict]:
    """Remove duplicate domains, keeping first occurrence."""
    seen = set()
    out = []
    for co in companies:
        d = co.get("domain", "").lower()
        if d and d not in seen:
            seen.add(d)
            out.append(co)
    return out


# ─── Main Entry Point ─────────────────────────────────────────────────────────

def find_similar_companies(seed_domain: str, limit: int = 5) -> list[dict]:
    """
    Discovers genuinely similar companies for a given seed domain.
    Tries 4 real discovery methods in priority order.
    Never returns hardcoded results — always based on the actual seed.
    """
    seed_domain = (
        seed_domain.strip().lower()
        .replace("https://", "").replace("http://", "")
        .split("/")[0]
    )
    logger.info(f"[Stage 1] Discovering companies similar to: {seed_domain}")

    # Tier 1: Clearbit (free, no key)
    logger.info("[Stage 1] Trying Clearbit industry search...")
    results = _clearbit_discover(seed_domain, limit=limit * 2)
    if results:
        results = _dedupe(results)[:limit]
        logger.info(f"[Stage 1] Clearbit → {len(results)} companies")
        return results

    # Tier 2: SerpAPI
    serpapi_key = os.getenv("SERPAPI_KEY", "")
    if serpapi_key:
        logger.info("[Stage 1] Trying SerpAPI competitor search...")
        results = _serpapi_discover(seed_domain, serpapi_key, limit=limit * 2)
        if results:
            results = _dedupe(results)[:limit]
            logger.info(f"[Stage 1] SerpAPI → {len(results)} companies")
            return results

    # Tier 3: Tavily
    tavily_key = os.getenv("TAVILY_API_KEY", "")
    if tavily_key:
        logger.info("[Stage 1] Trying Tavily semantic search...")
        results = _tavily_discover(seed_domain, tavily_key, limit=limit * 2)
        if results:
            results = _dedupe(results)[:limit]
            logger.info(f"[Stage 1] Tavily → {len(results)} companies")
            return results

    # Tier 4: DuckDuckGo scrape (no API key required)
    logger.info("[Stage 1] Trying DuckDuckGo scrape...")
    results = _ddg_discover(seed_domain, limit=limit * 2)
    if results:
        results = _dedupe(results)[:limit]
        logger.info(f"[Stage 1] DuckDuckGo → {len(results)} companies")
        return results

    logger.error("[Stage 1] All discovery methods failed.")
    return []
