# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project does

A daily morning assistant ("Morning Job Brief") that scans a Gmail inbox for recruitment/job-related emails, uses Gemini to summarize, classify, and legitimacy-check each one, drafts a suggested reply (as a Gmail **draft** — never sent automatically), logs everything to a Notion CRM database, reviews that CRM for overdue follow-ups, and delivers a short digest as a new page in a Notion "Morning Briefs" database. Runs on GitHub Actions on a cron schedule (once daily, 8:00 AM Stockholm time); no server to maintain. The user always reviews and sends replies themselves from Gmail.

This pipeline deliberately hardcodes Google Gemini and never calls the Anthropic API — see "Provider-agnostic LLM layer" below for why the multi-provider infrastructure still exists in the codebase despite that.

There's a separate, complementary layer of Claude Code subagents (`.claude/agents/*.md` — Career CRM Agent, Job Search Assistant, Outreach Agent, Story Scout, CV Agent) for on-demand tasks like job search, outreach drafting, and CV review. Those only work invoked directly in an interactive Claude Code conversation — personal Connectors (Gmail, Notion) don't propagate to agents spawned via the Agent tool, only environment-level integrations do (confirmed via a live capability check; see each agent file's "Known limitation" section). This repo's actual automation (the thing that runs unattended on a schedule) is pure Python + GitHub Actions, not a Claude subagent.

## Tech stack

- Python 3.12, stdlib `dataclasses` for models, no web framework.
- `google-genai` SDK for the Gemini LLM calls this pipeline actually uses. `anthropic`/`openai` SDKs remain as dependencies of the shared, unused-by-this-pipeline provider-agnostic `llm_client.py` layer.
- `google-api-python-client` + `google-auth` for Gmail (OAuth installed-app flow, `gmail.modify` scope).
- `httpx` for raw Notion REST API calls (no Notion SDK).
- `python-dotenv` for local `.env` loading; `PyYAML` for `config/providers.yaml`.
- `pytest` for tests, run via GitHub Actions (`.github/workflows/morning-job-brief.yml`) on a daily cron (mornings) plus `workflow_dispatch`.

## Commands

```
pip install -r requirements.txt        # install deps
cp .env.example .env                   # fill in real values for local runs
python -m src.job_assistant.main       # run the pipeline once, locally
pytest                                  # run the full test suite
pytest tests/test_llm_client.py         # run one test file
pytest tests/test_main.py::test_run_raises_when_every_thread_fails   # run a single test
python scripts/local_oauth_bootstrap.py --client-id <id> --client-secret <secret>  # one-time: mint a Gmail refresh token
```

Set `MAX_EMAILS_PER_RUN=2` in `.env` for a small first local test run.

## Architecture

### Pipeline (`src/job_assistant/main.py`)

For each candidate Gmail thread: **dedup check → relevance check → analyze (summary, classification, priority, legitimacy) → write to Notion → draft reply in Gmail → best-effort label**. After all threads: **Daily Career Review → Morning Brief → deliver to Notion**.

- Dedup is primarily a Gmail label (`Job-Bot-Processed`, created on first run if missing) — the search query excludes anything already carrying it. This replaced an earlier Notion-message-id-based scheme once the OAuth scope was widened to `gmail.modify` to support label management.
- `gmail_client.get_thread` analyzes the last *inbound* message, not unconditionally the thread's last message — if the user already replied, the literal last message is her own text. `EmailThread.already_replied` reflects whether an even-newer outbound message exists after that.
- Before creating a new row (i.e. no thread-id match), `_process_thread` also checks `notion.find_page_by_company` for an existing row with the same `Company` and updates that instead — this catches the same application resurfacing on a *different* Gmail thread (e.g. a fresh subject line). Skipped when `Company` is blank, since matching on an empty string would merge unrelated applications.
- `Status` is written from a constrained enum (`Active`/`Messaged`/`Call Scheduled`/`Closed`/`Followed Up`, see `models.determine_status`) computed from the classification and `already_replied` — it tracks *conversation state*, distinct from `Stage` (pipeline phase, via `STAGE_MAPPING`) and from the classification itself (folded into the `Email Summary` text as a `[Classification]` prefix rather than its own property).
- Label application is **best-effort and never blocks the Notion update**: attempt `gmail_client.apply_label`; on success, done; on failure, log a warning and continue — the CRM write already happened either way. See `_apply_label_best_effort`.
- `run()` never lets one bad thread take down the whole run: `_process_thread` exceptions are caught per-thread and logged, but if **every** candidate thread fails, `run()` raises `RuntimeError` so GitHub Actions reports the run as failed (treated as a likely systemic issue — bad credentials, wrong Notion database id — rather than per-email flukes).
- `_daily_career_review` scans the whole CRM (`notion.query_pages`) for overdue follow-ups, applications waiting >7 days, and upcoming interviews, excluding rows already `Closed`/`Rejected`. `_compose_morning_brief` turns that plus the run's `ThreadOutcome`s into the digest text, and `_rank_priority_actions` picks the top 5 for the "Recommended priorities" section.
- The Morning Brief is delivered as a new page (with the digest as page-body paragraphs, not a property — it's often too long for a single rich_text property) in a separate Notion database (`NOTION_MORNING_BRIEF_DATABASE_ID`), via `notion_client.create_page_with_body`.

### Provider-agnostic LLM layer (`src/common/llm_client.py`)

`LLMClient` is a thin facade over per-provider "backend" classes (`_AnthropicBackend`, `_OpenAIBackend`, `_GeminiBackend`), each implementing the same two-method interface: `is_job_related(text) -> bool` and `analyze_email(text) -> EmailAnalysis`. The provider is selectable via `LLM_PROVIDER`, resolved in `config.load_config()` — **but `job_assistant/main.py` always constructs `LLMClient("gemini", config.gemini_api_key, config.gemini_model)` directly, ignoring `LLM_PROVIDER`/`config.llm_api_key`/`config.llm_model` entirely.** `config.gemini_api_key`/`gemini_model` are populated unconditionally from `GEMINI_API_KEY`/`GEMINI_MODEL` regardless of what `LLM_PROVIDER` is set to, specifically so main.py can never accidentally pair another provider's key with the Gemini backend. This multi-provider machinery (and the Anthropic/OpenAI billing-fallback logic below) remains as shared, tested infrastructure — it's just not exercised by this repo's actual automation.

`EmailAnalysis` carries: `summary`, `what_recruiter_wants`, `classification` (one of `CLASSIFICATIONS`: Good news / Rejection / Interview invitation / Request for more information / Case study or assessment / Another next step), `suggested_reply`, `company`, `role`, `contact_name` (signature/display name, empty if none — never guessed from an email address), `priority` (Urgent/High/Normal/Low), `legitimacy_confidence`, `legitimacy_notes`, `next_action`. The shared JSON schema (`_ANALYSIS_JSON_SCHEMA`) is reused verbatim across all three providers' tool/function/response-schema definitions.

Every backend method wraps its provider call in a broad `try/except` and re-raises as `LLMProviderError`, regardless of the underlying cause (invalid key, no credits, outage, rate limit, malformed response, etc). `main._process_thread` catches `LLMProviderError` specifically and, instead of failing the run, logs the thread to Notion with `Status = "Needs AI Review"` and the raw email body saved, then moves on. That fallback row deliberately gets no `Last Processed Message ID` and is **not** labeled `Job-Bot-Processed`, so it's retried automatically on the next daily run once the provider recovers.

`LLMBillingError`/the Anthropic→OpenAI billing fallback still exist in `LLMClient` but are dead code from this pipeline's perspective (it never constructs an Anthropic backend) — kept because the class is still directly tested and could matter if a future pipeline selects Anthropic.

Email content passed to any provider is always wrapped in `<email>...</email>` tags with an explicit system-prompt instruction to treat it as untrusted data, never as instructions — a first line of defense against prompt injection from email content. `main._email_context` also includes the sender name/email/subject alongside the body, so the legitimacy check has the sender's actual domain to compare against the claimed company.

### Notion property model (`src/common/notion_client.py`, `src/job_assistant/models.py`)

Uses the stable `database_id`-based endpoints (API version `2022-06-28`). **Important gotcha:** a Notion database's own page ID and its data source ID are different UUIDs — `NOTION_DATA_SOURCE_ID` must be the database's own page UUID (from its URL), not the `collection://...` data source ID; the wrong one 404s even with a valid token. `notion_client.py`'s module docstring has the full explanation.

`NotionClient.append_note` fetches existing `Notes` and appends rather than overwrites — every write to `Notes` (today's date, summary, whether replied, legitimacy notes, attachments) goes through it. `query_pages` paginates through every result matching a filter (used by the Daily Career Review, which needs to scan many rows, not just find one match). `create_page_with_body` creates a page in an arbitrary database (not necessarily the client's own `database_id`) with long text as chunked paragraph blocks — used for the Morning Brief, since a single rich_text property caps at 2000 characters.

`models.py` holds `JOB_BOT_LABEL_NAME`, `STAGE_MAPPING` (classification → Stage), `NEEDS_AI_REVIEW_STATUS`, `CONVERSATION_STATUSES`, and `determine_status()` (classification + already_replied + next_action → one of `CONVERSATION_STATUSES`).

### Gmail (`src/common/gmail_client.py`)

Scope is `gmail.modify` — widened from the earlier `gmail.readonly` + `gmail.compose` specifically to support label management (`list_labels`/`get_or_create_label`/`apply_label`), which is now the primary dedup mechanism. This module still intentionally never implements or calls any send-capable method (`users.messages.send`, `users.drafts.send`) — that remains the structural safeguard against ever sending email automatically, not just the OAuth scope. Do not add a send function here.

`search_candidate_threads` builds a deliberately plain `newer_than:2d in:inbox [-label:X]` query rather than a keyword-boolean one — in practice a keyword query both misses genuine recruiter threads and lets spam through, so relevance is judged per-thread (via the LLM's cheap `is_job_related` check) instead of pre-filtered by search terms.

## Working in this repo

- Always explain your plan before making changes.
- Run the test suite (`pytest`) after making changes and before considering a task done.
- Keep code clean and well documented — but per this repo's existing style, prefer clear naming over comments; only add a comment when it captures a non-obvious *why* (see existing module docstrings for examples), not a restatement of what the code does.
