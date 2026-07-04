"""Generic Notion REST API wrapper: query, create, and update pages.

Uses the stable "database_id"-based endpoints (API version 2022-06-28)
rather than the newer multi-data-source API, since the CRM Database is a
normal single-data-source database -- this keeps the integration simple.

IMPORTANT ID GOTCHA: under Notion's current data model, a database's own ID
and its (single) data source's ID are two DIFFERENT UUIDs. This client's
"database_id" config value must be the database's own page ID -- the UUID
in the database's Notion URL (e.g. notion.so/workspace/Name-<this-uuid>) --
NOT the "collection://<uuid>" data source ID shown in Notion's internal
fetch/search tooling. Passing the data source UUID here returns a 404 from
/v1/databases/{id}/query even with a valid, correctly-shared token.
"""

from dataclasses import dataclass

import httpx

NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


def _normalize_database_id(database_id: str) -> str:
    """Strips a "collection://" prefix if present.

    Note this only removes the prefix -- it does not fix a value that is a
    data source ID rather than a database ID (see module docstring). Those
    are different UUIDs; this function can't tell them apart.
    """
    if database_id.startswith("collection://"):
        return database_id[len("collection://") :]
    return database_id


def _plain_rich_text(page: dict, property_name: str) -> str:
    rich_text = page.get("properties", {}).get(property_name, {}).get("rich_text", [])
    return "".join(part.get("plain_text", "") for part in rich_text)


def plain_select(page: dict, property_name: str) -> str:
    select = page.get("properties", {}).get(property_name, {}).get("select")
    return (select or {}).get("name", "")


def plain_date(page: dict, property_name: str) -> str | None:
    date = page.get("properties", {}).get(property_name, {}).get("date")
    return date.get("start") if date else None


def plain_checkbox(page: dict, property_name: str) -> bool:
    return bool(page.get("properties", {}).get(property_name, {}).get("checkbox"))


# Alias -- exposed publicly (the leading underscore was module-private) since
# the Daily Career Review needs to read text properties (Company, Next Step,
# ...) off raw pages returned by query_pages(), not just internally here.
plain_rich_text = _plain_rich_text


def _chunk_text(text: str, limit: int) -> list[str]:
    text = text or ""
    return [text[i : i + limit] for i in range(0, len(text), limit)] or [""]


@dataclass
class ExistingPage:
    page_id: str
    last_processed_message_id: str


class NotionClient:
    def __init__(self, token: str, database_id: str):
        self.database_id = _normalize_database_id(database_id)
        self._client = httpx.Client(
            base_url=NOTION_API_BASE,
            headers={
                "Authorization": f"Bearer {token}",
                "Notion-Version": NOTION_VERSION,
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

    def find_page_by_thread_id(self, gmail_thread_id: str) -> ExistingPage | None:
        """Returns the existing page (and its last-processed message id) for this thread, if any."""
        return self._find_page(
            {"property": "Gmail Thread ID", "rich_text": {"equals": gmail_thread_id}}
        )

    def find_page_by_company_and_role(self, company: str, role: str) -> ExistingPage | None:
        """Returns the existing page for this Company + Role / Job Title combination, if any.

        Fallback dedup match used when a thread-id lookup misses -- e.g. the
        same application resurfaces on a new Gmail thread (a recruiter
        starting a fresh subject line rather than replying on the original
        thread). See job_assistant/main.py._process_thread.
        """
        return self._find_page(
            {
                "and": [
                    {"property": "Company", "rich_text": {"equals": company}},
                    {"property": "Role / Job Title", "rich_text": {"equals": role}},
                ]
            }
        )

    def find_page_by_company(self, company: str) -> ExistingPage | None:
        """Returns the existing page for this Company alone, if any -- used
        as the fallback search when a Gmail Thread ID lookup misses (e.g. an
        automated ATS notification with no distinct thread history yet).
        """
        return self._find_page({"property": "Company", "rich_text": {"equals": company}})

    def query_pages(self, filter_: dict | None = None, page_size: int = 100) -> list[dict]:
        """Returns raw page objects matching filter_ (all pages if None),
        paginating through every result. Used by the Daily Career Review,
        which needs to scan many rows rather than find a single match."""
        results: list[dict] = []
        cursor: str | None = None
        while True:
            body: dict = {"page_size": page_size}
            if filter_:
                body["filter"] = filter_
            if cursor:
                body["start_cursor"] = cursor
            response = self._client.post(f"/databases/{self.database_id}/query", json=body)
            response.raise_for_status()
            data = response.json()
            results.extend(data.get("results", []))
            if not data.get("has_more"):
                return results
            cursor = data.get("next_cursor")

    def append_note(self, page_id: str, note_text: str) -> None:
        """Appends note_text to the page's existing Notes, never overwriting
        prior content."""
        response = self._client.get(f"/pages/{page_id}")
        response.raise_for_status()
        existing = _plain_rich_text(response.json(), "Notes")
        combined = f"{existing}\n\n{note_text}" if existing else note_text
        self.update_page(page_id, {"Notes": text_prop(combined)})

    def create_page_with_body(self, database_id: str, properties: dict, body_text: str) -> str:
        """Creates a page in the given database (not necessarily this
        client's own database_id) with body_text as page content -- used for
        the Morning Brief digest, which is longer than a single rich_text
        property can hold. Chunks into <=2000-char paragraph blocks (Notion's
        per-block text limit)."""
        children = [
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {"rich_text": [{"type": "text", "text": {"content": chunk}}]},
            }
            for chunk in _chunk_text(body_text, 2000)
        ]
        response = self._client.post(
            "/pages",
            json={
                "parent": {"database_id": _normalize_database_id(database_id)},
                "properties": properties,
                "children": children,
            },
        )
        response.raise_for_status()
        return response.json()["id"]

    def _find_page(self, filter_: dict) -> ExistingPage | None:
        response = self._client.post(
            f"/databases/{self.database_id}/query",
            json={"filter": filter_},
        )
        response.raise_for_status()
        results = response.json().get("results", [])
        if not results:
            return None
        page = results[0]
        return ExistingPage(
            page_id=page["id"],
            last_processed_message_id=_plain_rich_text(page, "Last Processed Message ID"),
        )

    def create_page(self, properties: dict) -> str:
        response = self._client.post(
            "/pages",
            json={"parent": {"database_id": self.database_id}, "properties": properties},
        )
        response.raise_for_status()
        return response.json()["id"]

    def update_page(self, page_id: str, properties: dict) -> None:
        response = self._client.patch(f"/pages/{page_id}", json={"properties": properties})
        response.raise_for_status()


# --- Property value builders, one per Notion property type used by this project ---


def title_prop(text: str) -> dict:
    return {"title": [{"text": {"content": text[:2000]}}]}


def text_prop(text: str) -> dict:
    return {"rich_text": [{"text": {"content": (text or "")[:2000]}}]}


def select_prop(name: str) -> dict:
    return {"select": {"name": name}}


def date_prop(iso_date: str | None) -> dict:
    return {"date": {"start": iso_date} if iso_date else None}


def email_prop(email: str) -> dict:
    return {"email": email or None}


def url_prop(url: str) -> dict:
    return {"url": url or None}
