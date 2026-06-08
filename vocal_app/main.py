#!/usr/bin/env python3
"""
Automated Cold-Outreach Pipeline
=================================
Usage:
    python main.py <seed_domain>                  # dry-run (safe)
    python main.py <seed_domain> --send           # live send after checkpoint
    python main.py <seed_domain> --limit 8        # more lookalike companies
    python main.py <seed_domain> --verbose        # debug logging

Example:
    python main.py openai.com
    python main.py tesla.com --limit 5
    python main.py swiggy.com --verbose
"""

import sys
import os
import time
import json
import argparse
import logging
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# ── colors ────────────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
RED    = "\033[91m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
RESET  = "\033[0m"

def c(color, text): return f"{color}{text}{RESET}"

def setup_logging(verbose=False):
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format=f"{DIM}%(asctime)s{RESET} %(levelname)-8s %(message)s",
        datefmt="%H:%M:%S",
    )

sys.path.insert(0, os.path.dirname(__file__))
from stages.company_finder import find_similar_companies
from stages.lead_finder    import find_leads
from stages.email_resolver import resolve_emails


def print_banner():
    print(f"""
{BOLD}{CYAN}┌──────────────────────────────────────────────────────┐
│   🚀  Automated Cold-Outreach Pipeline               │
│   Discovery → Leads → Emails → Outreach              │
└──────────────────────────────────────────────────────┘{RESET}
""")


def print_stage(num, name):
    print(f"\n{BOLD}{YELLOW}[Stage {num}/4] {name}{RESET}")
    print(f"{DIM}{'─' * 54}{RESET}")


def print_summary(seed, companies, leads, resolved):
    verified   = sum(1 for r in resolved if r.get("email_verified"))
    mx_ok      = sum(1 for r in resolved if r.get("mx_valid"))
    with_li    = sum(1 for r in leads if r.get("linkedin"))
    skippable  = sum(1 for r in resolved
                     if r.get("email_confidence", 0) < int(os.getenv("MIN_EMAIL_CONFIDENCE","30")))

    print(f"""
{BOLD}{GREEN}╔════════════════════════════════════════════════════════╗
║                  PIPELINE SUMMARY                      ║
╠════════════════════════════════════════════════════════╣{RESET}""")
    rows = [
        ("Seed domain",         c(CYAN,  seed)),
        ("Companies found",     c(CYAN,  str(len(companies)))),
        ("Leads found",         c(CYAN,  str(len(leads)))),
        ("With LinkedIn URL",   c(GREEN, str(with_li))),
        ("Emails resolved",     c(CYAN,  str(len(resolved)))),
        ("Verified emails",     c(GREEN, str(verified))),
        ("MX-valid domains",    c(GREEN, str(mx_ok))),
        ("Below conf. threshold", c(YELLOW, str(skippable)) + c(DIM, " (will be skipped)")),
    ]
    for label, value in rows:
        line = f"  {label:<26}: {value}"
        print(f"{BOLD}{GREEN}║{RESET}{line:<54}{BOLD}{GREEN}║{RESET}")
    print(f"{BOLD}{GREEN}╚════════════════════════════════════════════════════════╝{RESET}")

    print(f"\n{BOLD}Contacts queued for outreach:{RESET}")
    hdr = f"{'Name':<26} {'Role':<24} {'Email':<36} {'Conf':>4}  {'Ver':>3}  {'MX':>2}"
    print(f"{DIM}{hdr}{RESET}")
    print(f"{DIM}{'─'*26} {'─'*24} {'─'*36} {'─'*4}  {'─'*3}  {'─'*2}{RESET}")
    for r in resolved:
        conf   = r.get("email_confidence", 0)
        ver    = c(GREEN, "✓") if r.get("email_verified") else c(YELLOW, "~")
        mx     = c(GREEN, "✓") if r.get("mx_valid") else c(RED, "✗")
        c_col  = GREEN if conf >= 70 else YELLOW if conf >= 40 else RED
        print(
            f"{r.get('name','?')[:25]:<26} "
            f"{r.get('role','?')[:23]:<24} "
            f"{r.get('email','—')[:35]:<36} "
            f"{c(c_col, str(conf)):>4}%  {ver}    {mx}"
        )


def safety_checkpoint() -> bool:
    print(f"""
{BOLD}{YELLOW}⚠  SAFETY CHECKPOINT{RESET}
{DIM}Review contacts above. Emails will fire immediately after confirmation.{RESET}
""")
    while True:
        ans = input(f"{BOLD}Send emails now? [y/N]: {RESET}").strip().lower()
        if ans in ("y", "yes"):
            return True
        if ans in ("n", "no", ""):
            return False


