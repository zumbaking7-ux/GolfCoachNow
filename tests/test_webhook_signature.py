"""Signature verification.

The webhook is a public URL. Signature verification is the only thing standing
between it and anyone who can send a POST request, so these tests matter more
than their length suggests.
"""

import json

from conftest import TEST_WEBHOOK_SECRET, load_event, post_webhook, sign_payload
from payments.models import Unlock


def test_valid_signature_is_accepted(client, db_session):
    response = post_webhook(client, load_event())

    assert response.status_code == 200
    assert db_session.query(Unlock).count() == 1


def test_tampered_payload_is_rejected(client, db_session):
    """Sign one body, send a different one.

    This is the attack the signature exists to stop: a real event captured off
    the wire, edited to name a different device, replayed.
    """
    event = load_event()
    honest_payload = json.dumps(event).encode()
    signature = sign_payload(honest_payload)

    event["data"]["object"]["client_reference_id"] = "attacker_device"
    tampered_payload = json.dumps(event).encode()

    response = client.post(
        "/payments/webhook",
        content=tampered_payload,
        headers={"stripe-signature": signature, "content-type": "application/json"},
    )

    assert response.status_code == 400
    assert db_session.query(Unlock).count() == 0


def test_wrong_secret_is_rejected(client, db_session):
    response = post_webhook(client, load_event(), secret="whsec_the_wrong_secret")

    assert response.status_code == 400
    assert db_session.query(Unlock).count() == 0


def test_missing_signature_header_is_rejected(client, db_session):
    response = client.post(
        "/payments/webhook",
        content=json.dumps(load_event()).encode(),
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 400
    assert db_session.query(Unlock).count() == 0


def test_body_that_is_not_json_is_rejected(client):
    payload = b"this is not json"
    response = client.post(
        "/payments/webhook",
        content=payload,
        headers={
            "stripe-signature": sign_payload(payload, TEST_WEBHOOK_SECRET),
            "content-type": "application/json",
        },
    )

    assert response.status_code == 400
