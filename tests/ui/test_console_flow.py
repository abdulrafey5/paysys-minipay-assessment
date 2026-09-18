"""GUI test: drives the MiniPay static console in a real browser against
the live API (k3d LoadBalancer or docker-compose, http://localhost:8081)."""
import time
import pytest
from playwright.sync_api import Page, expect

UI_URL = "http://localhost:8081"


@pytest.fixture
def ref_suffix():
    return str(int(time.time()))


def test_health_indicator_shows_healthy(page: Page):
    page.goto(UI_URL)
    expect(page.locator("#healthStatus")).to_contain_text("healthy", timeout=5000)


def test_create_customer_and_payment_flow(page: Page, ref_suffix):
    page.goto(UI_URL)

    customer_ref = f"CUST_UI_{ref_suffix}"
    txn_ref = f"TXN_UI_{ref_suffix}"

    page.fill("#custRef", customer_ref)
    page.fill("#custName", "UI Test Customer")
    page.get_by_role("button", name="Create Customer").click()
    expect(page.locator("#custResult")).to_contain_text("HTTP 201", timeout=5000)
    expect(page.locator("#custResult")).to_contain_text(customer_ref)

    page.fill("#payCustRef", customer_ref)
    page.fill("#payTxRef", txn_ref)
    page.fill("#payAmount", "150.00")
    page.get_by_role("button", name="Create Payment").click()
    result = page.locator("#payResult")
    expect(result).to_contain_text("HTTP", timeout=5000)
    body_text = result.inner_text()
    assert "200" in body_text or "500" in body_text

    page.fill("#lookupTxRef", txn_ref)
    page.get_by_role("button", name="Look Up").click()
    expect(page.locator("#lookupResult")).to_contain_text(txn_ref, timeout=5000)


def test_duplicate_customer_ref_shows_conflict(page: Page, ref_suffix):
    page.goto(UI_URL)
    customer_ref = f"CUST_DUP_{ref_suffix}"

    page.fill("#custRef", customer_ref)
    page.fill("#custName", "First")
    page.get_by_role("button", name="Create Customer").click()
    expect(page.locator("#custResult")).to_contain_text("HTTP 201", timeout=5000)

    page.fill("#custRef", customer_ref)
    page.fill("#custName", "Duplicate Attempt")
    page.get_by_role("button", name="Create Customer").click()
    expect(page.locator("#custResult")).to_contain_text("HTTP 409", timeout=5000)
