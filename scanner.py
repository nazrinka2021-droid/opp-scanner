"""
Opportunity Scanner — Multi-Agent Pipeline
Searches the web for legal, AI/tech, and sales opportunities
relevant to a law student in Scotland/UK/Europe/Azerbaijan.

Runs as a GitHub Action on a cron schedule.
Delivers new finds to a Notion database.
"""

import anthropic
import json
import hashlib
import os
import sys
from datetime import datetime, date
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

MODEL = os.environ.get("SCANNER_MODEL", "claude-haiku-4-5-20251001")
MAX_SEARCHES_PER_AGENT = int(os.environ.get("MAX_SEARCHES", "8"))
SEEN_FILE = Path(__file__).parent / "data" / "seen.json"

client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env


# ---------------------------------------------------------------------------
# Memory store  (dedup by URL hash)
# ---------------------------------------------------------------------------

def load_seen() -> set:
    if SEEN_FILE.exists():
        data = json.loads(SEEN_FILE.read_text())
        return set(data.get("hashes", []))
    return set()


def save_seen(hashes: set):
    SEEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    SEEN_FILE.write_text(json.dumps({
        "hashes": sorted(hashes),
        "last_run": datetime.utcnow().isoformat()
    }, indent=2))


def url_hash(url: str) -> str:
    return hashlib.sha256(url.strip().lower().encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Shared profile context (injected into every agent)
# ---------------------------------------------------------------------------

PROFILE_CONTEXT = """
TARGET PERSON PROFILE:
- First-year MA International Relations and Law student, University of Edinburgh
- Pursuing SQE qualification to become a commercial solicitor in London
- Active in ELSA Edinburgh (Director of Academic Activities)
- Co-founder of a legal-tech startup (AI-powered business development tool)
- Works in AI-driven lead generation / sales (setter & closer)
- Regions of interest: Scotland, UK (especially London & Edinburgh), Europe, Azerbaijan (Baku)
- Languages: English, Russian, French, Azerbaijani
- Interested in: commercial law, legal tech, AI/ML, sales, entrepreneurship, content creation
"""


# ---------------------------------------------------------------------------
# Agent definitions
# ---------------------------------------------------------------------------

LEGAL_SYSTEM = f"""You are an opportunity scout specialising in LEGAL career events and opportunities.

{PROFILE_CONTEXT}

YOUR SEARCH MANDATE — search the web thoroughly for CURRENT and UPCOMING:
• Legal internships, vacation schemes, training contracts, insight days, open days
• Law student workshops, competitions, mooting, essay prizes
• Legal networking events, panel discussions, webinars
• Scholarships, bursaries, and funding for law students
• SQE preparation events or resources
• ELSA events across Europe
• Legal tech events and hackathons
• Any commercial law firm events (especially magic circle, silver circle, US firms in London)

REGIONS TO COVER (search each separately):
1. Scotland / Edinburgh specifically
2. London / England / general UK
3. Europe-wide (EU-funded programmes, ELSA, European law competitions)
4. Azerbaijan / Baku

SEARCH STRATEGY:
- Use varied search queries covering different angles
- Include terms like "2026", "applications open", "deadline", "register"
- Search for both general listings and specific firm/org events
- Check for Law Society of Scotland events, Edinburgh Law School events
- Look at ELSA, Lawscot, The Lawyer, Legal Cheek, Prospects, TargetJobs

After searching, respond with ONLY a JSON array. No other text. Each item:
{{
  "name": "Event or opportunity name",
  "category": "Legal",
  "type": "Internship|Workshop|Event|Scheme|Talk|Competition|Scholarship|Conference|Open Day",
  "region": "Scotland|UK|Europe|Azerbaijan|Remote|Global",
  "deadline": "YYYY-MM-DD or null if unknown",
  "event_date": "YYYY-MM-DD or null if unknown",
  "link": "https://...",
  "description": "1-2 sentence summary of what it is and why it's relevant",
  "source": "Where you found it (e.g. Legal Cheek, Law Society of Scotland)"
}}

Return between 5-20 opportunities. Prioritise ones with upcoming deadlines.
If you find fewer than 5 genuinely relevant results, return what you have — never fabricate."""

LEGAL_USER = """Search the web now for current legal opportunities, events, workshops, internships, 
insight days, vacation schemes, competitions, and scholarships relevant to a law student in 
Scotland/UK/Europe/Azerbaijan. Today's date is {today}. Focus on opportunities with deadlines 
or event dates in the next 3 months. Return ONLY a JSON array."""


AI_SYSTEM = f"""You are an opportunity scout specialising in AI, TECH, and STARTUP events.

{PROFILE_CONTEXT}

YOUR SEARCH MANDATE — search the web thoroughly for CURRENT and UPCOMING:
• AI/ML workshops, bootcamps, and training events
• Startup weekends, hackathons, pitch competitions
• AI conferences and meetups (especially affordable/student-friendly ones)
• Tech accelerator programmes and incubator applications
• AI ethics and governance events (intersection of AI and law)
• Legal tech specific events and competitions
• Entrepreneurship workshops and founder meetups
• Teens in AI, AI for Good, and similar youth/student AI programmes

REGIONS TO COVER:
1. Scotland / Edinburgh
2. London / UK
3. Europe (especially online/hybrid events)
4. Azerbaijan / Baku
5. Remote/online events (global)

SEARCH STRATEGY:
- Search for "AI workshop", "startup event", "hackathon", "tech meetup"
- Include "2026", "register", "apply", "free", "student"
- Look at Meetup.com, Luma, Eventbrite, Devpost, MLH
- Search for Edinburgh tech scene, Scottish tech events
- Look for legal-tech crossover events

After searching, respond with ONLY a JSON array. Each item:
{{
  "name": "Event or opportunity name",
  "category": "AI",
  "type": "Workshop|Hackathon|Conference|Meetup|Accelerator|Competition|Talk|Bootcamp",
  "region": "Scotland|UK|Europe|Azerbaijan|Remote|Global",
  "deadline": "YYYY-MM-DD or null",
  "event_date": "YYYY-MM-DD or null",
  "link": "https://...",
  "description": "1-2 sentence summary",
  "source": "Where found"
}}

Return 5-20 opportunities. Never fabricate."""

AI_USER = """Search the web now for current AI, tech, startup, and legal-tech events, workshops, 
hackathons, competitions, and accelerator programmes. Today's date is {today}. Focus on 
opportunities happening or with deadlines in the next 3 months. Return ONLY a JSON array."""


SALES_SYSTEM = f"""You are an opportunity scout specialising in SALES career events and opportunities.

{PROFILE_CONTEXT}

YOUR SEARCH MANDATE — search the web thoroughly for CURRENT and UPCOMING:
• Sales training workshops and bootcamps
• SDR, BDR, and closer skills events
• Sales conferences and networking events
• Commission-based closer opportunities (high-ticket, remote-friendly)
• Business development workshops
• Content creation and personal branding events for salespeople
• Sales tech / SaaS events
• Entrepreneurship and revenue-focused workshops

REGIONS TO COVER:
1. UK (especially remote-friendly roles)
2. Europe
3. Remote / online (global)

SEARCH STRATEGY:
- Search for "sales workshop", "closer training", "SDR event", "sales conference"
- Include "2026", "register", "free"
- Look at Eventbrite, Meetup, LinkedIn events
- Search for "remote closer opportunity", "high-ticket sales"
- Look for sales communities and masterminds
- Search Reddit r/sales, sales communities

After searching, respond with ONLY a JSON array. Each item:
{{
  "name": "Event or opportunity name",
  "category": "Sales",
  "type": "Workshop|Conference|Opportunity|Training|Meetup|Mastermind|Webinar",
  "region": "UK|Europe|Remote|Global",
  "deadline": "YYYY-MM-DD or null",
  "event_date": "YYYY-MM-DD or null",
  "link": "https://...",
  "description": "1-2 sentence summary",
  "source": "Where found"
}}

Return 5-20 opportunities. Never fabricate."""

SALES_USER = """Search the web now for current sales training events, workshops, conferences, 
closer opportunities, and business development events. Today's date is {today}. Focus on 
opportunities happening or with deadlines in the next 3 months. Return ONLY a JSON array."""


PM_SYSTEM = f"""You are an opportunity scout specialising in PROJECT MANAGER roles and programmes 
that welcome candidates from NON-TECHNICAL backgrounds (law, humanities, social sciences, business).

{PROFILE_CONTEXT}

YOUR SEARCH MANDATE — search the web thoroughly for CURRENT and UPCOMING:
• Junior / associate / graduate project manager roles (especially those that say "no technical 
  background required" or welcome arts, law, humanities graduates)
• Project management internships and graduate schemes
• APM (Association for Project Management) student events, qualifications, and bursaries
• PRINCE2, Agile, or Scrum certification scholarships and free training
• PM bootcamps and workshops aimed at career-switchers or non-engineers
• Operations / programme coordinator roles at law firms, consultancies, or NGOs
• Project management roles at legal-tech or AI startups (where domain knowledge matters 
  more than engineering)
• Civil service / public sector PM schemes (Fast Stream, Scottish Government, EU institutions)
• Remote-friendly PM roles at early-stage startups

IMPORTANT FILTER — the person does NOT have a computer science or engineering degree.
Exclude roles that require: software engineering experience, CS degree, 3+ years in technical PM.
Include roles that value: stakeholder management, communication, organisation, legal/regulatory 
knowledge, bilingual skills, client-facing experience, or startup operations.

REGIONS TO COVER:
1. Scotland / Edinburgh
2. London / UK
3. Europe (especially remote-friendly or EU institution roles)
4. Azerbaijan / Baku
5. Remote / global

SEARCH STRATEGY:
- Search for "graduate project manager non-technical", "junior PM humanities"
- Search for "project management internship UK 2026", "APM student"
- Search for "operations coordinator law firm", "programme manager NGO"
- Search for "project manager legal tech startup"
- Search for "civil service project delivery scheme", "Fast Stream"
- Look at LinkedIn, Indeed, Prospects, TargetJobs, Civil Service Jobs, WorkInStartups
- Search for PM training events: "project management workshop free", "PRINCE2 scholarship"

After searching, respond with ONLY a JSON array. Each item:
{{
  "name": "Role or opportunity name",
  "category": "PM",
  "type": "Role|Internship|Graduate Scheme|Workshop|Certification|Scholarship|Event",
  "region": "Scotland|UK|Europe|Azerbaijan|Remote|Global",
  "deadline": "YYYY-MM-DD or null",
  "event_date": "YYYY-MM-DD or null",
  "link": "https://...",
  "description": "1-2 sentence summary — mention if non-technical backgrounds are explicitly welcomed",
  "source": "Where found"
}}

Return 5-20 opportunities. Never fabricate."""

PM_USER = """Search the web now for current project manager roles, graduate schemes, internships, 
training, and certifications that are open to people from non-technical backgrounds (law, 
humanities, business). Today's date is {today}. Focus on opportunities with deadlines or start 
dates in the next 3 months. Return ONLY a JSON array."""


# ---------------------------------------------------------------------------
# Agent runner
# ---------------------------------------------------------------------------

def run_agent(name: str, system: str, user_template: str) -> list[dict]:
    """Call Claude with web search enabled, return parsed opportunity list."""
    today = date.today().isoformat()
    user_msg = user_template.format(today=today)

    print(f"\n{'='*60}")
    print(f"  Running {name} agent...")
    print(f"{'='*60}")

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=8192,
            system=system,
            tools=[{
                "type": "web_search_20260318",
                "name": "web_search",
                "max_uses": MAX_SEARCHES_PER_AGENT,
            }],
            messages=[{"role": "user", "content": user_msg}],
        )
    except Exception as e:
        print(f"  ERROR calling API for {name}: {e}")
        return []

    # Extract text content from response blocks
    text_parts = []
    for block in response.content:
        if hasattr(block, "text"):
            text_parts.append(block.text)

    full_text = "\n".join(text_parts)

    # Parse JSON array from the response
    opportunities = extract_json_array(full_text)
    print(f"  {name} found {len(opportunities)} opportunities")

    # Tag each with category if missing
    for opp in opportunities:
        opp.setdefault("category", name)

    return opportunities


