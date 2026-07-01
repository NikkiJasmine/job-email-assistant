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
        response = self._client.post(
            f"/databases/{self.database_id}/query",
            json={
                "filter": {
                    "property": "Gmail Thread ID",
                    "rich_text": {"equals": gmail_thread_id},
                }
            },
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
