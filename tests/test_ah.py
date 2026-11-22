"""Tests against recorded AH API responses (tests/fixtures), no network."""
import json
from datetime import date
from pathlib import Path

import httpx
import pytest

from grocery_assistant import notify
from grocery_assistant.config import load_queries
from grocery_assistant.formatters import build_posts, euro, split
from grocery_assistant.runner import collect, run
from grocery_assistant.stores.ah import AHClient

ROOT = Path(__file__).parent.parent
FIXTURE = json.loads((ROOT / "tests/fixtures/ah_search_9344.json").read_text())


def ah_transport(calls: list | None = None) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if calls is not None:
            calls.append(request)
        if request.url.path.endswith("/auth/token/anonymous"):
            return httpx.Response(200, json={"access_token": "t", "expires_in": 600})
        assert request.headers["Authorization"] == "Bearer t"
        if request.url.params["taxonomyId"] == "9344":
            return httpx.Response(200, json=FIXTURE)
        return httpx.Response(200, json={"products": []})

    return httpx.MockTransport(handler)


@pytest.fixture
def query():
    return load_queries(ROOT / "config/queries.yaml")["ah-meat-fish-meals"]


def titles(sections):
    return {label: [p.title for p in ps] for label, ps in sections}


def test_config_loads(query):
    assert query.schedule == "0 8 * * 1"
    assert [c.id for c in query.categories] == [9344, 5481, 1651, 1301]


def test_only_in_store_and_valid_today(query):
    with AHClient(transport=ah_transport(), pause=0) as c:
        sun = titles(collect(query, c, date(2026, 11, 22)))
        mon = titles(collect(query, c, date(2026, 11, 23)))
    # online-only (AHONLINE) and other-category products are dropped
    assert sun["Meat"] == ["Unox Knaks"]
    assert sorted(mon["Meat"]) == [
        "AH Biologisch Spekreepjes gerookt", "AH Kipfilethaasjes", "AH Scharrel kipfilet 2 stuks",
    ]
    assert sun["Cold cuts"] == mon["Cold cuts"] == []


def test_dry_run_does_not_post(query, monkeypatch, capsys):
    monkeypatch.setattr(notify, "post", lambda *a, **k: pytest.fail("posted"))
    posts = run(query, day=date(2026, 11, 23), dry_run=True,
                client=AHClient(transport=ah_transport(), pause=0))
    assert posts[0].startswith("#### AH bonus week 48:")
    assert "3 in-store offers, valid until Sun 29 Nov." in posts[0]
    assert "**VOOR 3.49** (€5,49 → €3,49)" in posts[0]
    assert "https://www.ah.nl/producten/product/wi" in capsys.readouterr().out


def test_failure_is_reported_to_mattermost(query, monkeypatch):
    sent = []
    monkeypatch.setattr(notify, "post", lambda name, texts: sent.append((name, texts)))
    broken = httpx.MockTransport(lambda r: httpx.Response(503))
    with pytest.raises(httpx.HTTPStatusError):
        run(query, day=date(2026, 11, 23), client=AHClient(transport=broken, pause=0))
    assert sent and sent[0][0] == "supermarket_prices"
    assert "fetching failed" in sent[0][1][0]


def test_webhook_post(monkeypatch):
    got = []
    monkeypatch.setenv("MATTERMOST_WEBHOOK_TEST", "http://mm/hooks/x")
    monkeypatch.setattr("time.sleep", lambda s: None)
    t = httpx.MockTransport(lambda r: got.append(json.loads(r.content)) or httpx.Response(200))
    notify.post("test", ["a", "b"], transport=t)
    assert got == [{"text": "a"}, {"text": "b"}]


def test_missing_webhook(monkeypatch):
    monkeypatch.delenv("MATTERMOST_WEBHOOK_NOPE", raising=False)
    with pytest.raises(notify.WebhookNotConfigured):
        notify.webhook_url("nope")


def test_split_respects_limit():
    lines = [f"- line {i} " + "x" * 50 for i in range(100)]
    posts = split(lines, limit=500)
    assert all(len(p) <= 500 for p in posts)
    assert "\n".join(posts).split("\n") == lines


def test_empty_result():
    posts = build_posts("AH bonus week {week}", [("Meat", [])], date(2026, 11, 23))
    assert posts == ["#### AH bonus week 48\nNo bonus offers found."]


def test_euro():
    assert euro(3.5) == "€3,50" and euro(None) == ""
