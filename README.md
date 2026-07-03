# Job Email Assistant

Hourly assistant that scans your Gmail for recruitment/job-related emails, summarizes and classifies each one, drafts a suggested reply (as a Gmail draft — **never sent automatically**), and logs everything to your Notion CRM Database. Runs on GitHub Actions; no server to maintain.

## One-time setup

### 1. Google Cloud (Gmail API)

1. Create a project at console.cloud.google.com and enable the **Gmail API**.
2. Configure the OAuth consent screen:
   - User type: **External**
   - Scopes: `gmail.readonly` and `gmail.compose` only
   - Add yourself as a test user
   - **Publishing status: "In Production"** (stay unverified — do not leave it on "Testing"). Testing-mode refresh tokens expire every 7 days under Google's unverified-app policy, which would silently break the hourly job. "In Production" while unverified removes that expiry and is standard for a personal single-user script. You'll see one extra "unverified app" click-through during the one-time consent flow below — that's expected.
3. Create an OAuth client ID of type **Desktop app**, download the JSON.
4. Run the local bootstrap script to get a refresh token:
   ```
   pip install -r requirements.txt
   python scripts/local_oauth_bootstrap.py --client-id <id> --client-secret <secret>
   ```
   This opens a browser, asks you to consent, and prints a `refresh_token`.

### 2. Anthropic

Create an API key at console.anthropic.com.

### 3. Notion

1. Create an internal integration at notion.so/my-integrations with Read/Update/Insert content capabilities.
2. Open your "CRM Database" page in Notion → `...` menu → **Connections** → add the integration. Without this step every API call 404s.
3. Add the new properties listed in the plan (`Role / Job Title`, `Recruiter Name`, `Recruiter Email`, `Date Received`, `Date Replied`, `Stage`, `Email Summary`, `Suggested Reply`, `Follow-up Date`, `Interview Date`, `Gmail Thread Link`, `Gmail Thread ID`), plus 5 new options on the existing `Status` select: `Interview Invitation`, `Rejection`, `Next Step`, `Assessment`, `Request for Information`.

### 4. GitHub repository secrets & variables

Repo Settings → Secrets and variables → Actions.

