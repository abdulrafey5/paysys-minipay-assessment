import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))
from diagnostics import analyze_transaction, summarize_stuck_report


def test_stuck_processing_flagged():
    now = datetime(2026, 9, 18, 12, 0, 0)
    tx = {"status": "PROCESSING", "created_at": now - timedelta(minutes=30)}
    result = analyze_transaction(tx, callbacks=[], now=now, stuck_threshold_minutes=15)
    assert any("exceeding" in a for a in result["anomalies"])
    assert "Escalate" in result["recommended_action"]


def test_processing_within_threshold_not_flagged():
    now = datetime(2026, 9, 18, 12, 0, 0)
    tx = {"status": "PROCESSING", "created_at": now - timedelta(minutes=5)}
    result = analyze_transaction(tx, callbacks=[], now=now, stuck_threshold_minutes=15)
    assert result["anomalies"] == ["No anomalies detected."]


def test_failed_transaction_reports_failure_code():
    tx = {"status": "FAILED", "failure_code": "UPSTREAM_ERROR", "created_at": datetime.utcnow()}
    result = analyze_transaction(tx, callbacks=[])
    assert "UPSTREAM_ERROR" in result["recommended_action"]


def test_success_without_successful_callback_flagged_as_anomaly():
    tx = {"status": "SUCCESS", "created_at": datetime.utcnow()}
    callbacks = [{"callback_status": "FAILED"}, {"callback_status": "FAILED"}]
    result = analyze_transaction(tx, callbacks)
    assert any("reconciliation mismatch" in a for a in result["anomalies"])


def test_success_with_successful_callback_is_clean():
    tx = {"status": "SUCCESS", "created_at": datetime.utcnow()}
    callbacks = [{"callback_status": "SUCCESS"}]
    result = analyze_transaction(tx, callbacks)
    assert result["anomalies"] == ["No anomalies detected."]


def test_multiple_callback_attempts_flagged():
    tx = {"status": "SUCCESS", "created_at": datetime.utcnow()}
    callbacks = [{"callback_status": "FAILED"}, {"callback_status": "SUCCESS"}]
    result = analyze_transaction(tx, callbacks)
    assert any("retries occurred" in a for a in result["anomalies"])


def test_summarize_stuck_report_counts_correctly():
    rows = [
        {"status": "PROCESSING"},
        {"status": "PROCESSING"},
        {"status": "FAILED"},
    ]
    summary = summarize_stuck_report(rows)
    assert summary["stuck_processing_count"] == 2
    assert summary["recent_failed_count"] == 1
    assert summary["total_flagged"] == 3
