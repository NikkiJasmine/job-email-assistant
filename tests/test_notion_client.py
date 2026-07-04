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


def test_find_page_by_company_and_role_returns_existing_page():
    client = _client_with_mocked_http()
    response = MagicMock()
    response.json.return_value = {
        "results": [
            {
                "id": "page-456",
                "properties": {
                    "Last Processed Message ID": {"rich_text": [{"plain_text": "msg-9"}]}
                },
            }
        ]
    }
    client._client.post.return_value = response

    existing = client.find_page_by_company_and_role("Acme Corp", "Engineer")

    assert existing.page_id == "page-456"
    assert existing.last_processed_message_id == "msg-9"
    _, kwargs = client._client.post.call_args
    filters = kwargs["json"]["filter"]["and"]
    assert {"property": "Company", "rich_text": {"equals": "Acme Corp"}} in filters
    assert {"property": "Role / Job Title", "rich_text": {"equals": "Engineer"}} in filters


def test_find_page_by_company_and_role_returns_none_when_no_match():
    client = _client_with_mocked_http()
    response = MagicMock()
    response.json.return_value = {"results": []}
    client._client.post.return_value = response

    assert client.find_page_by_company_and_role("Acme Corp", "Engineer") is None


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


def test_find_page_by_company_returns_existing_page():
    client = _client_with_mocked_http()
    response = MagicMock()
    response.json.return_value = {
        "results": [
            {"id": "page-789", "properties": {"Last Processed Message ID": {"rich_text": []}}}
        ]
    }
    client._client.post.return_value = response

    existing = client.find_page_by_company("Nova")

    assert existing.page_id == "page-789"
    _, kwargs = client._client.post.call_args
    assert kwargs["json"]["filter"] == {"property": "Company", "rich_text": {"equals": "Nova"}}


def test_query_pages_paginates_through_all_results():
    client = _client_with_mocked_http()
    page1 = MagicMock()
    page1.json.return_value = {"results": [{"id": "p1"}], "has_more": True, "next_cursor": "abc"}
    page2 = MagicMock()
    page2.json.return_value = {"results": [{"id": "p2"}], "has_more": False}
    client._client.post.side_effect = [page1, page2]

    results = client.query_pages()

    assert [r["id"] for r in results] == ["p1", "p2"]
    first_call_body = client._client.post.call_args_list[0].kwargs["json"]
    assert "start_cursor" not in first_call_body
    second_call_body = client._client.post.call_args_list[1].kwargs["json"]
    assert second_call_body["start_cursor"] == "abc"


def test_append_note_preserves_existing_notes():
    client = _client_with_mocked_http()
    get_response = MagicMock()
    get_response.json.return_value = {
        "properties": {"Notes": {"rich_text": [{"plain_text": "Old note."}]}}
    }
    client._client.get.return_value = get_response
    client._client.patch.return_value = MagicMock()

    client.append_note("page-123", "New note.")

    _, kwargs = client._client.patch.call_args
    combined = kwargs["json"]["properties"]["Notes"]["rich_text"][0]["text"]["content"]
    assert combined == "Old note.\n\nNew note."


def test_append_note_with_no_existing_notes():
    client = _client_with_mocked_http()
    get_response = MagicMock()
    get_response.json.return_value = {"properties": {"Notes": {"rich_text": []}}}
    client._client.get.return_value = get_response
    client._client.patch.return_value = MagicMock()

    client.append_note("page-123", "First note.")

    _, kwargs = client._client.patch.call_args
    combined = kwargs["json"]["properties"]["Notes"]["rich_text"][0]["text"]["content"]
    assert combined == "First note."


def test_create_page_with_body_uses_given_database_and_chunks_text():
    client = _client_with_mocked_http()
    response = MagicMock()
    response.json.return_value = {"id": "brief-page-1"}
    client._client.post.return_value = response

    long_text = "x" * 2500
    page_id = client.create_page_with_body("some-other-db-id", {"Name": {"title": []}}, long_text)

    assert page_id == "brief-page-1"
    _, kwargs = client._client.post.call_args
    assert kwargs["json"]["parent"]["database_id"] == "some-other-db-id"
    children = kwargs["json"]["children"]
    assert len(children) == 2
    assert children[0]["paragraph"]["rich_text"][0]["text"]["content"] == "x" * 2000
    assert children[1]["paragraph"]["rich_text"][0]["text"]["content"] == "x" * 500
