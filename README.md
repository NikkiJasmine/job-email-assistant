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

Every ~3 days, scans RSS feeds (marketing/AI/branding trade press, brand newsrooms), Reddit, and YouTube for marketing stories, scores every candidate 1-10 on originality/marketing value/discussion level/LinkedIn potential, and keeps only the top 5. For each, Claude writes a brand, topic, summary, why-it-matters note, a public-reaction summary (grounded in real comments when available), a marketing lesson, and 3 LinkedIn post angles (discussion ideas, not full posts) -- all saved to a Notion database. Emails you a narrative digest: the #1 story called out first with why it was chosen, the rest in ranked order, and a closing "Patterns I'm noticing" section connecting the 5 stories. Runs on GitHub Actions; no server to maintain.

Quality over quantity is the design point: most candidate stories should score low and get dropped. Generic product launches, earnings, stock market news, and celebrity gossip unrelated to marketing are explicitly scored near zero (see the rubric in `src/story_scout/llm.py`).

**On sources**: Instagram, TikTok, and LinkedIn have no legitimate public content-discovery API -- their APIs manage your own account, not searching what other creators post, and scraping around that means fighting active bot detection and breaching their Terms of Service. So they are not automated sources here. See "Adding a story by hand" below for feeding in something you found on those platforms yourself. RSS, Reddit, and YouTube all have real public/official APIs and are fully automated.

## One-time setup

### 1. Notion

1. Reuse the same internal integration created for the Job Email Assistant (or create one at notion.so/my-integrations with Read/Update/Insert content capabilities).
2. Create a new **Story Scout** database — separate from the job-search CRM — with these properties:
   - `Name` (title)
   - `Brand` (text)
   - `Platform` (select) — options: RSS, Reddit, YouTube, Instagram, TikTok, LinkedIn (add more as you use manual entry for other platforms)
   - `Topic` (select) — options matching `TOPICS` in `src/story_scout/llm.py`: Marketing Campaigns, Creative Advertising, Influencer Marketing, AI in Marketing, Rebrands, Viral Campaigns, Community Management, Brand Strategy, Retail Marketing, Beauty Marketing, Fashion Marketing, Luxury Marketing, PR Wins, PR Failures, Brand Collaborations, Outdoor Advertising, Social Media Strategy
   - `URL` (url)
   - `Source` (text)
   - `Published Date` (date)
   - `Date Added` (date)
   - `Score` (number)
   - `Summary` (text)
   - `Why It Matters` (text)
   - `Public Reaction` (text)
   - `Marketing Lesson` (text)
   - `LinkedIn Post Angles` (text) — 3 numbered ideas in one field
3. Open the database → `...` menu → **Connections** → add the integration.
4. Copy the database's own page UUID from its Notion URL for `NOTION_STORY_DATABASE_ID` below (not a data source UUID — see the caveat comment next to `NOTION_DATA_SOURCE_ID` in `.env.example`, same gotcha applies here).

### 2. Anthropic

Reuses the same `ANTHROPIC_API_KEY` as the Job Email Assistant.

### 3. Gmail (for the digest notification)

Reuses the same Google OAuth credentials (`GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET`/`GOOGLE_REFRESH_TOKEN`) already set up for the Job Email Assistant — no new consent flow needed, since the `gmail.compose` scope it already requests permits sending. Set `STORY_SCOUT_NOTIFY_EMAIL` to whatever address should receive the digest, and `STORY_SCOUT_RECIPIENT_NAME` to how the report should address you (defaults to "you").

### 4. Reddit (optional)

1. Create a free "script" app at reddit.com/prefs/apps.
2. Set `REDDIT_CLIENT_ID` and `REDDIT_CLIENT_SECRET`. If unset, Reddit is skipped (not a hard failure) and the pipeline runs on the other sources alone.
3. Edit `TRUSTED_SUBREDDITS` in `src/story_scout/sources/reddit.py` to change which subreddits it checks.

### 5. YouTube (optional)

1. In console.cloud.google.com, enable the **YouTube Data API v3** and create an API key.
2. Set `YOUTUBE_API_KEY`. If unset, YouTube is skipped (not a hard failure).
3. Edit `SEARCH_QUERIES` in `src/story_scout/sources/youtube.py` to change what it searches for.

### 6. GitHub repository secrets & variables

Repo Settings → Secrets and variables → Actions.

**Secrets:** `ANTHROPIC_API_KEY`, `NOTION_TOKEN`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REFRESH_TOKEN` (all already set if you've set up the Job Email Assistant), plus optional `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `YOUTUBE_API_KEY`

**Variables:** `CLAUDE_MODEL` (already set), plus new **`NOTION_STORY_DATABASE_ID`**, **`STORY_SCOUT_NOTIFY_EMAIL`**, and optionally `STORY_SCOUT_RECIPIENT_NAME` / `STORY_SCOUT_TOP_N` (default 5)

## How it runs

`.github/workflows/story_scout.yml` runs on an approximate every-3-days cron (`workflow_dispatch` also available for manual testing from the Actions tab). Each run:

1. Fetches recent candidates from every enabled source (RSS always; Reddit/YouTube if configured).
2. Removes duplicates: exact URL matches and near-duplicate titles across outlets covering the same story.
3. Skips any story whose URL is already logged in the Notion database, so a story still circulating doesn't get re-added next time.
4. Asks Claude to score every remaining candidate 1-10 (originality, marketing value, discussion level, LinkedIn potential), using real upvote/comment/view counts where available.
5. Keeps only the top `STORY_SCOUT_TOP_N` (default 5) by score.
6. For each, fetches real top comments (Reddit/YouTube only -- RSS has none) and asks Claude to generate the brand, topic, summary, why-it-matters note, public-reaction summary, marketing lesson, and 3 LinkedIn post angles, then creates the Notion page. Public reaction is only ever built from real comment text; if none was available, it says so rather than inventing one.
7. Asks Claude to find cross-story patterns across the top 5 (e.g. "three luxury brands leaned on nostalgia this week").
8. Emails `STORY_SCOUT_NOTIFY_EMAIL` the narrative report (skipped if nothing made the cut). A failed email never blocks the Notion writes — they're already saved by the time it sends.

Note: the notification step does call a send-capable Gmail API method, unlike the Job Email Assistant's `common/gmail_client.py`, which deliberately never does (see that file's docstring). The distinction: this always emails *you*, never a third party, so it's a different, much lower-risk action than auto-sending a reply on your behalf. That send-capable code is confined to `src/story_scout/notifier.py`.

## Local testing

```
cp .env.example .env   # fill in real values, including NOTION_STORY_DATABASE_ID
pip install -r requirements.txt
python -m src.story_scout.main
```

## Adding a story by hand (Instagram, TikTok, LinkedIn, anything without an API)

Instead, when you spot something worth including yourself, feed it in directly:

```
python -m src.story_scout.manual_entry \
  --url "https://www.instagram.com/p/abc123/" \
  --title "Silence, brand: the shift from funny to fatigued" \
  --source "Instagram (@girlsinmarketing)" \
  --platform "Instagram" \
  --text "Paste the caption, transcript, or a description of the post here." \
  --comments "Optional: paste real comment text here if you have it."
```

This skips the scoring step (you already decided it's worth including) and runs the same brand/topic/summary/reaction/lesson/LinkedIn-angles generation as the scheduled pipeline, saving straight into the same Notion database. `--comments` is optional -- if you don't have real comment text to paste in, the public-reaction field will say so rather than invent one. It also skips anything whose URL is already logged, so re-running is safe.

---

## Tests

```
pytest
```