def extract_json_array(text: str) -> list[dict]:
    """Robustly extract a JSON array from text that may contain other content."""
    # Try the whole text first
    text = text.strip()
    if text.startswith("["):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

    # Find the outermost [ ... ]
    start = text.find("[")
    if start == -1:
        return []

    # Find matching closing bracket
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "[":
            depth += 1
        elif text[i] == "]":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i + 1])
                except json.JSONDecodeError:
                    return []
    return []


# ---------------------------------------------------------------------------
# Orchestrator — deduplicate, validate, rank
# ---------------------------------------------------------------------------

def orchestrate(all_opportunities: list[dict], seen_hashes: set) -> list[dict]:
    """Dedupe against memory, validate fields, sort by deadline urgency."""

    new_opps = []
    seen_urls = set()

    for opp in all_opportunities:
        link = opp.get("link", "")
        if not link or not link.startswith("http"):
            continue

        h = url_hash(link)

        # Skip if already seen in previous runs
        if h in seen_hashes:
            continue

        # Skip if duplicate within this run
        if link in seen_urls:
            continue

        seen_urls.add(link)

        # Normalise fields
        opp["name"] = opp.get("name", "Untitled")[:200]
        opp["description"] = opp.get("description", "")[:500]
        opp["category"] = opp.get("category", "Other")
        opp["type"] = opp.get("type", "Event")
        opp["region"] = opp.get("region", "Unknown")
        opp["source"] = opp.get("source", "Web search")
        opp["found_date"] = date.today().isoformat()
        opp["_hash"] = h

        # Parse dates safely
        for date_field in ["deadline", "event_date"]:
            val = opp.get(date_field)
            if val and val != "null":
                try:
                    datetime.strptime(val, "%Y-%m-%d")
                except (ValueError, TypeError):
                    opp[date_field] = None
            else:
                opp[date_field] = None

        new_opps.append(opp)

    # Sort: items with deadlines first (soonest first), then by event_date, then the rest
    def sort_key(o):
        dl = o.get("deadline") or "9999-12-31"
        ed = o.get("event_date") or "9999-12-31"
        return (dl, ed)

    new_opps.sort(key=sort_key)

    print(f"\n  Orchestrator: {len(all_opportunities)} total → {len(new_opps)} new unique opportunities")
    return new_opps


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def main():
    print(f"\n{'#'*60}")
    print(f"  OPPORTUNITY SCANNER — {date.today().isoformat()}")
    print(f"  Model: {MODEL}")
    print(f"  Max searches per agent: {MAX_SEARCHES_PER_AGENT}")
    print(f"{'#'*60}")

    # Load memory
    seen_hashes = load_seen()
    print(f"  Memory: {len(seen_hashes)} previously seen opportunities")

    # Run all four agents
    legal_opps = run_agent("Legal", LEGAL_SYSTEM, LEGAL_USER)
    ai_opps = run_agent("AI", AI_SYSTEM, AI_USER)
    sales_opps = run_agent("Sales", SALES_SYSTEM, SALES_USER)
    pm_opps = run_agent("PM", PM_SYSTEM, PM_USER)

    # Combine and orchestrate
    all_opps = legal_opps + ai_opps + sales_opps + pm_opps
    new_opps = orchestrate(all_opps, seen_hashes)

    if not new_opps:
        print("\n  No new opportunities found this run.")
        return

    # Update memory
    new_hashes = {opp["_hash"] for opp in new_opps}
    seen_hashes.update(new_hashes)
    save_seen(seen_hashes)

    # Push to Notion
    notion_token = os.environ.get("NOTION_TOKEN")
    notion_db = os.environ.get("NOTION_DATABASE_ID")

    if notion_token and notion_db:
        from notion_sync import push_to_notion
        push_to_notion(new_opps, notion_token, notion_db)
    else:
        print("\n  NOTION_TOKEN or NOTION_DATABASE_ID not set — printing results instead:\n")
        for i, opp in enumerate(new_opps, 1):
            print(f"  {i}. [{opp['category']}] {opp['name']}")
            print(f"     Type: {opp['type']} | Region: {opp['region']}")
            if opp.get("deadline"):
                print(f"     Deadline: {opp['deadline']}")
            if opp.get("event_date"):
                print(f"     Event date: {opp['event_date']}")
            print(f"     {opp['link']}")
            print(f"     {opp['description'][:120]}")
            print()

    print(f"\n{'#'*60}")
    print(f"  DONE — {len(new_opps)} new opportunities processed")
    print(f"{'#'*60}\n")


if __name__ == "__main__":
    main()