**Secrets:** `ANTHROPIC_API_KEY`, `NOTION_TOKEN`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REFRESH_TOKEN`

**Variables:** `CLAUDE_MODEL` (default `claude-sonnet-5`), `NOTION_DATA_SOURCE_ID`, `MAX_EMAILS_PER_RUN` (default `20`)

## How it runs

`.github/workflows/hourly_job_emails.yml` runs every hour (`workflow_dispatch` also available for manual testing from the Actions tab). Each run:

1. Searches Gmail for job/recruiter-looking emails from the last 2 days.
2. For each thread, checks Notion for an existing row matching its Gmail thread ID whose stored `Last Processed Message ID` already matches the thread's latest message — if so, skips it (no LLM calls at all). This is the dedup mechanism: it's done via Notion rather than a Gmail label, since managing Gmail labels needs a broader OAuth scope (`gmail.labels`/`gmail.modify`) than this project requests.
3. Runs a cheap relevance check to drop keyword false positives.
4. Summarizes, classifies, and drafts a reply for each relevant thread.
5. Creates a Gmail **draft** on the thread (never sends).
6. Creates/updates the matching row in your Notion CRM Database, including the new `Last Processed Message ID`, so a failed run retries cleanly next hour and a successful one won't be redone.

You always review and send replies yourself from Gmail.

## Local testing

```
cp .env.example .env   # fill in real values
pip install -r requirements.txt
python -m src.job_assistant.main
```

Set `MAX_EMAILS_PER_RUN=2` in `.env` for a small first test run.

---

# Story Scout AI

Daily assistant that scans trusted marketing, AI, branding, creator-economy, advertising, PR, social-media, and consumer-behavior RSS feeds, dedupes them, filters for relevance to a marketing LinkedIn audience, and logs each story to its own Notion database with a summary, the key lesson(s), and three LinkedIn post ideas. Sends you a digest email when it's done. Runs on GitHub Actions every morning; no server to maintain.

This is **Phase 1** (collect stories → Notion). Later phases — ranking stories by interest, multiple post angles, drafted posts, non-RSS sources like Instagram/TikTok/Reddit — build on the same pipeline without changing this phase's code; see `src/story_scout/sources/base.py`'s `Source` protocol for the extension point new discovery sources plug into.

## One-time setup

### 1. Notion

1. Reuse the same internal integration created for the Job Email Assistant (or create one at notion.so/my-integrations with Read/Update/Insert content capabilities).
2. Create a new **Story Scout** database — separate from the job-search CRM — with these properties:
   - `Name` (title)
   - `URL` (url)
   - `Source` (text)
   - `Category` (select) — add options matching `src/story_scout/sources/feeds.py`: Marketing, AI, Branding, Creator Economy, Advertising, PR, Social Media, Consumer Behavior
   - `Published Date` (date)
   - `Date Added` (date)
   - `Summary` (text)
   - `Key Lessons` (text)
   - `LinkedIn Post Ideas` (text) — 3 numbered ideas in one field
3. Open the database → `...` menu → **Connections** → add the integration.
4. Copy the database's own page UUID from its Notion URL for `NOTION_STORY_DATABASE_ID` below (not a data source UUID — see the caveat comment next to `NOTION_DATA_SOURCE_ID` in `.env.example`, same gotcha applies here).

### 2. Anthropic

Reuses the same `ANTHROPIC_API_KEY` as the Job Email Assistant.

### 3. Gmail (for the digest notification)

Reuses the same Google OAuth credentials (`GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET`/`GOOGLE_REFRESH_TOKEN`) already set up for the Job Email Assistant — no new consent flow needed, since the `gmail.compose` scope it already requests permits sending. Set `STORY_SCOUT_NOTIFY_EMAIL` to whatever address should receive the daily digest (typically your own).

### 4. GitHub repository secrets & variables

Repo Settings → Secrets and variables → Actions.

**Secrets:** `ANTHROPIC_API_KEY`, `NOTION_TOKEN`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REFRESH_TOKEN` (all already set if you've set up the Job Email Assistant)

**Variables:** `CLAUDE_MODEL` (already set), plus new **`NOTION_STORY_DATABASE_ID`** and **`STORY_SCOUT_NOTIFY_EMAIL`**

## How it runs

`.github/workflows/story_scout.yml` runs daily at 07:00 UTC (`workflow_dispatch` also available for manual testing from the Actions tab — edit the cron line if 07:00 UTC isn't "morning" for you). Each run:

1. Fetches recent entries from the trusted RSS feeds listed in `src/story_scout/sources/feeds.py` — edit that file to add/remove sources, no other code changes needed.
2. Removes duplicates: exact URL matches and near-duplicate titles across outlets covering the same story.
3. Skips any story whose URL is already logged in the Notion database, so a story still circulating doesn't get re-added the next day.
4. Asks Claude to filter the remaining candidates down to what's genuinely relevant and interesting for a marketing LinkedIn audience.
5. For each relevant story, asks Claude for a summary, the key lesson(s), and three LinkedIn post ideas, then creates the Notion page.
6. Emails `STORY_SCOUT_NOTIFY_EMAIL` a digest of everything added this run (skipped if nothing new was added). A failed email never blocks the Notion writes — they're already saved by the time it sends.

Note: this notification step does call a send-capable Gmail API method, unlike the Job Email Assistant's `common/gmail_client.py`, which deliberately never does (see that file's docstring). The distinction: this always emails *you*, never a third party, so it's a different, much lower-risk action than auto-sending a reply on your behalf. That send-capable code is confined to `src/story_scout/notifier.py`.

## Local testing

```
cp .env.example .env   # fill in real values, including NOTION_STORY_DATABASE_ID
pip install -r requirements.txt
python -m src.story_scout.main
```

## Adding a story by hand (Instagram, TikTok, anything without an RSS feed)

Instagram and TikTok don't offer public content discovery the way RSS does for news sites -- their APIs are built for managing your own account, not searching what other creators post, and scraping around that would mean fighting their bot detection and their Terms of Service. So there's no automated source for them.

Instead, when you spot something worth including yourself, feed it in directly:

```
python -m src.story_scout.manual_entry \
  --url "https://www.instagram.com/p/abc123/" \
  --title "Silence, brand: the shift from funny to fatigued" \
  --source "Instagram (@girlsinmarketing)" \
  --category "Social Media" \
  --text "Paste the caption, transcript, or a description of the post here."
```

This skips the relevance filter (you already decided it's worth including) and runs the same summary / key-lessons / LinkedIn-ideas generation as the daily pipeline, saving straight into the same Notion database. It also skips anything whose URL is already logged, so re-running is safe.

---

## Tests

```
pytest
```
