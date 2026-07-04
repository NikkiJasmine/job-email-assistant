import base64
from unittest.mock import MagicMock

from src.common import gmail_client


def _b64(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode("utf-8")).decode("utf-8")


def _message(msg_id, from_header, subject, body, message_id_header=None, sent=False):
    headers = [
        {"name": "From", "value": from_header},
        {"name": "Subject", "value": subject},
    ]
    if message_id_header:
        headers.append({"name": "Message-ID", "value": message_id_header})
    return {
        "id": msg_id,
        "labelIds": ["SENT"] if sent else ["INBOX"],
        "payload": {
            "headers": headers,
            "mimeType": "text/plain",
            "body": {"data": _b64(body)},
        },
    }


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
            _message(
                "msg-1",
                "Jane Recruiter <jane@acme.com>",
                "Interview invitation",
                "We'd like to interview you.",
                message_id_header="<abc@acme.com>",
            )
        ]
    }

    thread = gmail_client.get_thread(service, "thread-1")

    assert thread.sender_name == "Jane Recruiter"
    assert thread.sender_email == "jane@acme.com"
    assert thread.subject == "Interview invitation"
    assert thread.rfc_message_id == "<abc@acme.com>"
    assert thread.body_text == "We'd like to interview you."
    assert thread.message_id == "msg-1"
    assert thread.already_replied is False


def test_get_thread_uses_last_inbound_message_not_a_later_sent_reply():
    """If Nicole already replied, the thread's literal last message is her
    own text -- get_thread must still analyze the recruiter's message, not
    her reply, while reporting already_replied=True."""
    service = MagicMock()
    service.users().threads().get().execute.return_value = {
        "messages": [
            _message(
                "msg-1",
                "Jane Recruiter <jane@acme.com>",
                "Interview invitation",
                "We'd like to interview you.",
                message_id_header="<abc@acme.com>",
            ),
            _message(
                "msg-2",
                "Nicole Scott <nicole.scott2696@gmail.com>",
                "Re: Interview invitation",
                "Thanks, I'd love to!",
                sent=True,
            ),
        ]
    }

    thread = gmail_client.get_thread(service, "thread-1")

    assert thread.already_replied is True
    assert thread.sender_email == "jane@acme.com"
    assert thread.body_text == "We'd like to interview you."
    assert thread.message_id == "msg-1"


def test_search_candidate_threads_default_has_no_label_filter():
    service = MagicMock()
    service.users().threads().list().execute.return_value = {
        "threads": [{"id": "t1"}, {"id": "t2"}]
    }

    thread_ids = gmail_client.search_candidate_threads(service, max_results=10)

    assert thread_ids == ["t1", "t2"]
    _, kwargs = service.users().threads().list.call_args
    assert "label:" not in kwargs["q"]
    assert kwargs["q"] == "newer_than:2d in:inbox"


def test_search_candidate_threads_excludes_given_label():
    service = MagicMock()
    service.users().threads().list().execute.return_value = {"threads": []}

    gmail_client.search_candidate_threads(service, max_results=10, exclude_label="Job-Bot-Processed")

    _, kwargs = service.users().threads().list.call_args
    assert kwargs["q"] == "newer_than:2d in:inbox -label:Job-Bot-Processed"


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
        already_replied=False,
    )

    draft_id = gmail_client.create_draft_reply(service, thread, "Thanks for reaching out.")

    assert draft_id == "draft-1"
    # Structural safeguard: this module must never call a send-capable endpoint.
    assert not hasattr(service.users().messages(), "send") or not service.users().messages().send.called
    assert not service.users().drafts().send.called


def test_list_labels_returns_name_to_id_mapping():
    service = MagicMock()
    service.users().labels().list().execute.return_value = {
        "labels": [{"id": "Label_1", "name": "Notes"}, {"id": "Label_13", "name": "Job-Bot-Processed"}]
    }

    assert gmail_client.list_labels(service) == {"Notes": "Label_1", "Job-Bot-Processed": "Label_13"}


def test_get_or_create_label_returns_existing_id_without_creating():
    service = MagicMock()
    service.users().labels().list().execute.return_value = {
        "labels": [{"id": "Label_13", "name": "Job-Bot-Processed"}]
    }

    label_id = gmail_client.get_or_create_label(service, "Job-Bot-Processed")

    assert label_id == "Label_13"
    service.users().labels().create.assert_not_called()


def test_get_or_create_label_creates_when_missing():
    service = MagicMock()
    service.users().labels().list().execute.return_value = {"labels": []}
    service.users().labels().create().execute.return_value = {"id": "Label_new"}

    label_id = gmail_client.get_or_create_label(service, "Job-Bot-Processed")

    assert label_id == "Label_new"
    _, kwargs = service.users().labels().create.call_args
    assert kwargs["body"]["name"] == "Job-Bot-Processed"


def test_apply_label_calls_threads_modify_with_add_label_ids():
    service = MagicMock()

    gmail_client.apply_label(service, "thread-1", "Label_13")

    _, kwargs = service.users().threads().modify.call_args
    assert kwargs["id"] == "thread-1"
    assert kwargs["body"] == {"addLabelIds": ["Label_13"]}
