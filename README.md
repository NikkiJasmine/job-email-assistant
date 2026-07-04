# Morning Job Brief

Daily morning assistant that scans your Gmail for recruitment/job-related emails, checks them for legitimacy, drafts a suggested reply (as a Gmail draft — **never sent automatically**), logs everything to your Notion CRM Database, reviews it for overdue follow-ups, and delivers a short "Morning Job Brief" digest to Notion. Runs on GitHub Actions; no server to maintain.

## One-time setup

### 1. Google Cloud (Gmail API)

1. Create a project at console.cloud.google.com and enable the **Gmail API**.
2. Configure the OAuth consent screen:
   - User type: **External**
   - Scope: `gmail.modify` only (a superset of read/compose that also covers label management — this pipeline's primary dedup mechanism is a Gmail label, which needs this broader scope; the code still never calls a send-capable endpoint, so nothing gets sent automatically)
   - Add yourself as a test user
   - **Publishing status: "In Production"** (stay unverified — do not leave it on "Testing"). Testing-mode refresh tokens expire every 7 days under Google's unverified-app policy, which would silently break the daily job. "In Production" while unverified removes that expiry and is standard for a personal single-user script. You'll see one extra "unverified app" click-through during the one-time consent flow below — that's expected.
3. Create an OAuth client ID of type **Desktop app**, download the JSON.
4. Run the local bootstrap script to get a refresh token:
   ```
   pip install -r requirements.txt
   python scripts/local_oauth_bootstrap.py --client-id <id> --client-secret <secret>
   ```
   This opens a browser, asks you to consent, and prints a `refresh_token`. If you have a refresh token from before the `gmail.modify` scope change, mint a new one — the old one won't have label-management permission and label calls will fail.

### 2. Google Gemini

This pipeline hardcodes Google Gemini as its LLM provider (not configurable, and it never calls the Anthropic API). Get a key at aistudio.google.com.

The repo also ships a provider-agnostic LLM layer (`src/common/llm_client.py`, supporting Anthropic/OpenAI/Gemini via `LLM_PROVIDER`) as shared infrastructure — but `job_assistant/main.py` always uses Gemini directly regardless of that setting, via its own `GEMINI_API_KEY`/`GEMINI_MODEL`.

### 3. Notion

1. Create an internal integration at notion.so/my-integrations with Read/Update/Insert content capabilities.
2. Open your "CRM Database" page in Notion → `...` menu → **Connections** → add the integration. Without this step every API call 404s.
3. Make sure these properties exist (additive-only if you're extending an existing database): `Company`, `Role / Job Title`, `Recruiter Name`, `Recruiter Email`, `Date Received`, `Date Replied`, `Stage`, `Priority`, `Email Summary`, `Suggested Reply`, `Next Step`, `Follow-up Date`, `Interview Date`, `Last Contact`, `Gmail Thread Link`, `Gmail Thread ID`, `Last Processed Message ID`, `Raw Email Body`, `Notes`, `Archived`, `Track`, `Category`.
4. `Status` select needs at minimum: `Active`, `Messaged`, `Call Scheduled`, `Closed`, `Followed Up` (the only values this pipeline writes for a resolved thread) plus `Needs AI Review` (the LLM-outage retry marker).
5. `Stage` select needs at minimum: `Applied`, `Interviewing`, `Case Study`, `Rejected` (set manually: `Offer`, `Waiting to Hear`, `Closed`).
6. Create a second, separate database for the daily brief itself — minimal schema: `Name` (title), `Date` (date). Share the same integration with it. Copy its database UUID for `NOTION_MORNING_BRIEF_DATABASE_ID`.

### 4. GitHub repository secrets & variables

Repo Settings → Secrets and variables → Actions.

**Secrets:** `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REFRESH_TOKEN`, `NOTION_TOKEN`, `GEMINI_API_KEY`

**Variables:** `NOTION_DATA_SOURCE_ID` (the CRM Database), `NOTION_MORNING_BRIEF_DATABASE_ID` (the brief database), `GEMINI_MODEL` (optional, defaults to `gemini-1.5-flash`), `MAX_EMAILS_PER_RUN` (default `20`)

## How it runs

`.github/workflows/morning-job-brief.yml` runs once a day, at 8:00 AM Stockholm time (`workflow_dispatch` also available for manual testing from the Actions tab). Each run:

1. Checks whether a Gmail label called `Job-Bot-Processed` exists, creating it if not.
2. Searches Gmail for candidate threads from the last 2 days, excluding anything already carrying that label. This label is the *primary* dedup mechanism.
3. For each candidate thread, reads the last inbound message (not a later reply of your own, if you've already answered), runs a cheap relevance check to drop non-recruitment threads, then analyzes the relevant ones: summary, classification, priority, a legitimacy/scam check, and a recommended next action.
4. Searches Notion first by Gmail Thread ID, then by Company, before deciding whether to create a new row or update an existing one — this catches the same application resurfacing on a different thread (e.g. a fresh subject line).
5. Appends to the row's `Notes` (never overwriting), sets `Status` to one of `Active` / `Messaged` / `Call Scheduled` / `Closed` / `Followed Up` based on the classification and whether you've already replied.
6. Creates a Gmail **draft** reply (skipped if you've already replied on that thread).
7. Applies the `Job-Bot-Processed` label — **best-effort**: if labeling fails, it logs a warning and moves on; the Notion update always happens regardless of whether labeling succeeded.
8. After all threads: reviews the whole CRM Database for overdue follow-ups, applications waiting more than 7 days, and upcoming interviews.
9. Composes a "🌅 Morning Job Brief" digest and writes it as a new page in your Morning Briefs database.

You always review and send replies yourself from Gmail.

### Resilience to LLM provider outages

The LLM provider is a third-party dependency, and this pipeline is designed so that provider trouble (an outage, an expired/invalid key, no credits left, being rate-limited, etc) never fails the whole run. When a provider call fails for a given email, the pipeline:

1. Logs the email to Notion (creating or updating its row as usual).
2. Sets its `Status` to `Needs AI Review`.
3. Saves the raw email body in the `Raw Email Body` property, so nothing is lost.
4. Continues on to the remaining emails in the run — one bad provider call never stops the rest.

Rows flagged `Needs AI Review` deliberately do **not** get a `Last Processed Message ID` written and are **not** labeled `Job-Bot-Processed`, so they're retried against the LLM automatically on every subsequent daily run (no manual intervention needed) until the provider recovers.

## Local testing

```
cp .env.example .env   # fill in real values
pip install -r requirements.txt
python -m src.job_assistant.main
```

Set `MAX_EMAILS_PER_RUN=2` in `.env` for a small first test run.

## Tests

```
pytest
```
