# Job Email Assistant

Daily morning assistant that scans your Gmail for recruitment/job-related emails, summarizes and classifies each one, drafts a suggested reply (as a Gmail draft — **never sent automatically**), and logs everything to your Notion CRM Database. Runs on GitHub Actions; no server to maintain.

## One-time setup

### 1. Google Cloud (Gmail API)

1. Create a project at console.cloud.google.com and enable the **Gmail API**.
2. Configure the OAuth consent screen:
   - User type: **External**
   - Scopes: `gmail.readonly` and `gmail.compose` only
   - Add yourself as a test user
   - **Publishing status: "In Production"** (stay unverified — do not leave it on "Testing"). Testing-mode refresh tokens expire every 7 days under Google's unverified-app policy, which would silently break the daily job. "In Production" while unverified removes that expiry and is standard for a personal single-user script. You'll see one extra "unverified app" click-through during the one-time consent flow below — that's expected.
3. Create an OAuth client ID of type **Desktop app**, download the JSON.
4. Run the local bootstrap script to get a refresh token:
   ```
   pip install -r requirements.txt
   python scripts/local_oauth_bootstrap.py --client-id <id> --client-secret <secret>
   ```
   This opens a browser, asks you to consent, and prints a `refresh_token`.

### 2. LLM provider

This project is provider-agnostic: pick **one** of Anthropic, OpenAI, or Google Gemini via `LLM_PROVIDER`. Only that provider's API key is required.

| `LLM_PROVIDER` | API key                  | Model env var  | Default model        | Get a key at            |
| -------------- | ------------------------- | -------------- | --------------------- | ------------------------ |
| `anthropic`    | `ANTHROPIC_API_KEY`       | `CLAUDE_MODEL` | `claude-sonnet-5`      | console.anthropic.com    |
| `openai`       | `OPENAI_API_KEY`          | `OPENAI_MODEL` | `gpt-4o-mini`          | platform.openai.com      |
| `gemini`       | `GEMINI_API_KEY`          | `GEMINI_MODEL` | `gemini-1.5-flash`     | aistudio.google.com      |

Switching providers later is just changing `LLM_PROVIDER` (and the matching API key) — no code changes needed.

The table above is data, not hard-coded logic: it lives in [`config/providers.yaml`](config/providers.yaml), which `src/common/config.py` reads at startup. Adding a future provider (or renaming an env var) is an edit to that file plus a matching backend class in `src/common/llm_client.py` — no other code changes.

### 3. Notion

1. Create an internal integration at notion.so/my-integrations with Read/Update/Insert content capabilities.
2. Open your "CRM Database" page in Notion → `...` menu → **Connections** → add the integration. Without this step every API call 404s.
3. Add the new properties listed in the plan (`Role / Job Title`, `Recruiter Name`, `Recruiter Email`, `Date Received`, `Date Replied`, `Stage`, `Email Summary`, `Suggested Reply`, `Follow-up Date`, `Interview Date`, `Gmail Thread Link`, `Gmail Thread ID`, `Raw Email Body`), plus 6 new options on the existing `Status` select: `Interview Invitation`, `Rejection`, `Next Step`, `Assessment`, `Request for Information`, `Needs AI Review`.

### 4. GitHub repository secrets & variables

Repo Settings → Secrets and variables → Actions.

**Secrets:** `NOTION_TOKEN`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REFRESH_TOKEN`, plus whichever of `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `GEMINI_API_KEY` matches your chosen provider. If `LLM_PROVIDER=anthropic`, also add `OPENAI_API_KEY` if you want the [automatic billing-error fallback](#resilience-to-llm-provider-outages) to actually engage — otherwise a billing/credit error is just handled like any other provider failure.

**Variables:** `LLM_PROVIDER` (default `anthropic`), `CLAUDE_MODEL` / `OPENAI_MODEL` / `GEMINI_MODEL` (whichever applies), `NOTION_DATA_SOURCE_ID`, `MAX_EMAILS_PER_RUN` (default `20`)

## How it runs

`.github/workflows/daily_job_email_assistant.yml` runs once a day, at 8:00 AM Stockholm time (`workflow_dispatch` also available for manual testing from the Actions tab). Each run:

1. Searches Gmail for job/recruiter-looking emails from the last 2 days.
2. For each thread, checks Notion for an existing row matching its Gmail thread ID whose stored `Last Processed Message ID` already matches the thread's latest message — if so, skips it (no LLM calls at all). This is the dedup mechanism: it's done via Notion rather than a Gmail label, since managing Gmail labels needs a broader OAuth scope (`gmail.labels`/`gmail.modify`) than this project requests.
3. Runs a cheap relevance check to drop keyword false positives.
4. Summarizes, classifies, and drafts a reply for each relevant thread.
5. Before creating a new Notion row, also checks for an existing row with the same `Company` + `Role / Job Title` (skipped if the thread-id check in step 2 already found a match, or if either field is blank). This catches the same application resurfacing on a different Gmail thread — e.g. a recruiter starting a fresh subject line instead of replying inline — and updates that row instead of creating a duplicate.
6. Creates a Gmail **draft** on the thread (never sends).
7. Creates/updates the matching row in your Notion CRM Database, including the new `Last Processed Message ID`, so a failed run retries cleanly the next day and a successful one won't be redone.

You always review and send replies yourself from Gmail.

### Resilience to LLM provider outages

The LLM provider is a third-party dependency, and this pipeline is designed so that provider trouble (an outage, an expired/invalid key, no credits left, being rate-limited, etc) never fails the whole run. When a provider call fails for a given email, the pipeline:

1. Logs the email to Notion (creating or updating its row as usual).
2. Sets its `Status` to `Needs AI Review`.
3. Saves the raw email body in the `Raw Email Body` property, so nothing is lost.
4. Continues on to the remaining emails in the run — one bad provider call never stops the rest.

Rows flagged `Needs AI Review` deliberately do **not** get a `Last Processed Message ID` written, so they're retried against the LLM automatically on every subsequent daily run (no manual intervention needed) until the provider recovers or the underlying issue (e.g. an expired key) is fixed.

**Automatic Anthropic → OpenAI fallback on billing errors.** If `LLM_PROVIDER=anthropic` and Anthropic specifically fails with a billing/credit error (out of credits, quota exceeded), and `OPENAI_API_KEY` is set (as a secret, independent of `LLM_PROVIDER`), the pipeline automatically retries that call against OpenAI instead of flagging it for review. Other Anthropic failures (outage, invalid key, rate limit) are unaffected and still go through the `Needs AI Review` path above. If `OPENAI_API_KEY` isn't set, or the OpenAI fallback also fails, a billing error is handled exactly like any other provider failure — the run never stops either way.

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
