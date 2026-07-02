# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project does

An hourly assistant that scans a Gmail inbox for recruitment/job-related emails, uses an LLM to summarize and classify each one and draft a suggested reply (as a Gmail **draft** — never sent automatically), and logs everything to a Notion CRM database. Runs on GitHub Actions on a cron schedule; no server to maintain. The user always reviews and sends replies themselves from Gmail.

## Tech stack

- Python 3.12, stdlib `dataclasses` for models, no web framework.
- `anthropic` / `openai` / `google-genai` SDKs for LLM calls (provider-agnostic, see Architecture below).
- `google-api-python-client` + `google-auth` for Gmail (OAuth installed-app flow).
- `httpx` for raw Notion REST API calls (no Notion SDK).
- `python-dotenv` for local `.env` loading; `PyYAML` for `config/providers.yaml`.
- `pytest` for tests, run via GitHub Actions (`.github/workflows/hourly_job_emails.yml`) on an hourly cron plus `workflow_dispatch`.

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

For each candidate Gmail thread: **dedup check → relevance check → analyze → write to Notion → draft reply in Gmail**.

- Dedup is done via Notion, not Gmail labels — a thread is skipped (no LLM calls at all) if an existing Notion row's `Last Processed Message ID` already matches the thread's latest message. Gmail label-based dedup was deliberately avoided because it needs a broader OAuth scope (`gmail.labels`/`gmail.modify`) than this project requests (readonly + compose only).
- Thread-id dedup only catches the same Gmail thread reappearing. Before creating a new row (i.e. no thread-id match), `_process_thread` also checks `notion.find_page_by_company_and_role` for an existing row with the same `Company` + `Role / Job Title` and updates that instead — this catches the same application resurfacing on a *different* Gmail thread. Skipped when either field is blank, since matching on an empty string would merge unrelated applications.
- `run()` never lets one bad thread take down the whole run: `_process_thread` exceptions are caught per-thread and logged, but if **every** candidate thread fails, `run()` raises `RuntimeError` so GitHub Actions reports the run as failed (this is treated as a likely systemic issue — bad credentials, wrong Notion database id — rather than per-email flukes).

### Provider-agnostic LLM layer (`src/common/llm_client.py`)

`LLMClient` is a thin facade over per-provider "backend" classes (`_AnthropicBackend`, `_OpenAIBackend`, `_GeminiBackend`), each implementing the same two-method interface: `is_job_related(text) -> bool` and `analyze_email(text) -> EmailAnalysis`. The provider is selected at runtime via `LLM_PROVIDER` (`anthropic` | `openai` | `gemini`, resolved in `config.load_config()`). Adding a new provider means adding one backend class and one entry in the `_BACKENDS` registry — the public interface never changes.

Provider *settings* (which env var holds the API key, which env var overrides the model, and the default model) are data, not code: they live in [`config/providers.yaml`](config/providers.yaml), loaded once at import time by `config._load_provider_registry()`. `config.py` never hard-codes a model name outside that file's defaults. Adding a provider's settings is a YAML edit; wiring up its actual API calls is the backend class in `llm_client.py`.

Every backend method wraps its provider call in a broad `try/except` and re-raises as `LLMProviderError`, regardless of the underlying cause (invalid key, no credits, outage, rate limit, malformed response, etc). This is intentional: `main._process_thread` catches `LLMProviderError` specifically and, instead of failing the run, logs the thread to Notion with `Status = "Needs AI Review"` and the raw email body saved, then moves on to the next thread. That fallback row deliberately does **not** get a `Last Processed Message ID`, so it's retried against the LLM automatically on the next hourly run once the provider recovers.

`LLMBillingError` (a subclass of `LLMProviderError`) is `_AnthropicBackend`'s narrower signal for a billing/credit failure specifically (detected via the error's `.type == "billing_error"`, with a message-text fallback), as opposed to any other failure. `LLMClient` uses it to implement a one-way, Anthropic-only fallback: if the primary provider is `anthropic` and `config.openai_fallback_api_key` is set (populated from `OPENAI_API_KEY`, independent of `LLM_PROVIDER`), a billing error is retried once against an `_OpenAIBackend` before propagating. Non-billing Anthropic failures never trigger this — they go straight to the `Needs AI Review` path like any other provider error, since a fallback provider is no more likely to help with an outage or invalid key.

The three CLASSIFICATIONS/analysis JSON schema (`_ANALYSIS_JSON_SCHEMA`) is shared verbatim across all three providers' tool/function/response-schema definitions rather than duplicated per backend.

Email content passed to any provider is always wrapped in `<email>...</email>` tags with an explicit system-prompt instruction to treat it as untrusted data, never as instructions — a first line of defense against prompt injection from email content. The LLM's only outputs are a human-reviewed draft and Notion fields, so the blast radius of a successful injection is inherently limited.

### Notion property model (`src/common/notion_client.py`, `src/job_assistant/models.py`)

Uses the stable `database_id`-based endpoints (API version `2022-06-28`). **Important gotcha:** a Notion database's own page ID and its data source ID are different UUIDs — `NOTION_DATA_SOURCE_ID` must be the database's own page UUID (from its URL), not the `collection://...` data source ID; the wrong one 404s even with a valid token. `notion_client.py`'s module docstring has the full explanation.

`models.py` holds the shared constants that couple the pipeline to specific Notion select-option values: `CLASSIFICATIONS`/`STAGE_MAPPING` (must match the `Status`/`Stage` select options configured in Notion) and `NEEDS_AI_REVIEW_STATUS`.

### Gmail safety (`src/common/gmail_client.py`)

This module intentionally never implements or calls any send-capable method (`users.messages.send`, `users.drafts.send`) — that is the structural safeguard against ever sending email automatically, not just the OAuth scope. Do not add a send function here.

## Working in this repo

- Always explain your plan before making changes.
- Run the test suite (`pytest`) after making changes and before considering a task done.
- Keep code clean and well documented — but per this repo's existing style, prefer clear naming over comments; only add a comment when it captures a non-obvious *why* (see existing module docstrings for examples), not a restatement of what the code does.
