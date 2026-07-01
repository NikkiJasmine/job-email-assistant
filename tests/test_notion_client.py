from unittest.mock import MagicMock

from src.common.notion_client import NotionClient, _normalize_database_id


def test_normalize_database_id_strips_collection_prefix():
    assert (
        _normalize_database_id("collection://88ec86e8-085d-4b7d-a155-d26b1e2e554f")
        == "88ec86e8-085d-4b7d-a155-d26b1e2e554f"
    )


def test_normalize_database_id_passes_through_plain_uuid():
    assert _normalize_database_id("88ec86e8-085d-4b7d-a155-d26b1e2e554f") == (
        "88ec86e8-085d-4b7d-a155-d26b1e2e554f"
    )


def _client_with_mocked_http():
    client = NotionClient(token="secret", database_id="88ec86e8-085d-4b7d-a155-d26b1e2e554f")
    client._client = MagicMock()
    return client


def test_find_page_by_thread_id_returns_existing_page():
    client = _client_with_mocked_http()
    response = MagicMock()
    response.json.return_value = {
        "results": [
            {
                "id": "page-123",
                "properties": {
                    "Last Processed Message ID": {
                        "rich_text": [{"plain_text": "msg-1"}]
                    }
                },
            }
        ]
    }
    client._client.post.return_value = response

    existing = client.find_page_by_thread_id("thread-abc")

    assert existing.page_id == "page-123"
    assert existing.last_processed_message_id == "msg-1"
    _, kwargs = client._client.post.call_args
    assert kwargs["json"]["filter"]["rich_text"]["equals"] == "thread-abc"


def test_find_page_by_thread_id_returns_none_when_no_match():
    client = _client_with_mocked_http()
    response = MagicMock()
    response.json.return_value = {"results": []}
    client._client.post.return_value = response

    assert client.find_page_by_thread_id("thread-missing") is None


def test_create_page_uses_configured_database_id():
    client = _client_with_mocked_http()
    response = MagicMock()
    response.json.return_value = {"id": "new-page"}
    client._client.post.return_value = response

    page_id = client.create_page({"Name": {"title": []}})

    assert page_id == "new-page"
    _, kwargs = client._client.post.call_args
    assert kwargs["json"]["parent"]["database_id"] == "88ec86e8-085d-4b7d-a155-d26b1e2e554f"


def test_update_page_calls_patch_with_page_id():
    client = _client_with_mocked_http()
    client._client.patch.return_value = MagicMock()

    client.update_page("page-123", {"Status": {"select": {"name": "Rejection"}}})

    args, _ = client._client.patch.call_args
    assert args[0] == "/pages/page-123"
