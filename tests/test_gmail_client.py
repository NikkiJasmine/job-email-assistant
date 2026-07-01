import base64
from unittest.mock import MagicMock

from src.common import gmail_client


def _b64(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode("utf-8")).decode("utf-8")


def test_thread_link():
    assert gmail_client.thread_link("abc123") == "https://mail.google.com/mail/u/0/#all/abc123"


def test_decode_body_plain_text():
    payload = {"mimeType": "text/plain", "body": {"data": _b64("Hello world")}}
    assert gmail_client._decode_body(payload) == "Hello world"


def test_decode_body_multipart():
    payload = {
        "mimeType": "multipart/alternative",
        "parts": [
            {"mimeType": "text/html", "body": {"data": _b64("<p>hi</p>")}},
            {"mimeType": "text/plain", "body": {"data": _b64("plain hi")}},
        ],
    }
    # text/plain part should be found via recursion even if listed second
    assert gmail_client._decode_body(payload) == "plain hi"


def test_get_thread_parses_sender_and_subject():
    service = MagicMock()
    service.users().threads().get().execute.return_value = {
        "messages": [
            {
                "id": "msg-1",
                "payload": {
                    "headers": [
                        {"name": "From", "value": "Jane Recruiter <jane@acme.com>"},
                        {"name": "Subject", "value": "Interview invitation"},
                        {"name": "Message-ID", "value": "<abc@acme.com>"},
                    ],
                    "mimeType": "text/plain",
                    "body": {"data": _b64("We'd like to interview you.")},
                },
            }
        ]
    }

    thread = gmail_client.get_thread(service, "thread-1")

    assert thread.sender_name == "Jane Recruiter"
    assert thread.sender_email == "jane@acme.com"
    assert thread.subject == "Interview invitation"
    assert thread.rfc_message_id == "<abc@acme.com>"
    assert thread.body_text == "We'd like to interview you."


def test_search_candidate_threads_excludes_processed_label():
    service = MagicMock()
    service.users().threads().list().execute.return_value = {
        "threads": [{"id": "t1"}, {"id": "t2"}]
    }

    thread_ids = gmail_client.search_candidate_threads(service, max_results=10)

    assert thread_ids == ["t1", "t2"]
    _, kwargs = service.users().threads().list.call_args
    assert "-label:AI-Processed" in kwargs["q"]


def test_get_or_create_label_reuses_existing():
    service = MagicMock()
    service.users().labels().list().execute.return_value = {
        "labels": [{"id": "Label_1", "name": "AI-Processed"}]
    }

    label_id = gmail_client.get_or_create_label(service)

    assert label_id == "Label_1"
    service.users().labels().create.assert_not_called()


def test_get_or_create_label_creates_when_missing():
    service = MagicMock()
    service.users().labels().list().execute.return_value = {"labels": []}
    service.users().labels().create().execute.return_value = {"id": "Label_new"}

    label_id = gmail_client.get_or_create_label(service)

    assert label_id == "Label_new"


def test_create_draft_reply_never_calls_send():
    service = MagicMock()
    service.users().drafts().create().execute.return_value = {"id": "draft-1"}

    thread = gmail_client.EmailThread(
        thread_id="t1",
        message_id="m1",
        rfc_message_id="<abc@acme.com>",
        subject="Interview invitation",
        sender_name="Jane",
        sender_email="jane@acme.com",
        body_text="body",
    )

    draft_id = gmail_client.create_draft_reply(service, thread, "Thanks for reaching out.")

    assert draft_id == "draft-1"
    # Structural safeguard: this module must never call a send-capable endpoint.
    assert not hasattr(service.users().messages(), "send") or not service.users().messages().send.called
    assert not service.users().drafts().send.called
