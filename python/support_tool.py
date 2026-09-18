#!/usr/bin/env python3
"""MiniPay L2 Support Utility.

Usage:
    python support_tool.py --transaction TXN000123
    python support_tool.py --transaction TXN000123 --json
    python support_tool.py --health
    python support_tool.py --stuck-report [--json]

Exit codes:
    0 = success
    1 = transaction/resource not found
    2 = configuration or connectivity error
    3 = unexpected internal error
"""
import argparse
import json
import logging
import sys

import requests

from lib.config import Config
from lib.db import DBConnectionError, fetch_callbacks, fetch_stuck_or_failed, fetch_transaction, get_connection
from lib.diagnostics import analyze_transaction, summarize_stuck_report

logger = logging.getLogger("support_tool")


def setup_logging(verbose):
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stderr,
    )


def cmd_transaction(cfg, ref, as_json):
    conn = get_connection(cfg)
    try:
        tx = fetch_transaction(conn, ref)
        if not tx:
            logger.warning("Transaction not found: %s", ref)
            if as_json:
                print(json.dumps({"error": "not_found", "transaction_ref": ref}))
            else:
                print(f"Transaction not found: {ref}")
            return 1

        callbacks = fetch_callbacks(conn, tx["id"])
        diagnosis = analyze_transaction(tx, callbacks, stuck_threshold_minutes=cfg.stuck_threshold_minutes)

        report = {
            "transaction_ref": tx["transaction_ref"],
            "customer_ref": tx["customer_ref"],
            "customer_name": tx["customer_name"],
            "amount": str(tx["amount"]),
            "status": tx["status"],
            "created_at": str(tx["created_at"]),
            "completed_at": str(tx["completed_at"]) if tx["completed_at"] else None,
            "failure_code": tx["failure_code"],
            "callback_attempts": len(callbacks),
            "callbacks": [
                {
                    "attempt_no": c["attempt_no"],
                    "http_status": c["http_status"],
                    "status": c["callback_status"],
                    "attempted_at": str(c["attempted_at"]),
                }
                for c in callbacks
            ],
            "anomalies": diagnosis["anomalies"],
            "recommended_action": diagnosis["recommended_action"],
        }

        if as_json:
            print(json.dumps(report, indent=2))
        else:
            print(f"=== Transaction {report['transaction_ref']} ===")
            print(f"Customer:    {report['customer_name']} ({report['customer_ref']})")
            print(f"Amount:      {report['amount']}")
            print(f"Status:      {report['status']}")
            print(f"Created:     {report['created_at']}")
            print(f"Completed:   {report['completed_at']}")
            print(f"Failure code:{report['failure_code']}")
            print(f"Callbacks:   {report['callback_attempts']} attempt(s)")
            for cb in report["callbacks"]:
                print(f"  - attempt {cb['attempt_no']}: {cb['status']} (HTTP {cb['http_status']}) at {cb['attempted_at']}")
            print("Anomalies:")
            for a in report["anomalies"]:
                print(f"  - {a}")
            print(f"Recommended action: {report['recommended_action']}")
        return 0
    finally:
        conn.close()


def cmd_health(cfg, as_json):
    result = {"db": "unknown", "api": "unknown"}
    exit_code = 0
    try:
        conn = get_connection(cfg, timeout_seconds=3)
        conn.cursor().execute("SELECT 1;")
        conn.close()
        result["db"] = "ok"
    except Exception as e:
        result["db"] = f"unreachable: {e}"
        exit_code = 2

    try:
        resp = requests.get(f"{cfg.api_url}/health", timeout=3)
        result["api"] = "ok" if resp.status_code == 200 else f"degraded (HTTP {resp.status_code})"
        if resp.status_code != 200:
            exit_code = 2
    except Exception as e:
        result["api"] = f"unreachable: {e}"
        exit_code = 2

    if as_json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Database: {result['db']}")
        print(f"API:      {result['api']}")
    return exit_code


def cmd_stuck_report(cfg, as_json):
    conn = get_connection(cfg)
    try:
        rows = fetch_stuck_or_failed(conn, cfg.stuck_threshold_minutes)
        summary = summarize_stuck_report(rows)
        if as_json:
            print(json.dumps({"summary": summary, "transactions": [
                {**r, "created_at": str(r["created_at"])} for r in rows
            ]}, indent=2))
        else:
            print(f"Stuck (PROCESSING > {cfg.stuck_threshold_minutes}min): {summary['stuck_processing_count']}")
            print(f"Recently FAILED (24h):                {summary['recent_failed_count']}")
            for r in rows[:20]:
                print(f"  - {r['transaction_ref']}: {r['status']} since {r['created_at']} ({r.get('failure_code') or ''})")
        return 0
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="MiniPay L2 support diagnostic tool")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--transaction", metavar="REF", help="Diagnose a single transaction by reference")
    group.add_argument("--health", action="store_true", help="Check API + database health")
    group.add_argument("--stuck-report", action="store_true", help="Summarize stuck/failed transactions")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    parser.add_argument("--config", metavar="PATH", help="Optional key=value config file")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    setup_logging(args.verbose)

    try:
        cfg = Config(config_file=args.config)
        cfg.validate()
    except ValueError as e:
        logger.error("Configuration error: %s", e)
        return 2

    try:
        if args.transaction:
            return cmd_transaction(cfg, args.transaction, args.json)
        if args.health:
            return cmd_health(cfg, args.json)
        if args.stuck_report:
            return cmd_stuck_report(cfg, args.json)
    except DBConnectionError as e:
        logger.error("Could not connect to database: %s", e)
        return 2
    except Exception as e:
        logger.exception("Unexpected error: %s", e)
        return 3


if __name__ == "__main__":
    sys.exit(main())
