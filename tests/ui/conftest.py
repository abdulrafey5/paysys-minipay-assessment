import pytest


@pytest.fixture(autouse=True)
def capture_browser_diagnostics(page):
    page.on("console", lambda msg: print(f"[console:{msg.type}] {msg.text}") if msg.type == "error" else None)
    page.on("requestfailed", lambda req: print(f"[requestfailed] {req.url} -> {req.failure}"))
    page.on("pageerror", lambda exc: print(f"[pageerror] {exc}"))
    yield
