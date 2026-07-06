"""
Notion sync — pushes opportunity records to a Notion database.

Expected database properties (create these in Notion first):
  - Name         (title)
  - Category     (select: Legal, AI, Sales)
  - Type         (select: Internship, Workshop, Event, Scheme, Talk, etc.)
  - Region       (select: Scotland, UK, Europe, Azerbaijan, Remote, Global)
  - Deadline     (date)
  - Event date   (date)
  - Link         (url)
  - Description  (rich_text)
  - Source        (rich_text)
  - Found        (date)
  - Status       (select: New, Interested, Applied, Passed)
"""

import requests
import time


NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


def push_to_notion(opportunities: list[dict], token: str, database_id: str):
    """Create a Notion page for each opportunity."""

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Notion-Version": NOTION_VERSION,
    }

    success = 0
    failed = 0

    for opp in opportunities:
        properties = {
            "Name": {
                "title": [{"text": {"content": opp["name"][:200]}}]
            },
            "Category": {
                "select": {"name": opp.get("category", "Other")}
            },
            "Type": {
                "select": {"name": opp.get("type", "Event")}
            },
            "Region": {
                "select": {"name": opp.get("region", "Unknown")}
            },
            "Link": {
                "url": opp.get("link")
            },
            "Description": {
                "rich_text": [{"text": {"content": opp.get("description", "")[:2000]}}]
            },
            "Source": {
                "rich_text": [{"text": {"content": opp.get("source", "Web search")[:200]}}]
            },
            "Status": {
                "select": {"name": "New"}
            },
        }

        # Add date fields only if they exist
        if opp.get("deadline"):
            properties["Deadline"] = {"date": {"start": opp["deadline"]}}

        if opp.get("event_date"):
            properties["Event date"] = {"date": {"start": opp["event_date"]}}

        if opp.get("found_date"):
            properties["Found"] = {"date": {"start": opp["found_date"]}}

        payload = {
            "parent": {"database_id": database_id},
            "properties": properties,
        }

        try:
            resp = requests.post(
                f"{NOTION_API}/pages",
                headers=headers,
                json=payload,
                timeout=30,
            )

            if resp.status_code == 200:
                success += 1
                print(f"  ✓ Added: {opp['name'][:60]}")
            elif resp.status_code == 429:
                # Rate limited — wait and retry once
                retry_after = int(resp.headers.get("Retry-After", 2))
                print(f"  ⏳ Rate limited, waiting {retry_after}s...")
                time.sleep(retry_after)
                resp = requests.post(
                    f"{NOTION_API}/pages",
                    headers=headers,
                    json=payload,
                    timeout=30,
                )
                if resp.status_code == 200:
                    success += 1
                    print(f"  ✓ Added (retry): {opp['name'][:60]}")
                else:
                    failed += 1
                    print(f"  ✗ Failed (retry): {opp['name'][:60]} — {resp.status_code}")
            else:
                failed += 1
                error_msg = resp.json().get("message", resp.text[:100])
                print(f"  ✗ Failed: {opp['name'][:60]} — {resp.status_code}: {error_msg}")

        except Exception as e:
            failed += 1
            print(f"  ✗ Error: {opp['name'][:60]} — {e}")

        # Small delay to avoid hammering Notion API
        time.sleep(0.4)

    print(f"\n  Notion sync: {success} added, {failed} failed")
