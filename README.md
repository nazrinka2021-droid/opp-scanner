# Opportunity Scanner

An automated multi-agent pipeline that scans the web daily for legal, AI/tech, and sales opportunities — and pushes them to a Notion database.

## What it does

Three specialist agents search the web in parallel:

| Agent | What it finds | Where it looks |
|-------|--------------|----------------|
| **Legal** | Internships, vacation schemes, insight days, workshops, competitions, scholarships | Scotland, UK, Europe, Azerbaijan |
| **AI/Tech** | Hackathons, startup events, AI workshops, accelerators, legal-tech events | Scotland, UK, Europe, Azerbaijan, Remote |
| **Sales** | Sales training, closer opportunities, conferences, masterminds | UK, Europe, Remote |
| **PM** | Project manager roles, grad schemes, certifications for non-technical backgrounds | Scotland, UK, Europe, Azerbaijan, Remote |

An **orchestrator** then deduplicates results against a memory file (so you never see the same thing twice), validates and ranks by deadline urgency, and pushes new finds to your Notion database.

## Cost estimate

Running daily with `claude-haiku-4-5`:

| Component | Monthly cost |
|-----------|-------------|
| Claude API tokens | ~$1.50–2.50 |
| Web searches (~32/day × 30) | ~$9.60 |
| GitHub Actions | Free (public repo) |
| **Total** | **~$11–12/month** |

Switch to `claude-sonnet-4-6` for better results at ~$15–18/month.

---

## Setup guide (step by step)

### Step 1: Get an Anthropic API key

1. Go to [console.anthropic.com](https://console.anthropic.com/)
2. Sign up or log in
3. Go to **API Keys** in the left sidebar
4. Click **Create Key**, name it "opportunity-scanner"
5. Copy the key (starts with `sk-ant-...`) — you'll need it in Step 4
6. Add at least $10 in credits under **Billing** (this will last ~1 month)

### Step 2: Create the Notion database

1. Go to [notion.so](https://notion.so) and open a workspace
2. Create a new **Full page database** (type `/database` and select "Database - Full page")
3. Name it "Opportunity Scanner" (or whatever you like)
4. Set up these columns (click `+` to add each property):

   | Property name | Type | Options to create |
   |--------------|------|-------------------|
   | Name | Title | *(already exists)* |
   | Category | Select | Legal, AI, Sales, PM |
   | Type | Select | Internship, Workshop, Event, Scheme, Talk, Hackathon, Competition, Scholarship, Conference, Open Day, Meetup, Accelerator, Bootcamp, Training, Opportunity, Mastermind, Webinar, Role, Graduate Scheme, Certification |
   | Region | Select | Scotland, UK, Europe, Azerbaijan, Remote, Global |
   | Deadline | Date | — |
   | Event date | Date | — |
   | Link | URL | — |
   | Description | Text | — |
   | Source | Text | — |
   | Found | Date | — |
   | Status | Select | New, Interested, Applied, Passed |

5. **Create a Notion integration:**
   - Go to [notion.so/my-integrations](https://www.notion.so/my-integrations)
   - Click **New integration**
   - Name: "Opportunity Scanner"
   - Select your workspace
   - Capabilities: check **Read content**, **Insert content**, **Update content**
   - Click **Submit** → copy the **Internal Integration Secret** (starts with `ntn_...`)

6. **Share the database with your integration:**
   - Go back to your database page in Notion
   - Click the `···` menu (top right) → **Connections** → find "Opportunity Scanner" → **Confirm**

7. **Get the database ID:**
   - Open the database in your browser
   - The URL looks like: `https://notion.so/YOUR-WORKSPACE/abc123def456...?v=...`
   - The database ID is the 32-character hex string **before** the `?v=` — copy it
   - Format it with hyphens: `abc123de-f456-7890-abcd-ef1234567890` (8-4-4-4-12 pattern)

### Step 3: Create the GitHub repository

1. Go to [github.com](https://github.com) — sign up if you don't have an account
2. Click the green **New** button (or go to [github.com/new](https://github.com/new))
3. Settings:
   - Repository name: `opportunity-scanner`
   - Visibility: **Public** (free unlimited Actions minutes)
   - Check **Add a README** (we'll replace it)
   - Click **Create repository**

4. **Upload the project files:**
   - On your new repo page, click **Add file** → **Upload files**
   - Drag and drop ALL the files from this project:
     - `scanner.py`
     - `notion_sync.py`
     - `requirements.txt`
     - `README.md`
     - `data/seen.json`
     - `.github/workflows/scan.yml`
   - **Important:** For the `.github` folder, you may need to use the command line (see below)

   **Easier method using command line (recommended):**
   ```bash
   # Install git if you don't have it: https://git-scm.com/downloads
   
   # Clone your empty repo
   git clone https://github.com/YOUR-USERNAME/opportunity-scanner.git
   cd opportunity-scanner
   
   # Copy all the project files into this folder
   # (overwrite the default README)
   
   # Push everything
   git add .
   git commit -m "Initial setup"
   git push
   ```

### Step 4: Add your secrets to GitHub

1. In your repo, go to **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret** and add these three:

   | Secret name | Value |
   |------------|-------|
   | `ANTHROPIC_API_KEY` | Your `sk-ant-...` key from Step 1 |
   | `NOTION_TOKEN` | Your `ntn_...` token from Step 2 |
   | `NOTION_DATABASE_ID` | The 32-character ID from Step 2 |

### Step 5: Enable GitHub Actions

1. Go to the **Actions** tab in your repo
2. You should see the "Opportunity Scanner" workflow
3. Click **Enable** if prompted
4. To test it immediately: click **Run workflow** → **Run workflow** (green button)
5. Watch the run — click on it to see live logs

### Step 6: Verify it works

1. After the action completes (2–5 minutes), check your Notion database
2. You should see new entries with Status = "New"
3. Set up a Notion **Board view** grouped by Status for a kanban workflow

---

## Customising

### Change scan frequency

Edit `.github/workflows/scan.yml`:

```yaml
# Twice daily (8am and 6pm UTC):
schedule:
  - cron: "0 8,18 * * *"

# Every Monday and Thursday:
schedule:
  - cron: "0 8 * * 1,4"

# Once a week (Sunday 9am UTC):
schedule:
  - cron: "0 9 * * 0"
```

### Use a smarter model

Change `SCANNER_MODEL` in the workflow file:
- `claude-haiku-4-5-20251001` — cheapest, good enough for scanning (~$8/month)
- `claude-sonnet-4-6` — better at finding niche opportunities (~$15/month)

### Add more search coverage

Edit the agent system prompts in `scanner.py` to:
- Add specific firms or organisations to check
- Add new regions
- Narrow the types of opportunities
- Add new search terms

### Add a fourth agent

Copy the pattern in `scanner.py` — create a new `SYSTEM` + `USER` prompt pair, call `run_agent()` with it in `main()`, and add the results to `all_opps`.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Action fails with "API key" error | Check ANTHROPIC_API_KEY is set correctly in GitHub Secrets |
| Notion entries missing | Check NOTION_TOKEN and NOTION_DATABASE_ID; ensure database is shared with integration |
| "Property does not exist" error | Column names in Notion must match exactly: "Name", "Category", "Type", "Region", "Deadline", "Event date", "Link", "Description", "Source", "Found", "Status" |
| No new results | The memory file filters out previously seen URLs — check `data/seen.json` |
| Want to reset memory | Replace contents of `data/seen.json` with `{"hashes": [], "last_run": null}` |
