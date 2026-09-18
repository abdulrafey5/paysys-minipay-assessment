"""Regression test for INCIDENT-001: a null completed_at (PROCESSING status)
must not crash GET /api/payments/{ref}. This test would have caught the
deliberately-introduced defect before it reached any environment."""
import os
import requests

API_URL = os.getenv("MINIPAY_API_URL", "http://localhost:18080")


def test_payment_lookup_handles_null_completed_at_without_500():
    # This test is intentionally data-driven against a known PROCESSING-status
    # transaction from the seed dataset, rather than hardcoding a fragile
    # assumption about live transaction creation timing.
    resp = requests.get(f"{API_URL}/api/payments/TXN00000029", timeout=5)
    assert resp.status_code != 500, (
        f"Got 500 for a PROCESSING transaction lookup — null completed_at "
        f"regression reintroduced. Body: {resp.text}"
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "processing_duration_seconds" in body
    assert body["processing_duration_seconds"] is None
