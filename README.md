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

1. Searches Gmail for job/recruiter-looking emails not already labeled `AI-Processed`.
2. Runs a cheap relevance check to drop false positives.
3. Summarizes, classifies, and drafts a reply for each relevant thread.
4. Creates a Gmail **draft** on the thread (never sends).
5. Creates/updates the matching row in your Notion CRM Database.
6. Labels the thread `AI-Processed` only after both writes succeed, so a failed run retries cleanly next hour.

You always review and send replies yourself from Gmail.

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