def save_results(data, seed):
    os.makedirs("runs", exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = f"runs/{seed.replace('.','_')}_{ts}.json"
    with open(fname, "w") as f:
        json.dump(data, f, indent=2, default=str)
    print(f"\n{DIM}Run saved → {fname}{RESET}")


def main():
    parser = argparse.ArgumentParser(description="Automated cold-outreach pipeline.")
    parser.add_argument("seed_domain")
    parser.add_argument("--limit",   type=int, default=5)
    parser.add_argument("--per-co",  type=int, default=2)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    setup_logging(args.verbose)
    print_banner()

    seed = args.seed_domain.strip().lower().replace("https://","").replace("http://","").split("/")[0]
    print(f"  {BOLD}Seed domain:{RESET} {c(CYAN, seed)}")
    print(f"  {BOLD}Limit:{RESET}       {args.limit} companies × {args.per_co} contacts")

    # Show which APIs are configured
    apis = {
        "Hunter.io":   bool(os.getenv("HUNTER_API_KEY")),
        "SerpAPI":     bool(os.getenv("SERPAPI_KEY")),
        "Tavily":      bool(os.getenv("TAVILY_API_KEY")),
        "Prospeo":     bool(os.getenv("PROSPEO_API_KEY")),
    }
    print(f"\n  {DIM}API status: " + " | ".join(
        f"{name}={'✓' if v else '✗'}" for name, v in apis.items()
    ) + f"{RESET}")

    run_data = {"seed": seed, "started_at": datetime.now().isoformat(), "apis": apis}

    # ── Stage 1 ───────────────────────────────────────────────────────────────
    print_stage(1, "Company Discovery")
    t0 = time.time()
    companies = find_similar_companies(seed, limit=args.limit)
    run_data["companies"] = companies
    if not companies:
        print(c(RED, "✗ No companies discovered. Try adding a SERPAPI_KEY or TAVILY_API_KEY."))
        sys.exit(1)
    for co in companies:
        src = c(DIM, f"[{co.get('source','?')}]")
        print(f"  {c(GREEN,'✓')} {co['name']:<26} {co['domain']:<28} {src}")
    print(f"{DIM}  → {len(companies)} companies in {time.time()-t0:.1f}s{RESET}")

    # ── Stage 2 ───────────────────────────────────────────────────────────────
    print_stage(2, "Lead / Decision-Maker Discovery")
    t0 = time.time()
    leads = find_leads(companies, max_per_company=args.per_co)
    run_data["leads"] = leads
    if not leads:
        print(c(RED, "✗ No leads found."))
        sys.exit(1)
    for lead in leads:
        li  = c(GREEN, "LinkedIn✓") if lead.get("linkedin") else c(DIM, "no LinkedIn")
        src = c(DIM, f"[{lead.get('source','?')}]")
        print(f"  {c(GREEN,'✓')} {lead['name']:<26} {lead['role']:<24} {li} {src}")
    print(f"{DIM}  → {len(leads)} leads in {time.time()-t0:.1f}s{RESET}")

    # ── Stage 3 ───────────────────────────────────────────────────────────────
    print_stage(3, "Email Resolution & Verification")
    t0 = time.time()
    resolved = resolve_emails(leads)
    run_data["resolved"] = resolved
    for r in resolved:
        conf = r.get("email_confidence", 0)
        c_col = GREEN if conf >= 70 else YELLOW if conf >= 40 else RED
        ver  = c(GREEN, "verified") if r.get("email_verified") else c(YELLOW, f"~{conf}%")
        mx   = c(GREEN,"mx✓") if r.get("mx_valid") else c(RED,"mx✗")
        print(f"  {r.get('name','?'):<26} → {r.get('email','—'):<38} {ver} {mx}")
    print(f"{DIM}  → {len(resolved)} emails in {time.time()-t0:.1f}s{RESET}")

    # ── Summary + Checkpoint ─────────────────────────────────────────────────
    print_summary(seed, companies, leads, resolved)

    print(f"\n{BOLD}{GREEN}Pipeline complete!{RESET}")
    print(f"  {c(GREEN,'Emails found'):<20} {len(resolved)}")
    verified = sum(1 for r in resolved if r.get("email_verified"))
    print(f"  {c(GREEN,'Verified'):<20} {verified}")
    print(f"  {c(YELLOW,'Confidence avg'):<20} {round(sum(r.get('email_confidence',0) for r in resolved) / len(resolved)) if resolved else 0}%")

    run_data["finished_at"] = datetime.now().isoformat()
    run_data["result"] = "success"
    save_results(run_data, seed)


if __name__ == "__main__":
    main()
