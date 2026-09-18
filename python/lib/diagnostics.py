"""Pure diagnostic logic — no I/O — so it can be unit tested without a live DB."""
from datetime import datetime, timedelta


def analyze_transaction(tx, callbacks, now=None, stuck_threshold_minutes=15):
    """Given a transaction dict and its callback rows, return anomalies and a
    recommended next action. Kept side-effect-free and dependency-free for
    straightforward unit testing."""
    now = now or datetime.utcnow()
    anomalies = []
    recommended_action = "No action needed; transaction appears healthy."

    if tx["status"] == "PROCESSING":
        age = now - tx["created_at"]
        if age > timedelta(minutes=stuck_threshold_minutes):
            anomalies.append(
                f"Transaction has been PROCESSING for {age}, exceeding the "
                f"{stuck_threshold_minutes}-minute SLA threshold."
            )
            recommended_action = (
                "Escalate to L3/payments team: transaction stuck in PROCESSING "
                "beyond SLA. Check payment worker/queue logs for this transaction_ref."
            )
        else:
            recommended_action = "Transaction still within normal processing window; monitor."

    elif tx["status"] == "FAILED":
        failed_cb = [c for c in callbacks if c["callback_status"] == "FAILED"]
        if failed_cb:
            anomalies.append(f"{len(failed_cb)} callback attempt(s) also failed.")
        code = tx.get("failure_code") or "UNKNOWN"
        recommended_action = (
            f"Transaction failed (code: {code}). If code indicates a transient "
            "upstream error, a retry may be appropriate; otherwise notify customer "
            "and check upstream provider status."
        )

    elif tx["status"] == "SUCCESS":
        success_cb = [c for c in callbacks if c["callback_status"] == "SUCCESS"]
        if not success_cb:
            anomalies.append(
                "Transaction marked SUCCESS but no successful callback was recorded "
                "— possible reconciliation mismatch between payment and notification."
            )
            recommended_action = (
                "Investigate callback delivery pipeline; customer/downstream system "
                "may not have been notified despite successful processing."
            )

    if len(callbacks) > 1:
        anomalies.append(f"{len(callbacks)} callback attempts recorded (retries occurred).")

    if not anomalies:
        anomalies.append("No anomalies detected.")

    return {"anomalies": anomalies, "recommended_action": recommended_action}


def summarize_stuck_report(rows):
    """Group a list of stuck/failed transaction rows into a small summary dict."""
    stuck = [r for r in rows if r["status"] == "PROCESSING"]
    failed = [r for r in rows if r["status"] == "FAILED"]
    return {
        "stuck_processing_count": len(stuck),
        "recent_failed_count": len(failed),
        "total_flagged": len(rows),
    }
